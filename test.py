import os
from dotenv import load_dotenv

load_dotenv()  # Carica il .env

token = os.getenv("DISCORD_TOKEN")

if token is None:
    print("❌ Errore: variabile DISCORD_TOKEN non trovata.")
elif len(token) < 50:
    print(f"⚠️ Token caricato ma troppo corto: {token}")
else:
    print(f"✅ Token caricato correttamente: {token[:10]}...")
