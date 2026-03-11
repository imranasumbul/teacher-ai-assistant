import requests

BASE_URL = "http://127.0.0.1:5000"

payload = {
    "student_id": "S3",
    "subject": "PM",
    "question_text": "What is Proactive Personality?",
    "concept_ids": [20,15],   # <-- replace with YOUR concept_ids from /ask
    "feedback": "understood"  # or "understood"
}

r = requests.post(f"{BASE_URL}/feedback", json=payload)
print(r.status_code)
print(r.text)