import requests

BASE_URL = "http://127.0.0.1:5000"

payload = {
    "student_id": "S2",
    "subject": "ML",
    "question_text": "How do supervised and unsupervised learning differ?",
    "concept_ids": [9, 10,11],   # <-- replace with YOUR concept_ids from /ask
    "feedback": "confused"  # or "understood"
}

r = requests.post(f"{BASE_URL}/feedback", json=payload)
print(r.status_code)
print(r.text)