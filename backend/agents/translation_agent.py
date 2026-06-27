"""
Agent 3 — Translation Agent
Rôle : Traduire le texte brut ou la transcription OCR dans la langue cible demandée par l'utilisateur.
"""
from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

def translate_text(text: str, target_language: str) -> str:
    """
    Traduit le texte dans la langue demandée via Groq Llama-3.3.
    """
    if not text.strip():
        return ""

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "votre_cle_groq_ici":
        return "Erreur : Clé GROQ_API_KEY manquante ou invalide"

    try:
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": f"Tu es un traducteur expert. Traduis le texte fourni en {target_language}. Retourne UNIQUEMENT la traduction finale sans commentaires."
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            temperature=0.2,
            max_completion_tokens=2000,
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"[Translation Error: {str(e)}]"

if __name__ == "__main__":
    test_text = "كتاب المجسطي"
    res = translate_text(test_text, "English")
    print(f"Original: {test_text}\nTranslation: {res}")
