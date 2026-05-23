"""
Assignment Evaluation Module
Evaluates student assignments using RAG and LLM for explainable feedback
"""

import os
import json
import re
from google import genai
from google.genai import types
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

def evaluate_single_answer(question_text, student_answer_text, rubric_text):
    """
    Evaluate a single student answer using LLM
    """
    if not gemini_client:
        return {"error": "Gemini API not configured"}
    
    prompt = f"""
You are an AI assignment evaluator.

Goal:
Evaluate a student's answer precisely and generate structured feedback for both backend processing and student report generation.

----------------------------------------

INPUT:
- Question
- Rubric (includes marking scheme and maximum marks)
- Student Answer

----------------------------------------

TASK:

For EACH question:

1. Evaluate strictly based on the rubric.
2. Assign score based ONLY on the rubric.
   - Do NOT assume total marks.
   - Extract maximum marks from rubric and score accordingly.

3. Extract ALL core learning concepts strictly from the QUESTION text:
   - Extract ONLY the core subjects being DIRECTLY interrogated/tested by the question.
   - DO NOT extract vague or contextual terms (e.g., "model performance", "accuracy", "data", "advantage").
   - Concepts MUST be highly specific to the subject domain (e.g., ML concepts like "bias", "variance", "decision trees").
   - Concepts MUST come ONLY from words/phrases explicitly present in the question.
   - Do NOT infer related concepts, and NEVER use the student answer for concept extraction.

4. Identify mistake types from the allowed list.

5. Generate clear feedback:
   - Correct Points → what student did right
   - Missing Points → what student missed or got wrong
   - Improvements → how to improve

----------------------------------------

ALLOWED MISTAKE TYPES (STRICT):
- concept_unclear
- incomplete_answer
- wrong_definition
- out_of_syllabus

----------------------------------------

STRICT OUTPUT FORMAT (JSON ONLY):

{{
  "score": <number>,
  "max_score": <number>,
  "concepts": ["<concept1>", "<concept2>"],
  "mistakes": ["<mistake_type1>", "<mistake_type2>"],
  "correct_points": ["point1", "point2"],
  "missing_points": ["point1", "point2"],
  "improvements": ["suggestion1", "suggestion2"]
}}

----------------------------------------

RULES:

- Be VERY precise. No long paragraphs.
- Each point should be short (1 line).
- Do NOT repeat same idea in multiple sections.
- Do NOT invent new mistake types.
- Always return valid JSON.
- If something is missing, return empty list [].
- Score must align with rubric marking distribution.
- STRICT CONCEPT EXTRACTION: Extract ONLY the direct subjects being tested. DO NOT extract contextual or vague terms like "model performance" or "advantage".

----------------------------------------

IMPORTANT:

- Output must be clean and structured so it can be directly shown in UI and converted into a student report (PDF).
- Do NOT include any text outside JSON.

QUESTION:
{question_text}

RUBRIC:
{rubric_text}

STUDENT ANSWER:
{student_answer_text}
""".strip()

    print("\n🤖 Calling Gemini for question evaluation...")
    try:
        resp = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.0)
        )
        
        parsed = parse_json_from_text(resp.text)
        
        if not parsed:
            print("❌ Failed to parse LLM response")
            return {"error": "Failed to parse evaluation response"}
        
        # Ensure score is reasonable (fallback to 0 if negative, don't clamp max since max_score varies)
        parsed["score"] = max(0, parsed.get("score", 0))
        
        print(f"✅ Evaluation complete: {parsed.get('score')}/{parsed.get('max_score')} score")
        return parsed
        
    except Exception as e:
        print(f"❌ Error during evaluation: {e}")
        return {"error": f"Evaluation failed: {str(e)}"}

def evaluate_assignment_batch(assignment_data: dict):
    """
    Evaluate multiple student answers in a single LLM call using RAG context.
    """
    if not gemini_client:
        return {"error": "Gemini API not configured"}
    
    prompt = f"""
You are an AI assignment evaluator.

Goal:
Evaluate a student's answers for an entire assignment and generate structured feedback for both backend processing and student report generation.

----------------------------------------

INPUT JSON:
{json.dumps(assignment_data, indent=2)}

----------------------------------------

TASK:

For EACH question in the input:

1. Use the provided CONTEXT as reference material.
   - Context contains relevant teacher notes retrieved via RAG.
   - Use it to verify correctness of the student's answer.
   - Do NOT ignore the context.

2. Evaluate the answer strictly based on:
   - rubric (PRIMARY)
   - context (SUPPORTING)

3. Assign score based ONLY on the rubric.
   - Do NOT assume total marks.
   - Extract maximum marks from rubric and score accordingly.

4. Extract ALL core learning concepts strictly from the QUESTION text:
   - Extract ONLY the core subjects being DIRECTLY interrogated/tested by the question.
   - DO NOT extract vague or contextual terms (e.g., "model performance", "accuracy", "data", "advantage").
   - Concepts MUST be highly specific to the subject domain (e.g., ML concepts like "bias", "variance", "decision trees").
   - Concepts MUST come ONLY from words/phrases explicitly present in the question.
   - Do NOT infer related concepts, and NEVER use the student answer for concept extraction.

5. Identify mistake types from the allowed list.

6. Generate clear feedback:
   - Correct Points → what student did right
   - Missing Points → what student missed or got wrong
   - Improvements → how to improve

----------------------------------------

ALLOWED MISTAKE TYPES (STRICT):
- concept_unclear
- incomplete_answer
- wrong_definition
- out_of_syllabus

----------------------------------------

OUTPUT FORMAT (STRICT JSON ONLY):

{{
  "results": [
    {{
      "id": <question_id_from_input>,
      "score": <number>,
      "max_score": <number>,
      "concepts": ["<concept1>", "<concept2>"],
      "mistakes": ["<mistake_type1>", "<mistake_type2>"],
      "correct_points": ["point1", "point2"],
      "missing_points": ["point1", "point2"],
      "improvements": ["suggestion1", "suggestion2"]
    }}
  ]
}}

----------------------------------------

RULES:

- Process EACH question independently.
- Do NOT mix answers between questions.
- Context is IMPORTANT — use it to judge correctness.
- Do NOT rely only on student answer.
- Do NOT hallucinate beyond context + rubric.
- Be VERY precise. No long paragraphs.
- Each feedback point should be short (1 line).
- Always return valid JSON.
- No text outside JSON.
- STRICT CONCEPT EXTRACTION: Extract ONLY the direct subjects being tested. DO NOT extract contextual or vague terms like "model performance" or "advantage".
""".strip()

    print("\n🤖 Calling Gemini for batch assignment evaluation...")
    try:
        resp = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.0)
        )
        
        parsed = parse_json_from_text(resp.text)
        
        if not parsed or "results" not in parsed:
            print("❌ Failed to parse batch LLM response")
            return {"error": "Failed to parse batch evaluation response"}
        
        # Ensure scores are reasonable
        for res in parsed["results"]:
            res["score"] = max(0, res.get("score", 0))
        
        print(f"✅ Batch Evaluation complete: {len(parsed['results'])} results")
        return parsed
        
    except Exception as e:
        print(f"❌ Error during batch evaluation: {e}")
        return {"error": f"Batch evaluation failed: {str(e)}"}

if __name__ == "__main__":
    # Test the evaluator
    q = "Explain overfitting."
    ans = "Overfitting is when a model learns the training data too well."
    rubric = "10 marks for correct definition."
    result = evaluate_single_answer(q, ans, rubric)
    print("Test Result:", result)