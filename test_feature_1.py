import requests

BASE_URL = "http://127.0.0.1:5000"


def test_ask_question(question, subject="general", student_id="S1", debug=False, expected_status=200):
    print(f"\n❓ Asking: {question!r} | subject={subject} | student_id={student_id} | debug={debug}")

    url = f"{BASE_URL}/ask"
    payload = {
        "question": question,
        "subject": subject,
        "student_id": student_id,
        "debug": debug,   # ✅ THIS is what makes backend return debug payload
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

                # ✅ print debug if present
                dbg = data.get("debug")
                if dbg:
                    print("\n   ========== DEBUG ==========")
                    print(f"   cold_start: {dbg.get('cold_start')}")
                    print(f"   avg_mastery_subject: {dbg.get('avg_mastery_subject')}")
                    print(f"   subject_mistake_counts_used: {dbg.get('subject_mistake_counts_used')}")
                    print(f"   concept_mastery_map_next_time: {dbg.get('concept_mastery_map_next_time')}")
                    print(f"   concept_mistake_counts_next_time: {dbg.get('concept_mistake_counts_next_time')}")
                    print("   --- style_instruction_used ---")
                    print(dbg.get("style_instruction_used"))
                    print("   ==============================\n")
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

    test_ask_question(
        "What is Artificial Bee Colony Algorithm?",
        subject="ML",
        student_id="S2",
        debug=True,          # ✅ Python True
        expected_status=200
    )

    print("\n✅ Test Complete")