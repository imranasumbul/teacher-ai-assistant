"""
Assignment Evaluation Module
Evaluates student assignments using RAG and LLM for explainable feedback
"""

import os
import json
import re
from google import genai
from dotenv import load_dotenv

load_dotenv()

from embedder import generate_embeddings
from vector_store import get_vector_store
from extractor import extract_text

# Gemini API
GOOGLE_API_KEY = os.environ.get("GEMINI_API_KEY")
if GOOGLE_API_KEY:
    gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
else:
    gemini_client = None

def parse_json_from_text(text: str):
    text = (text or "").strip()
    text = text.replace("```json", "").replace("```", "").strip()
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None

def evaluate_assignment(student_answer_text, topic, subject, evaluation_rules_text):
    """
    Evaluate student assignment using RAG and LLM
    
    Args:
        student_answer_text (str): Extracted text from student's assignment
        topic (str): Assignment topic for context retrieval
        subject (str): Subject area
        evaluation_rules_text (str): Teacher's evaluation rules/rubric
        
    Returns:
        dict: Evaluation result with marks, feedback, etc.
    """
    if not gemini_client:
        return {"error": "Gemini API not configured"}
    
    if not student_answer_text.strip():
        return {"error": "No student answer text provided"}
    
    if not topic.strip():
        return {"error": "No topic provided"}
    
    # Generate embedding for topic to retrieve relevant context
    print(f"\n🔍 Retrieving context for topic: {topic}")
    embedding_pairs = generate_embeddings([topic])
    if not embedding_pairs:
        return {"error": "Could not generate embedding for topic"}
    
    query_vector = embedding_pairs[0][0]
    store = get_vector_store()
    results = store.search(query_vector, k=5) if store else []
    
    retrieved_texts = [r.get("chunk_text", "") for r in results]
    context_str = "\n\n".join([t for t in retrieved_texts if t]).strip()
    
    if not context_str:
        return {"error": "No relevant context found in teacher notes"}
    
    print(f"✅ Retrieved {len(retrieved_texts)} relevant chunks")
    
    # Build evaluation prompt
    prompt = f"""
You are a teacher evaluating a student's assignment submission.

Your task is to provide fair, explainable feedback based on:
1. The evaluation rules/rubric provided by the teacher
2. The reference content from teacher notes
3. The student's submitted answer

IMPORTANT RULES:
- Only evaluate based on content covered in the reference material
- If the answer goes off-syllabus or uses concepts not in the reference, flag it and deduct marks accordingly
- Provide specific, actionable feedback
- Be constructive and encouraging

Return ONLY valid JSON in this exact format:
{{
  "marks": <number out of 10>,
  "correct_points": ["Specific correct point 1", "Specific correct point 2"],
  "missing_points": ["Missing concept 1", "Missing concept 2"],
  "improvement_suggestions": ["Suggestion 1", "Suggestion 2"],
  "off_syllabus": <boolean - true if answer uses concepts not in reference material>
}}

EVALUATION RULES/RUBRIC:
{evaluation_rules_text}

REFERENCE CONTENT (Teacher Notes):
{context_str}

STUDENT ANSWER:
{student_answer_text}
""".strip()
    
    print("\n🤖 Calling Gemini for evaluation...")
    try:
        resp = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        
        parsed = parse_json_from_text(resp.text)
        
        if not parsed:
            print("❌ Failed to parse LLM response")
            return {"error": "Failed to parse evaluation response"}
        
        # System-level enforcement
        if parsed.get("off_syllabus", False):
            # Deduct marks for off-syllabus content
            original_marks = parsed.get("marks", 0)
            parsed["marks"] = max(0, original_marks - 3)  # Deduct 3 marks for off-syllabus
            parsed["missing_points"].append("Answer contains concepts not covered in class notes")
            parsed["improvement_suggestions"].append("Focus on concepts taught in class")
        
        # Ensure marks are reasonable
        parsed["marks"] = max(0, min(10, parsed.get("marks", 0)))
        
        print(f"✅ Evaluation complete: {parsed.get('marks')}/10 marks")
        return parsed
        
    except Exception as e:
        print(f"❌ Error during evaluation: {e}")
        return {"error": f"Evaluation failed: {str(e)}"}

if __name__ == "__main__":
    # Test the evaluator
    test_answer = "Machine learning is a subset of AI that uses algorithms to learn from data."
    test_topic = "Machine Learning"
    test_subject = "CS"
    test_rules = "Award marks for correct definitions, examples, and explanations. Deduct for incorrect information."
    
    result = evaluate_assignment(test_answer, test_topic, test_subject, test_rules)
    print("Test Result:", result)