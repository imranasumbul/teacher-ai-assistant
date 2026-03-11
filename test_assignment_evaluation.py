import os
import json
from dotenv import load_dotenv

load_dotenv()

from db import init_db
from vector_store import get_vector_store, save_to_vector_store
from embedder import generate_embeddings
from assignment_checker import evaluate_assignment

def run_test():
    print("\n--- Starting Assignment Evaluation Backend Test ---")
    
    # 1. Initialize DB (just in case)
    init_db()
    
    # 2. Add some dummy context to the vector store (Simulating teacher notes upload)
    teacher_notes = [
        "Photosynthesis is the process by which green plants and certain other organisms transform light energy into chemical energy.",
        "During photosynthesis in green plants, light energy is captured and used to convert water, carbon dioxide, and minerals into oxygen and energy-rich organic compounds.",
        "The primary pigment involved in photosynthesis is chlorophyll, which gives plants their green color."
    ]
    
    print("📝 Generating embeddings for dummy teacher notes (Photosynthesis)...")
    embedding_pairs = generate_embeddings(teacher_notes)
    if embedding_pairs:
        save_to_vector_store(embedding_pairs, "dummy_biology_notes.txt")
        print("✅ Dummy notes added to vector store")
    else:
        print("❌ Failed to generate embeddings. Is GEMINI_API_KEY set?")
        return

    # 3. Define the Teacher's Evaluation Rules (Rubric)
    evaluation_rules = """
    Rubric for Photosynthesis Question (Out of 10 Marks):
    - Mentioning light energy conversion to chemical energy: 3 marks
    - Mentioning water and carbon dioxide as inputs: 3 marks
    - Mentioning oxygen as an output: 2 marks
    - Mentioning chlorophyll: 2 marks
    - Deduct 1 mark for poor grammar (if applicable).
    """
    
    # 4. Define a good student answer
    good_student_answer = "Photosynthesis is how plants turn light into chemical energy. They use water and CO2 to produce oxygen. Chlorophyll helps them do this."
    
    # 5. Define a bad/off-syllabus student answer
    bad_student_answer = "Photosynthesis is when a plant uses electricity to grow. Plants breathe out nitrogen and eat soil."

    topic = "Photosynthesis"
    subject = "Biology"

    print("\n" + "="*50)
    print("🧪 TEST 1: Evaluating Good Student Answer")
    print("="*50)
    print(f"Student Answer: {good_student_answer}")
    
    result_good = evaluate_assignment(good_student_answer, topic, subject, evaluation_rules)
    print("\n📊 Result (Good Answer):")
    print(json.dumps(result_good, indent=2))

    print("\n" + "="*50)
    print("🧪 TEST 2: Evaluating Bad/Off-Syllabus Student Answer")
    print("="*50)
    print(f"Student Answer: {bad_student_answer}")
    
    result_bad = evaluate_assignment(bad_student_answer, topic, subject, evaluation_rules)
    print("\n📊 Result (Bad Answer):")
    print(json.dumps(result_bad, indent=2))
    
    print("\n--- Test Complete ---")

if __name__ == "__main__":
    run_test()
