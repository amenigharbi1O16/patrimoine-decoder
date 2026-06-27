import os
import json
import base64
from dotenv import load_dotenv

# On utilise l'ancien SDK (google-generativeai) car il pointe vers
# l'endpoint stable generativelanguage.googleapis.com — accessible depuis toutes les régions.
import google.generativeai as genai

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("Clé GOOGLE_API_KEY manquante dans le fichier .env")

# Configure le SDK avec la clé API
genai.configure(api_key=api_key)

MANUSCRIPTS_DIR = os.path.join("data", "manuscripts")
RESULTS_DIR = os.path.join("data", "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# Prompt envoyé à Gemini Vision pour tester ses capacités sur chaque manuscrit
PROMPT = (
    "Analyze this historical Arabic manuscript page. "
    "Provide a transcription of the visible text in modern Arabic script, "
    "identify the author, the title of the work, and the approximate date. "
    "If you are not sure about the author or title, state it clearly."
)

def encode_image_to_base64(image_path: str) -> str:
    """Lit une image depuis le disque et la convertit en base64 pour l'API."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def run_test():
    tests = {
        "Add MS 7474": os.path.join(MANUSCRIPTS_DIR, "add_ms_7474.jpg"),
        "Or 9011":     os.path.join(MANUSCRIPTS_DIR, "or_9011.jpg")
    }

    results = {}

    # gemini-2.5-flash : modèle multimodal le plus récent disponible sur ce projet
    model = genai.GenerativeModel("gemini-2.5-flash")

    print("\n=== DÉBUT DES TESTS GEMINI VISION ===\n")

    for name, path in tests.items():
        print(f"Analyzing manuscript: {name}...")

        if not os.path.exists(path):
            print(f"  Image not found: {path}\n")
            continue

        try:
            # Prépare l'image encodée en base64
            image_b64 = encode_image_to_base64(path)

            # Appel à l'API avec l'image et le texte du prompt
            response = model.generate_content([
                PROMPT,
                {"mime_type": "image/jpeg", "data": image_b64}
            ])

            response_text = response.text
            print(f"\n--- RÉSULTAT POUR {name} ---")
            print(response_text)
            print("-" * 50 + "\n")

            results[name] = {
                "shelf_mark": name,
                "prompt_used": PROMPT,
                "gemini_response": response_text
            }

        except Exception as e:
            print(f"  Error for {name}: {e}\n")
            results[name] = {"shelf_mark": name, "error": str(e)}

    # Sauvegarde du rapport final
    output_path = os.path.join(RESULTS_DIR, "test_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    print(f"Test complete. Results saved to: {output_path}")

if __name__ == "__main__":
    run_test()