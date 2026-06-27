"""
Agent 2 — Validation Agent (Grounding)
Rôle : Comparer ce que Gemini a dit avec les données réelles du catalogue MCP.
C'est lui qui détecte les hallucinations.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.mcp_server.catalog_server import verify_claim, get_manuscript_metadata

def validate_manuscript_claims(manuscript_id: str, claimed_author: str) -> dict:
    """
    Vérifie les affirmations de l'IA contre le catalogue archivistique MCP.
    Retourne le verdict : VERIFIED ou HALLUCINATION.
    """
    # Fix the case for shelf_mark since the mock catalog uses "Add MS 7474"
    if manuscript_id.lower() == "add_ms_7474":
        shelf_mark = "Add MS 7474"
    elif manuscript_id.lower() == "or_9011":
        shelf_mark = "Or 9011"
    else:
        shelf_mark = manuscript_id

    # 1. Récupère les vraies données du catalogue
    real_data = get_manuscript_metadata(shelf_mark)

    # 2. Compare l'auteur revendiqué avec le vrai auteur
    # verify_claim(claim, shelf_mark)
    claim = f"Author is {claimed_author}"
    verdict = verify_claim(claim, shelf_mark)
    
    is_verified = verdict.get("verified")
    
    if is_verified is True:
        final_verdict = "VERIFIED"
        confidence = 0.95
    elif is_verified is False:
        final_verdict = "HALLUCINATION DETECTED"
        confidence = 0.20
    else:
        final_verdict = "UNVERIFIED (Not in catalog)"
        confidence = 0.0

    return {
        "agent": "validation_agent",
        "manuscript_id": shelf_mark,
        "claimed_author": claimed_author,
        "real_author": real_data.get("author", "Unknown"),
        "verdict": final_verdict,
        "confidence": confidence,
        "source": "Qatar Digital Library / MCP",
        "verified_facts": [verdict.get("reason", "")]
    }


if __name__ == "__main__":
    # Test : Gemini a dit Ibn al-Haytham pour add_ms_7474 → devrait donner HALLUCINATION
    result = validate_manuscript_claims("add_ms_7474", "Ibn al-Haytham")
    print("=== VALIDATION AGENT RESULT ===")
    print(f"Auteur revendiqué : {result['claimed_author']}")
    print(f"Vrai auteur       : {result['real_author']}")
    print(f"Verdict           : {result['verdict']}  (confiance: {result['confidence']})")

