import requests

BASE_URL = "http://127.0.0.1:5000"

payload = {
    "student_id": "S2",
    "subject": "ML",
    "question_text": "What is Artificial Bee Colony Algorithm?",
    "concept_ids": [1, 8, 2, 12],   # <-- replace with YOUR concept_ids from /ask
    "feedback": "understood"  # or "understood"
}

r = requests.post(f"{BASE_URL}/feedback", json=payload)
print(r.status_code)
print(r.text)