import requests

BASE_URL = "http://127.0.0.1:5000"

payload = {
    "student_id": "S1",
    "subject": "ML",
    "question_text": "What is Artificial Bee Colony Optimization?",
    "concept_ids": [1, 2, 3, 4, 7],   # <-- replace with YOUR concept_ids from /ask
    "feedback": "confused"  # or "understood"
}

r = requests.post(f"{BASE_URL}/feedback", json=payload)
print(r.status_code)
print(r.text)