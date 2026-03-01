import requests

BASE_URL = "http://127.0.0.1:5000"


def test_ask_question(question, subject="general", student_id="S1", expected_status=200):
    print(f"\n❓ Asking: {question!r} | subject={subject} | student_id={student_id}")

    url = f"{BASE_URL}/ask"
    payload = {
        "question": question,
        "subject": subject,
        "student_id": student_id,  # backend may ignore for now (fine)
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        print(f"   Status Code: {response.status_code}")

        if response.status_code == expected_status:
            if response.status_code == 200:
                data = response.json()
                print(f"   🤖 Answer: {data.get('answer')}")
                print(f"   🧠 Concept Labels: {data.get('concept_labels')}")
                print(f"   🆔 Concept IDs: {data.get('concept_ids')}")
            else:
                print("   ✅ Got expected error/response.")
                print(f"   Response: {response.text}")
        else:
            print("   ❌ Unexpected status!")
            print(f"   Expected: {expected_status}, Got: {response.status_code}")
            print(f"   Response: {response.text}")

        return response

    except Exception as e:
        print(f"   ❌ Connection/Error: {str(e)}")
        return None


if __name__ == "__main__":
    print("🧪 Testing: RAG + Concept Catalog (Phase 2)")
    print("=" * 60)

    # 1) Basic question (subject provided)
    test_ask_question(
        "What is Artificial Bee Colony Optimization?",
        subject="ML",
        student_id="S1",
        expected_status=200
    )

    # 2) Irrelevant question (should likely reply 'Not in syllabus' if notes don't cover it)
    test_ask_question(
        "What is the capital of France?",
        subject="ML",
        student_id="S1",
        expected_status=200
    )

    # 3) Empty question (backend will return 400)
    test_ask_question(
        "",
        subject="ML",
        student_id="S1",
        expected_status=400
    )

    print("\n✅ Test Complete")