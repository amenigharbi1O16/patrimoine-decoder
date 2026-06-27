import requests, json, time, os

API = os.getenv("API_URL", "http://localhost:8000")
USERNAME = os.getenv("TEST_USER", "final_test")
PASSWORD = os.getenv("TEST_PASS", "testpass123")


def get_token():
    """Register (or login) and return JWT bearer token."""
    for endpoint in ("/api/register", "/api/login"):
        try:
            r = requests.post(
                f"{API}{endpoint}",
                json={"username": USERNAME, "password": PASSWORD},
                timeout=10,
            )
            if r.status_code in (200, 201):
                return r.json()["access_token"]
        except Exception:
            pass
    raise RuntimeError("Could not authenticate — is the backend running?")


def run_tests():
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{API}/api/analyze"

    tests = [
        {
            "name": "TEST A - Or 9011 + ibn al haytham -> HALLUCINATION 5%",
            "data": {
                "manuscript_id": "or_9011",
                "claimed_author": "ibn al haytham",
                "target_language": "English",
            },
            "file": "data/manuscripts/or_9011.jpg",
            "expect_verdict": "HALLUCINATION",
            "expect_confidence": 5,
        },
        {
            "name": "TEST B - Add MS 7474 + Ptolemy -> VERIFIED 95%",
            "data": {
                "manuscript_id": "add_ms_7474",
                "claimed_author": "Ptolemy",
                "target_language": "English",
            },
            "file": "data/manuscripts/add_ms_7474.jpg",
            "expect_verdict": "VERIFIED",
            "expect_confidence": 95,
        },
        {
            "name": "TEST C - Arabic text paste -> real translation",
            "data": {
                "manuscript_id": "none",
                "claimed_author": "",
                "target_language": "English",
                "text_input": (
                    "كتاب المجسطي — تأليف بطليموس الحكيم. "
                    "المقالة الأولى في علم الفلك والهيئة."
                ),
            },
            "file": None,
            "expect_translation": True,
        },
    ]

    passed = 0
    for test in tests:
        sep = "=" * 60
        print(sep)
        print(test["name"])
        print(sep)
        try:
            if test["file"]:
                with open(test["file"], "rb") as f:
                    r = requests.post(
                        url, files={"file": f}, data=test["data"],
                        headers=headers, timeout=120,
                    )
            else:
                r = requests.post(
                    url, data=test["data"], headers=headers, timeout=120,
                )
            if r.status_code == 401:
                print("  FAIL: 401 Unauthorized — check auth")
                continue
            if r.status_code != 200:
                print(f"  FAIL: HTTP {r.status_code} — {r.text[:200]}")
                continue
            d = r.json()
            verdict = d.get("verdict")
            confidence = d.get("confidence_score")
            translation = d.get("translation") or ""
            explanation = d.get("explanation") or ""
            print(f"  VERDICT     : {verdict}")
            print(f"  CONFIDENCE  : {confidence}%")
            print(f"  TRANSLATION : {translation[:120]}...")
            print(f"  EXPLANATION : {explanation[:120]}")

            ok = True
            if "expect_verdict" in test:
                ok = verdict == test["expect_verdict"]
                if "expect_confidence" in test:
                    ok = ok and confidence == test["expect_confidence"]
            if test.get("expect_translation"):
                ok = ok and len(translation) > 20
                ok = ok and "unavailable" not in translation.lower()

            print(f"  RESULT      : {'PASS' if ok else 'FAIL'}")
            if ok:
                passed += 1
        except Exception as e:
            print(f"  ERROR: {e}")
        time.sleep(1)

    print("\n" + "=" * 60)
    print(f"SUMMARY: {passed}/{len(tests)} tests passed")
    print("=" * 60)
    return passed == len(tests)


if __name__ == "__main__":
    success = run_tests()
    raise SystemExit(0 if success else 1)
