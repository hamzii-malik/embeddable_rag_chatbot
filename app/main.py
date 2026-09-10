import os
from html import escape
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session

from .database import init_db, get_db
from .models import Website
from .tasks import process_website_task
from .rag import generate_rag_answer

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

app = FastAPI(title="EMBEDD IQ")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.on_event("startup")
def startup():
    init_db()

class ScanRequest(BaseModel):
    url: HttpUrl

class ChatRequest(BaseModel):
    website_id: str
    query: str = Field(min_length=1, max_length=2000)

@app.post("/api/scan")
def start_scan(payload: ScanRequest, db: Session = Depends(get_db)):
    website = Website(url=str(payload.url), status="PROCESSING")
    db.add(website)
    db.commit()
    db.refresh(website)

    process_website_task(website.id, str(payload.url))
    return {"status": "processing", "website_id": website.id}

@app.get("/api/status/{website_id}")
def check_status(website_id: str, request: Request, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Not found")

    origin = str(request.base_url).rstrip("/")
    base = os.getenv("NGROK_URL") or (origin if "localhost" not in origin and "127.0.0.1" not in origin else BASE_URL)
    embed_snippet = f'<script src="{base}/static/widget.js" data-website-id="{website.id}"></script>'
    return {
        "website_id": website.id,
        "status": website.status,
        "name": website.name,
        "primary_color": website.primary_color,
        "stage": website.current_stage or website.status,
        "pages_scanned": website.pages_scanned or 0,
        "chunks_indexed": website.chunks_indexed or 0,
        "error": website.error_message if website.status == "FAILED" else None,
        "total_pages_scanned": len(website.total_pages) if website.total_pages else 0,
        "embed_code": embed_snippet if website.status == "COMPLETED" else None
    }

@app.get("/api/website/{website_id}/config")
def get_config(website_id: str, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website or website.status != "COMPLETED":
        raise HTTPException(status_code=404, detail="Pending")
    return {
      "name": website.name,
      "url": website.url,
      "logo_url": website.logo_url,
      "primary_color": website.primary_color,
    }

@app.post("/api/chat")
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    return {"answer": generate_rag_answer(db, payload.website_id, payload.query)}

@app.get("/preview/{website_id}")
def preview_website(website_id: str, request: Request, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website or website.status != "COMPLETED":
        raise HTTPException(status_code=404, detail="Chatbot not ready yet")

    site_url = website.url or ""
    if not site_url:
        raise HTTPException(status_code=404, detail="Website URL is missing")

    origin      = str(request.base_url).rstrip("/")
    widget_base = os.getenv("NGROK_URL") or (
        origin if ("localhost" not in origin and "127.0.0.1" not in origin) else BASE_URL
    )

    brand_name  = escape(website.name or "Support", quote=True)
    brand_color = escape(website.primary_color or "#17191d", quote=True)
    logo_url    = escape(website.logo_url or "", quote=True)
    widget_src  = escape(f"{widget_base}/static/widget.js", quote=True)
    safe_site   = escape(site_url, quote=True)

    # The website is rendered in the iframe and the widget is rendered in this
    # parent document, so the launcher remains above the website content.
    preview_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{brand_name} - Live Preview</title>
  <style>
    html, body {{ margin: 0; width: 100%; height: 100%; overflow: hidden; background: #fff; }}
    #site-frame {{ position: fixed; inset: 0; width: 100%; height: 100%; border: 0; background: #fff; }}
  </style>
</head>
<body>
  <iframe id="site-frame" src="{safe_site}" title="{brand_name} website"
          allow="fullscreen" sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-top-navigation"></iframe>
  <script src="{widget_src}" data-website-id="{website_id}"
          data-logo-url="{logo_url}" data-site-url="{safe_site}"></script>
</body>
</html>"""
    return HTMLResponse(preview_html)

    logo_img_tag = (
        f'<img class="fb-icon" src="{logo_url}" alt="{brand_name}" '
        'onerror="this.style.display=\'none\'" />'
        if logo_url else ""
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>{brand_name} — Chatbot Preview</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{ height: 100%; overflow: hidden; background: #0d0f12; }}

    /* Top chrome bar */
    #chrome {{
      position: fixed; top: 0; left: 0; right: 0; z-index: 2147483647;
      height: 48px;
      background: #111418;
      border-bottom: 1px solid #1e2228;
      display: flex; align-items: center; gap: 10px;
      padding: 0 16px;
      font-family: 'Segoe UI', system-ui, sans-serif;
    }}
    .dot {{ width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }}
    .dot-r {{ background: #ff5f57; }}
    .dot-a {{ background: #ffbd2e; }}
    .dot-g {{ background: #28c840; }}

    #urlbar {{
      flex: 1; height: 28px;
      background: #080a0d;
      border: 1px solid #1e2228;
      border-radius: 6px;
      display: flex; align-items: center; gap: 6px;
      padding: 0 10px;
      font-size: 12px; color: #6b7380;
      overflow: hidden;
    }}
    #urlbar span {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}

    #brandBadge {{
      display: flex; align-items: center; gap: 7px;
      padding: 4px 10px 4px 6px;
      border-radius: 999px;
      background: {brand_color};
      font-size: 12px; font-weight: 700;
      white-space: nowrap; flex-shrink: 0;
    }}
    #brandBadge img {{
      width: 20px; height: 20px; border-radius: 4px; object-fit: contain;
      background: rgba(255,255,255,.15); padding: 1px;
    }}

    /* The website iframe */
    #siteFrame {{
      position: fixed;
      top: 48px; left: 0; right: 0; bottom: 0;
      width: 100%; height: calc(100% - 48px);
      border: 0; background: #fff;
    }}

    /* Fallback shown when iframe is blocked */
    #fallback {{
      display: none;
      position: fixed;
      top: 48px; left: 0; right: 0; bottom: 0;
      background: #f4f5f7;
      align-items: center; justify-content: center;
      font-family: 'Segoe UI', system-ui, sans-serif;
    }}
    .fb-card {{
      background: #fff; border-radius: 16px;
      padding: 40px 36px; max-width: 480px; width: 90%;
      text-align: center;
      box-shadow: 0 4px 32px rgba(0,0,0,.10);
    }}
    .fb-icon {{
      width: 64px; height: 64px; border-radius: 14px;
      object-fit: contain; margin: 0 auto 20px;
      border: 1px solid #e8e8e8; display: block;
    }}
    .fb-icon-placeholder {{
      width: 64px; height: 64px; border-radius: 14px;
      background: {brand_color}22;
      display: flex; align-items: center; justify-content: center;
      margin: 0 auto 20px;
    }}
    .fb-icon-placeholder svg {{ width:32px; height:32px; fill:{brand_color}; }}
    .fb-title {{ font-size: 20px; font-weight: 700; color: #1a1a2e; margin-bottom: 8px; }}
    .fb-desc  {{ font-size: 14px; color: #666; line-height: 1.6; margin-bottom: 24px; }}
    .fb-btn {{
      display: inline-flex; align-items: center; gap: 8px;
      background: {brand_color}; color: #fff;
      padding: 12px 24px; border-radius: 10px;
      font-size: 14px; font-weight: 700;
      text-decoration: none; transition: opacity .2s;
    }}
    .fb-btn:hover {{ opacity: .88; }}
    .fb-note {{ font-size: 12px; color: #aaa; margin-top: 16px; }}
    .fb-chatbot-hint {{
      margin-top: 20px; padding: 12px 16px;
      background: {brand_color}11; border-radius: 8px;
      border-left: 3px solid {brand_color};
      font-size: 13px; color: #555; text-align: left;
    }}
  </style>
</head>
<body>

<!-- Browser chrome -->
<div id="chrome">
  <div class="dot dot-r"></div>
  <div class="dot dot-a"></div>
  <div class="dot dot-g"></div>

  <div id="urlbar">
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" stroke-width="2" style="flex-shrink:0">
      <rect x="3" y="11" width="18" height="11" rx="2"/>
      <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
    </svg>
    <span>{safe_site}</span>
  </div>

  <div id="brandBadge">
    <img id="brandLogo" src="{logo_url}" alt="{brand_name}"
         onerror="this.style.display='none'" />
    {brand_name}
  </div>
</div>

<!-- Actual website iframe -->
<iframe id="siteFrame" src="{safe_site}" title="{brand_name} website"
        allow="fullscreen"
        sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-top-navigation">
</iframe>

<!-- Fallback when iframe is blocked by X-Frame-Options / CSP -->
<div id="fallback">
  <div class="fb-card">
    {logo_img_tag}
    <div class="fb-title">{brand_name}</div>
    <div class="fb-desc">
      This website blocks preview embedding for security reasons — this is normal for sites like WhatsApp, Facebook, and others.<br><br>
      Your chatbot is still fully working! Use the chat button in the bottom-right corner to test it.
    </div>
    <a class="fb-btn" href="{safe_site}" target="_blank" rel="noopener">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
        <path d="M19 19H5V5h7V3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/>
      </svg>
      Open Website Directly
    </a>
    <div class="fb-chatbot-hint">
      💬 <strong>Chatbot is active</strong> — click the button in the bottom-right corner to start chatting with the AI assistant.
    </div>
    <div class="fb-note">The embed code works perfectly on your own website pages.</div>
  </div>
</div>

<!-- Widget — always injected, works regardless of iframe -->
<script src="{widget_src}"
        data-website-id="{website_id}"
  data-logo-url="{logo_url}"
  data-site-url="{safe_site}">
</script>

<script>
  (function(){{
    // Badge text colour
    const hex   = '{brand_color}'.replace('#','');
    const r = parseInt(hex.length===3 ? hex[0]+hex[0] : hex.slice(0,2),16);
    const g = parseInt(hex.length===3 ? hex[1]+hex[1] : hex.slice(2,4),16);
    const b = parseInt(hex.length===3 ? hex[2]+hex[2] : hex.slice(4,6),16);
    const light = (r*299+g*587+b*114)/1000 > 128;
    document.getElementById('brandBadge').style.color = light ? '#17191d' : '#ffffff';

  }})();
</script>
</body>
</html>"""
    return HTMLResponse(html)

@app.get("/", response_class=HTMLResponse)
def index():
    with open("app/static/index.html", encoding="utf-8", errors="replace") as f:
        return f.read()