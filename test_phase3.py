import io
import json
from app import app
from db import get_session, ConceptMastery, MistakePattern, ConceptCatalog, Student, Assignment

def run_test():
    client = app.test_client()
    session = get_session()
    
    # Check if assignment 1 exists
    assignment = session.query(Assignment).first()
    if not assignment:
        print("No assignments found in DB. Please publish one first.")
        return
        
    assignment_id = str(assignment.assignment_id)
    print(f"Using Assignment ID: {assignment_id} ({assignment.title})")

    # Simulate a student answer file
    test_answer_content = b"""
Machine Learning Assignment
A1
Overfitting is when a model learns the training data perfectly including noise, so it fails on new data. Example: memorizing past exams.
A2
Supervised learning uses labeled data. Workflow is collecting data, processing, training, and predicting.
A3
Classification predicts categories.
A4
Bias is error from simplification. Variance is error from overfitting.
A5
Decision trees split data based on features to make a tree.
"""
    
    data = {
        'assignment_id': assignment_id,
        'student_id': 'S1',
        'file': (io.BytesIO(test_answer_content), 'test_answer.txt')
    }
    
    print("\n⏳ Submitting student answer for evaluation (this takes a moment)...")
    response = client.post('/evaluate_assignment', data=data, content_type='multipart/form-data')
    
    print(f"\n✅ Response Status: {response.status_code}")
    if response.status_code == 200:
        print("✅ Received structured JSON evaluation!")
    else:
        print("❌ Error:", response.data)
        return

    print("\n" + "="*40)
    print("🔍 CHECKING DATABASE FOR UPDATES")
    print("="*40)
    
    student = session.query(Student).filter_by(student_id="S1").first()
    print(f"Student 'S1' exists: {student is not None}")
    
    print("\n📈 CONCEPT MASTERY FOR S1:")
    mastery = session.query(ConceptMastery).filter_by(student_id="S1").all()
    if not mastery:
        print("No mastery records found.")
    for m in mastery:
        concept = session.query(ConceptCatalog).get(m.concept_id)
        status = "🟢 Understood (>=70%)" if m.mastery > 0.5 else "🔴 Confused (<70%)"
        print(f" - {concept.label}: {m.mastery:.2f}  {status}")
        
    print("\n⚠️ MISTAKE COUNTS FOR S1:")
    mistakes = session.query(MistakePattern).filter_by(student_id="S1").all()
    if not mistakes:
        print("No mistakes logged! Perfect answers.")
    for m in mistakes:
        concept = session.query(ConceptCatalog).get(m.concept_id)
        print(f" - {concept.label} | Tag: '{m.mistake_tag}' | Count: {m.count}")
        
    session.close()

if __name__ == '__main__':
    run_test()
