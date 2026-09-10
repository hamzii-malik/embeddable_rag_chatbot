import threading
from .database import SessionLocal
from .models import Website
from .scanner import scan_website
from .rag import process_and_store_website_data


def _run_process_website(website_id: str, url: str):
    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if website:
            website.current_stage = "SCANNING"
            website.status = "PROCESSING"
            db.commit()

        def report_page(page_number, page_url):
            progress = db.query(Website).filter(Website.id == website_id).first()
            if progress:
                progress.current_stage = f"SCANNING page {page_number}: {page_url}"
                progress.pages_scanned = page_number
                db.commit()

        brand_info, pages_data = scan_website(url, on_page=report_page)

        if not pages_data:
            if website:
                website.status = "FAILED"
                website.error_message = "No readable HTML pages were found on this website."
                db.commit()
            return

        if website:
            website.name = brand_info.get("name")
            website.logo_url = brand_info.get("logo_url")
            website.primary_color = brand_info.get("primary_color")
            website.error_message = None
            website.total_pages = [p["url"] for p in pages_data]
            website.pages_scanned = len(pages_data)
            website.current_stage = "INDEXING content"
            db.commit()

        website.chunks_indexed = process_and_store_website_data(db, website_id, pages_data)
        website.current_stage = "FINALIZING chatbot"
        db.commit()
        website.status = "COMPLETED"
        website.current_stage = "READY"
        db.commit()
    except Exception as e:
        db.rollback()
        website = db.query(Website).filter(Website.id == website_id).first()
        if website:
            website.status = "FAILED"
            website.current_stage = "FAILED"
            website.error_message = str(e)[:1000]
            db.commit()
    finally:
        db.close()


def process_website_task(website_id: str, url: str):
    """Start website processing in a background thread (no Celery queue)."""
    thread = threading.Thread(
        target=_run_process_website,
        args=(website_id, url),
        daemon=True,
    )
    thread.start()