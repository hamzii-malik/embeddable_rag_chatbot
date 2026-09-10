"""
Script to launch ngrok tunnel for Embeddable RAG Bot.
Usage:
    venv\Scripts\python start_ngrok.py
    venv\Scripts\python start_ngrok.py --token YOUR_NGROK_AUTH_TOKEN
"""
import sys
import os
import argparse
from pyngrok import ngrok, conf

def main():
    parser = argparse.ArgumentParser(description="Start Ngrok tunnel for Embeddable RAG Bot")
    parser.add_argument("--token", help="Your ngrok authtoken (get free from https://dashboard.ngrok.com)")
    parser.add_argument("--port", type=int, default=8000, help="Local port to tunnel (default: 8000)")
    args = parser.parse_args()

    token = args.token or os.getenv("NGROK_AUTHTOKEN")
    if token:
        ngrok.set_auth_token(token)
        print("✅ Ngrok authtoken saved!")

    try:
        tunnel = ngrok.connect(args.port)
        public_url = tunnel.public_url
        print("\n" + "="*60)
        print("🚀 NGROK TUNNEL IS LIVE!")
        print("="*60)
        print(f"🌍 Public Dashboard URL: {public_url}")
        print(f"📦 Public Widget Script:  {public_url}/static/widget.js")
        print("="*60)
        print("\nAap is public URL ko kisi bhi external website par embed kar sakte hain!")
        print("Press Ctrl+C to stop the tunnel.\n")
        
        ngrok_process = ngrok.get_ngrok_process()
        ngrok_process.proc.wait()
    except KeyboardInterrupt:
        print("\nStopping ngrok tunnel...")
        ngrok.kill()
    except Exception as e:
        err_msg = str(e)
        if "ERR_NGROK_4018" in err_msg or "authentication failed" in err_msg.lower():
            print("\n" + "!"*60)
            print("⚠️  NGROK AUTHTOKEN REQUIRED")
            print("!"*60)
            print("Ngrok chalane ke liye ek baar free authtoken set karna zaroori hai:")
            print("1. Free account banayein: https://dashboard.ngrok.com/signup")
            print("2. Token yahan se copy karein: https://dashboard.ngrok.com/get-started/your-authtoken")
            print("3. Phir ye command run karein:")
            print("   venv\\Scripts\\python.exe start_ngrok.py --token <APKA_TOKEN>")
            print("   ya:")
            print("   C:\\Users\\hamza\\AppData\\Local\\ngrok\\ngrok.exe config add-authtoken <APKA_TOKEN>")
            print("!"*60 + "\n")
        else:
            print(f"❌ Error starting ngrok: {e}")

if __name__ == "__main__":
    main()
