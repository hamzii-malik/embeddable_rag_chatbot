import os
import re
import ssl
import threading
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from sqlalchemy.orm import Session
from sqlalchemy import text
from .models import DocumentChunk

load_dotenv()

gemini_api_key      = os.getenv("GEMINI_API_KEY")
gemini_model_name   = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
gemini_fallback_model = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-1.5-pro")

# Chat client — longer timeout
gemini_client = genai.Client(
    api_key=gemini_api_key,
    http_options=types.HttpOptions(api_version="v1beta", timeout=90000),
) if gemini_api_key else None

# Embed client — shorter timeout so we fail-fast and retry
embed_client = genai.Client(
    api_key=gemini_api_key,
    http_options=types.HttpOptions(api_version="v1beta", timeout=25000),
) if gemini_api_key else None

_EMBEDDING_MODEL  = os.getenv("GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-001")
_EMBEDDING_DIM    = 1536

_answer_cache     = {}
_cache_lock       = threading.Lock()
_cache_ttl        = int(os.getenv("RAG_CACHE_TTL_SECONDS", "300"))
_cache_size       = int(os.getenv("RAG_CACHE_SIZE", "512"))
_EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "20"))
_EMBED_DELAY      = float(os.getenv("EMBED_DELAY_SECONDS", "1.0"))
_EMBED_RETRIES    = int(os.getenv("EMBED_MAX_RETRIES", "5"))
_CHAT_RETRIES     = 4


def _is_transient(exc: Exception) -> bool:
    s = str(exc).upper()
    return isinstance(exc, (ssl.SSLError, TimeoutError, ConnectionError)) or any(
        k in s for k in ("SSL", "UNEXPECTED_EOF", "TIMEOUT", "TIMED OUT",
                         "CONNECTION RESET", "502", "503", "504", "DEADLINE")
    )


# ── Embeddings ────────────────────────────────────────────────────────────────

def _embed_with_retry(texts: list[str]) -> list[list[float]]:
    if not embed_client:
        raise RuntimeError("GEMINI_API_KEY not configured")
    last_exc = None
    for attempt in range(_EMBED_RETRIES):
        try:
            result = embed_client.models.embed_content(
                model=_EMBEDDING_MODEL,
                contents=texts,
                config=types.EmbedContentConfig(output_dimensionality=_EMBEDDING_DIM),
            )
            return [e.values for e in result.embeddings]
        except Exception as exc:
            last_exc = exc
            s = str(exc)
            if "429" in s or "RESOURCE_EXHAUSTED" in s:
                wait = (2 ** attempt) * 5
                print(f"[RAG] Embed rate-limit (attempt {attempt+1}), wait {wait}s")
                time.sleep(wait)
            elif _is_transient(exc) and attempt + 1 < _EMBED_RETRIES:
                wait = min(2 ** attempt, 8)
                print(f"[RAG] Embed transient error (attempt {attempt+1}), retry {wait}s")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Embedding failed after {_EMBED_RETRIES} retries: {last_exc}")


def get_embedding(text_data: str) -> list[float]:
    return _embed_with_retry([text_data])[0]


def get_embeddings(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    out = []
    for i in range(0, len(texts), _EMBED_BATCH_SIZE):
        out.extend(_embed_with_retry(texts[i:i + _EMBED_BATCH_SIZE]))
        if i + _EMBED_BATCH_SIZE < len(texts):
            time.sleep(_EMBED_DELAY)
    return out


# ── Chunking ──────────────────────────────────────────────────────────────────

def chunk_text(text_data: str, max_words: int = 200, overlap: int = 1) -> list[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text_data.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    chunks, cur, wc = [], [], 0
    for s in sentences:
        sw = len(s.split())
        if wc + sw > max_words and cur:
            chunks.append(" ".join(cur))
            cur = cur[-overlap:] if overlap else []
            wc = sum(len(x.split()) for x in cur)
        cur.append(s)
        wc += sw
    if cur:
        chunks.append(" ".join(cur))
    return [c for c in chunks if c.strip()]


# ── Indexing ──────────────────────────────────────────────────────────────────

def process_and_store_website_data(db: Session, website_id: str, pages_data: list) -> int:
    db.query(DocumentChunk).filter(DocumentChunk.website_id == website_id).delete()
    db.commit()
    pending = [(p["url"], c) for p in pages_data for c in chunk_text(p["text"]) if c.strip()]
    if not pending:
        return 0
    print(f"[RAG] Indexing {len(pending)} chunks…")
    vectors = get_embeddings([c for _, c in pending])
    db.add_all([
        DocumentChunk(website_id=website_id, page_url=url, content=chunk, embedding=vec)
        for (url, chunk), vec in zip(pending, vectors)
    ])
    db.commit()
    print(f"[RAG] Done — {len(pending)} chunks indexed.")
    return len(pending)


# ── Retrieval ─────────────────────────────────────────────────────────────────

def retrieve_relevant_chunks(db: Session, website_id: str, query: str, limit: int = 8) -> list:
    results, seen = [], set()

    # Stage 1 — vector cosine
    try:
        vec = get_embedding(query)
        vec_str = "[" + ",".join(map(str, vec)) + "]"
        rows = db.execute(text("""
            SELECT page_url, content, 1-(embedding <=> CAST(:v AS vector)) AS score
            FROM document_chunks WHERE website_id=:wid
            ORDER BY embedding <=> CAST(:v AS vector) LIMIT :lim
        """), {"wid": website_id, "v": vec_str, "lim": limit}).fetchall()
        for r in rows:
            k = r[1][:120]
            if k not in seen:
                seen.add(k); results.append(r)
    except Exception as e:
        print(f"[RAG] Vector search skipped: {type(e).__name__}: {str(e)[:80]}")

    # Stage 2 — FTS English
    need = limit - len(results)
    if need > 0:
        for sql, params in [
            # 2a phrase
            ("""SELECT page_url,content,ts_rank(to_tsvector('english',content),plainto_tsquery('english',:q)) AS s
                FROM document_chunks WHERE website_id=:wid
                AND to_tsvector('english',content)@@plainto_tsquery('english',:q)
                ORDER BY s DESC LIMIT :lim""",
             {"wid": website_id, "q": query, "lim": need}),
            # 2b OR keywords
            ("""SELECT page_url,content,ts_rank(to_tsvector('english',content),to_tsquery('english',:q)) AS s
                FROM document_chunks WHERE website_id=:wid
                AND to_tsvector('english',content)@@to_tsquery('english',:q)
                ORDER BY s DESC LIMIT :lim""",
             {"wid": website_id,
              "q": " | ".join(re.findall(r'\b[a-zA-Z0-9_]{3,}\b', query)) or query,
              "lim": need}),
        ]:
            try:
                for r in db.execute(text(sql), params).fetchall():
                    k = r[1][:120]
                    if k not in seen:
                        seen.add(k); results.append(r)
                        need -= 1
                if need <= 0:
                    break
            except Exception:
                pass

    # Stage 3 — ILIKE last resort
    if need > 0:
        for w in re.findall(r'\b[a-zA-Z0-9_]{3,}\b', query):
            try:
                for r in db.execute(text("""
                    SELECT page_url,content,0.1 AS s FROM document_chunks
                    WHERE website_id=:wid AND content ILIKE :t LIMIT :lim
                """), {"wid": website_id, "t": f"%{w}%", "lim": need}).fetchall():
                    k = r[1][:120]
                    if k not in seen:
                        seen.add(k); results.append(r)
                        need -= 1
            except Exception:
                pass
            if need <= 0:
                break

    return results[:limit]


# ── Answer generation ─────────────────────────────────────────────────────────

def _call_gemini(prompt: str, config: types.GenerateContentConfig) -> str:
    """Call generate_content with SSL/transient retry + model fallback."""
    models_to_try = (
        [gemini_model_name] if gemini_model_name == gemini_fallback_model
        else [gemini_model_name, gemini_fallback_model]
    )
    last_exc = None
    for model in models_to_try:
        for attempt in range(_CHAT_RETRIES):
            try:
                resp = gemini_client.models.generate_content(
                    model=model, contents=prompt, config=config
                )
                text_out = resp.text
                if text_out is None and resp.candidates:
                    try:
                        text_out = resp.candidates[0].content.parts[0].text
                    except Exception:
                        text_out = None
                if not text_out:
                    raise RuntimeError("Empty Gemini response (safety filter?)")
                return text_out.strip()
            except Exception as exc:
                last_exc = exc
                if _is_transient(exc) and attempt + 1 < _CHAT_RETRIES:
                    wait = min(2 ** attempt, 10)
                    print(f"[RAG] Chat transient error ({model}, attempt {attempt+1}), retry {wait}s: {exc}")
                    time.sleep(wait)
                else:
                    print(f"[RAG] Chat failed with model {model}: {exc}")
                    break   # try next model
    raise RuntimeError(f"All Gemini chat attempts failed: {last_exc}")


def generate_gemini_answer(context: str, query: str,
                           bot_name: str = "Assistant", website_url: str = "") -> str:
    if not gemini_client:
        raise RuntimeError("GEMINI_API_KEY not configured")

    has_ctx = bool(context and context.strip())
    system = (
        f"You are the official AI assistant for {bot_name}, "
        f"embedded on {website_url or 'this website'}.\n\n"
        "RULES:\n"
        "1. Answer ONLY from the provided context. Do not invent information.\n"
        "2. If the context lacks a clear answer, politely say so and suggest contacting the team.\n"
        "3. Be concise, professional, and friendly — clear paragraphs, no unnecessary bullet lists.\n"
        "4. Never expose raw URLs or internal chunk metadata.\n"
        f"5. If asked who you are: say you are the AI assistant for {bot_name}.\n"
        "6. Match the visitor's language (English, Urdu, Roman Urdu, etc.).\n"
        "7. Do NOT start with 'Based on the context' or similar meta-phrases."
    )
    body = (
        f"Context from the website:\n\n{context}\n\n---\nVisitor question: {query}"
        if has_ctx else
        f"No relevant content found.\n\nVisitor question: {query}\n\n"
        "Politely inform the visitor and suggest they contact the team."
    )
    cfg = types.GenerateContentConfig(
        temperature=0.15,
        max_output_tokens=int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "900")),
    )
    return _call_gemini(f"{system}\n\n{body}", cfg)


# ── Public entry point ────────────────────────────────────────────────────────

def generate_rag_answer(db: Session, website_id: str, query: str) -> str:
    cache_key = (website_id, " ".join(query.lower().split()))
    now = time.monotonic()
    with _cache_lock:
        hit = _answer_cache.get(cache_key)
        if hit and hit[0] > now:
            return hit[1]

    from .models import Website
    website  = db.query(Website).filter(Website.id == website_id).first()
    bot_name = (website.name or "Assistant") if website else "Assistant"
    site_url = (website.url  or "")          if website else ""

    results = retrieve_relevant_chunks(db, website_id, query, limit=8)
    context = "\n\n".join(
        re.sub(r'\[Image:[^\]]*\]', '', r[1]).strip()
        for r in results
        if re.sub(r'\[Image:[^\]]*\]', '', r[1]).strip()
    )

    try:
        answer = generate_gemini_answer(context, query, bot_name=bot_name, website_url=site_url)
    except Exception as exc:
        print(f"[RAG] Final Gemini failure: {exc}")
        answer = (
            "I'm sorry, I wasn't able to generate a response right now. "
            "Please try again in a moment or contact the team directly."
        )

    with _cache_lock:
        if len(_answer_cache) >= _cache_size:
            _answer_cache.pop(next(iter(_answer_cache)))
        _answer_cache[cache_key] = (now + _cache_ttl, answer)
    return answer
