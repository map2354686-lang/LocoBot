# keep_alive.py
from flask import Flask
import threading
import requests
import time
import os
import sys

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot is running and healthy!"

# 🚀 Uruchamia Flaska
def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# 💓 Self-ping co 10 minut (Render stay awake)
def self_ping():
    url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'locobot-whr2.onrender.com')}"
    while True:
        try:
            response = requests.get(url)
            print(f"[PING] Self-ping sent ({response.status_code}) ✅")
        except Exception as e:
            print(f"[PING ERROR] {e}")
        time.sleep(600)

# 🧠 Watchdog — sprawdza, czy Flask działa i restartuje proces, jeśli nie
def watchdog():
    url = f"http://localhost:{os.environ.get('PORT', 8080)}"
    while True:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                print("⚠️ Flask nie odpowiada poprawnie! Restartuję bota...")
                os.execv(sys.executable, ['python'] + sys.argv)
        except Exception:
            print("❌ Flask padł! Restartuję bota...")
            os.execv(sys.executable, ['python'] + sys.argv)
        time.sleep(300)  # sprawdzaj co 5 minut

# 🔧 Główna funkcja
def start_keep_alive():
    threading.Thread(target=run_web, daemon=True).start()
    threading.Thread(target=self_ping, daemon=True).start()
    threading.Thread(target=watchdog, daemon=True).start()
    print("🌐 Keep-alive system aktywny ✅")
