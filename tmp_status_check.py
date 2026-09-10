import os, sys, time, requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Make sure dotenv resolves the project .env reliably when running a file.
project_dir = r"c:\Users\hamza\Downloads\projects Week\embeddable-rag-bot"
load_dotenv(os.path.join(project_dir, '.env'))

print('START_CHECK')
try:
    db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:1234@localhost:5432/embedd_iq_db')
    engine = create_engine(db_url)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, url, status, current_stage, pages_scanned, chunks_indexed, error_message FROM websites ORDER BY created_at DESC LIMIT 5")).fetchall()
        print('DB_ROWS')
        for r in rows:
            print(dict(r._mapping))
except Exception as e:
    print('DB_ERROR', repr(e))

try:
    r = requests.get('http://127.0.0.1:8000/', timeout=20)
    print('APP_STATUS', r.status_code)
    print(r.text[:300])
except Exception as e:
    print('APP_ERROR', repr(e))
