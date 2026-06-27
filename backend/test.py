from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

if not api_key or api_key == "votre_cle_groq_ici":
    print("❌ Erreur: Clé GROQ_API_KEY manquante ou invalide dans le fichier .env")
    exit(1)

client = Groq(api_key=api_key)

try:
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "user",
                "content": "Say 'API key works!' in French"
            }
        ]
    )
    print("[OK] API Response:", completion.choices[0].message.content)
except Exception as e:
    print("[ERROR]", str(e)[:200])