import os
import json
import re

from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Load env variables
load_dotenv()

from extractor import extract_text
from chunker import chunk_text
from embedder import generate_embeddings
from vector_store import save_to_vector_store, get_vector_store

# NEW Gemini SDK
from google import genai

# DB init
from db import init_db
init_db()

# Concept catalog service
from concept_service import get_or_create_concept_ids, identify_concepts_from_vector

from personalization import (
    get_or_create_student,
    log_interaction,
    get_mastery_map,
    get_mistake_counts,
    update_mastery,
    increment_mistake,
    build_personalization_instruction,
)

# Assignment checker
from assignment_checker import evaluate_assignment

app = Flask(__name__)

# =========================
# Helpers
# =========================
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

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# =========================
# Configuration
# =========================
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf", "txt"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Gemini API
GOOGLE_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GOOGLE_API_KEY:
    print("❌ WARNING: GEMINI_API_KEY not set")
    gemini_client = None
else:
    gemini_client = genai.Client(api_key=GOOGLE_API_KEY)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# =========================
# Routes (Pages)
# =========================
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/student_doubt")
def student_doubt():
    return render_template("student_doubt.html")

@app.route("/assignment_upload")
def assignment_upload():
    return render_template("assignment_upload.html")

@app.route("/teacher_notes")
def teacher_notes():
    return render_template("teacher_notes.html")

# =========================
# Upload Teacher Notes with Evaluation Rules
# =========================
@app.route("/upload_notes", methods=["POST"])
def upload_notes():
    if "file" not in request.files or "evaluation_rules_file" not in request.files:
        return jsonify({"error": "Missing notes or rubric file"}), 400

    file = request.files["file"]
    rules_file_upload = request.files["evaluation_rules_file"]

    if file.filename == "" or rules_file_upload.filename == "":
        return jsonify({"error": "No file selected for notes or rubric"}), 400

    if not allowed_file(file.filename) or not allowed_file(rules_file_upload.filename):
        return jsonify({"error": "Only PDF and txt allowed for both files"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    rules_filename = secure_filename(rules_file_upload.filename)
    rules_filepath = os.path.join(app.config["UPLOAD_FOLDER"], rules_filename)
    rules_file_upload.save(rules_filepath)

    print(f"✅ Uploaded teacher notes: {filename} and rubric: {rules_filename}")

    try:
        # Process and extract teacher notes
        extracted_text = extract_text(filepath)
        chunks = chunk_text(extracted_text)
        embedding_pairs = generate_embeddings(chunks)
        save_to_vector_store(embedding_pairs, filename)
        
        # Process and extract evaluation rules
        evaluation_rules = extract_text(rules_filepath)

        # Store evaluation rules as a text file for the assignment checker
        rules_dest_file = os.path.join(app.config["UPLOAD_FOLDER"], "evaluation_rules.txt")
        with open(rules_dest_file, "w", encoding="utf-8") as f:
            f.write(evaluation_rules)

        # Clean up the original uploaded rubric file since we extracted its text
        if os.path.exists(rules_filepath):
            os.remove(rules_filepath)

        return jsonify({
            "message": "Teacher notes and evaluation rules uploaded successfully",
            "chunks": len(chunks),
            "rules_length": len(evaluation_rules)
        }), 200

    except Exception as e:
        print("❌ Upload processing error:", e)
        return jsonify({"error": str(e)}), 500

# =========================
# Evaluate Assignment
# =========================
@app.route("/evaluate_assignment", methods=["POST"])
def evaluate_assignment_route():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    topic = request.form.get("topic", "").strip()
    subject = request.form.get("subject", "general").strip()

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Only PDF and txt allowed"}), 400

    if not topic:
        return jsonify({"error": "Topic is required"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    print(f"✅ Uploaded assignment: {filename}")

    try:
        # Extract student answer text
        student_answer_text = extract_text(filepath)

        # Load evaluation rules
        rules_file = os.path.join(app.config["UPLOAD_FOLDER"], "evaluation_rules.txt")
        if not os.path.exists(rules_file):
            return jsonify({"error": "Evaluation rules not found. Please upload teacher notes first."}), 400

        with open(rules_file, "r", encoding="utf-8") as f:
            evaluation_rules_text = f.read()

        # Evaluate assignment
        result = evaluate_assignment(student_answer_text, topic, subject, evaluation_rules_text)

        if "error" in result:
            return jsonify(result), 400

        return jsonify(result), 200

    except Exception as e:
        print("❌ Evaluation error:", e)
        return jsonify({"error": str(e)}), 500

# =========================
# Ask Doubt (RAG + Personalization)
# =========================
@app.route("/ask", methods=["POST"])
def ask_question():
    if gemini_client is None:
        return jsonify({"error": "Gemini not configured"}), 500

    data = request.get_json(silent=True) or {}
    debug = bool(data.get("debug", False))

    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Question required"}), 400

    student_id = (data.get("student_id") or "S1").strip()
    subject = (data.get("subject") or "general").strip()

    print(f"\n❓ Question: {question} | subject={subject} | student_id={student_id} | debug={debug}")

    try:
        # 0) Ensure student exists
        get_or_create_student(student_id)

        # Subject-level (fallback) stats used for THIS call
        subject_mastery_map = get_mastery_map(student_id, subject) or {}
        subject_mistake_counts = get_mistake_counts(student_id, subject) or {}

        # 1) RAG retrieval
        embedding_pairs = generate_embeddings([question])
        if not embedding_pairs:
            return jsonify({"error": "Failed to generate embedding"}), 500

        query_vector = embedding_pairs[0][0]
        store = get_vector_store()
        results = store.search(query_vector, k=5) if store else []

        retrieved_texts = [r.get("chunk_text", "") for r in results]
        context_str = "\n\n".join([t for t in retrieved_texts if t]).strip()

        # ✅ Guard: if nothing retrieved, don't call Gemini
        if not context_str:
            concept_labels = ["out_of_syllabus"]
            concept_ids = get_or_create_concept_ids(subject, concept_labels)

            # Log interaction (still useful)
            log_interaction(
                student_id=student_id,
                subject=subject,
                interaction_type="doubt",
                question_text=question,
                concept_ids=concept_ids,
                outcome="not_in_syllabus_no_context",
            )

            payload = {
                "answer": "Not in syllabus",
                "concept_labels": concept_labels,
                "concept_ids": concept_ids,
            }

            if debug:
                payload["debug"] = {
                    "reason": "no_context_retrieved",
                    "retrieved_chunks_preview": [t[:120] for t in retrieved_texts[:3]],
                }

            return jsonify(payload), 200

        # 2) Personalization style (Targeted Concept or Subject fallback)
        # PRE-FLIGHT CONCEPT MATCHING: Identify exact concepts from question embedding
        guessed_concept_ids = identify_concepts_from_vector(subject, query_vector, top_k=2)

        if guessed_concept_ids:
            # We found specific concepts! Load THEIR exact mastery instead of averages.
            mastery_map = get_mastery_map(student_id, subject, guessed_concept_ids) or {}
            mistake_counts = get_mistake_counts(student_id, subject, guessed_concept_ids) or {}
            cold_start = False # because we are pulling known concepts even if they just default to 0.5
        else:
            # Fallback to subject-level averages
            mastery_map = subject_mastery_map
            mistake_counts = subject_mistake_counts
            cold_start = not mastery_map and not mistake_counts

        if cold_start:
            avg_mastery = 0.5
            weak_concepts = []
        else:
            scores = [float(v) for v in mastery_map.values() if isinstance(v, (int, float))]
            avg_mastery = sum(scores) / len(scores) if scores else 0.5
            weak_concepts =[(cid, score)for cid, score in mastery_map.items()if score < 0.5]


        style_instruction = build_personalization_instruction(
                    subject=subject,
                    avg_mastery=avg_mastery,
                    mastery_map=mastery_map,
                    weak_concepts=weak_concepts,
                    mistake_counts=mistake_counts,
                    cold_start=cold_start,
                )

        # 3) ONE Gemini call: answer + concepts (JSON)
        combined_prompt = f"""
You are a teacher assistant.

{style_instruction}

TASK:
1) Answer the student's question using ONLY the teacher notes.
2) Extract 2 to 5 LEARNING CONCEPT labels (core syllabus topics) relevant to the question.

STUDENT STATE:
- cold_start = {cold_start}
- avg_mastery = {avg_mastery}
- mistake_counts = {mistake_counts}

RULES:
- If answer is not found in the notes, answer must be exactly: "Not in syllabus"
- If answer is "Not in syllabus", set concept_labels = ["out_of_syllabus"].

Concept labels must be noun-phrase learning topics (algorithms/theories/models/techniques).
Do NOT output: definition, mechanism, approach, components, applications, examples.

Return ONLY valid JSON in this exact format:
{{
  "answer": "...",
  "concept_labels": ["...", "..."]
}}

TEACHER NOTES:
{context_str}

STUDENT QUESTION:
{question}
""".strip()

        resp = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=combined_prompt,
        )

        parsed = parse_json_from_text(resp.text)

        if not parsed:
            answer = (resp.text or "").strip()
            concept_labels = ["general"]
        else:
            answer = (parsed.get("answer") or "").strip()
            concept_labels = parsed.get("concept_labels") or ["general"]
            if not isinstance(concept_labels, list):
                concept_labels = ["general"]

        # 4) Enforce out-of-syllabus
        if answer.strip().lower() == "not in syllabus":
            concept_labels = ["out_of_syllabus"]

        # 5) Map labels -> concept_ids
        concept_ids = get_or_create_concept_ids(subject, concept_labels)

        # Concept-specific stats (these affect NEXT time these concepts appear)
        concept_mastery_map = get_mastery_map(student_id, subject, concept_ids) or {}
        concept_mistake_counts = get_mistake_counts(student_id, subject, concept_ids) or {}

        # 6) Log interaction
        log_interaction(
            student_id=student_id,
            subject=subject,
            interaction_type="doubt",
            question_text=question,
            concept_ids=concept_ids,
            outcome="answered",
        )

        payload = {
            "answer": answer,
            "concept_labels": concept_labels,
            "concept_ids": concept_ids,
        }

        if debug:
            payload["debug"] = {
                "cold_start": cold_start,
                "avg_mastery_subject": avg_mastery,
                "weak_concepts_subject": weak_concepts,
                "subject_mastery_map_used": subject_mastery_map,
                "subject_mistake_counts_used": subject_mistake_counts,
                "concept_mastery_map_next_time": concept_mastery_map,
                "concept_mistake_counts_next_time": concept_mistake_counts,
                "style_instruction_used": style_instruction[:800],
                "retrieved_chunks_preview": [t[:120] for t in retrieved_texts[:3]],
            }

        return jsonify(payload), 200

    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"error": str(e)}), 500

# =========================
# Feedback Route (Mastery update)
# =========================
@app.route("/feedback", methods=["POST"])
def feedback():
    data = request.get_json(silent=True) or {}

    student_id = (data.get("student_id") or "").strip()
    subject = (data.get("subject") or "general").strip()
    question_text = (data.get("question_text") or "").strip()

    feedback_value = (data.get("feedback") or "").strip().lower()  # understood / confused
    concept_ids = data.get("concept_ids")

    if not student_id:
        return jsonify({"error": "student_id required"}), 400

    if feedback_value not in ("understood", "confused"):
        return jsonify({"error": "feedback must be 'understood' or 'confused'"}), 400

    if not isinstance(concept_ids, list) or not all(isinstance(x, int) for x in concept_ids):
        return jsonify({"error": "concept_ids must be a list of integers"}), 400

    get_or_create_student(student_id)

    update_mastery(student_id, subject, concept_ids, feedback_value)

    if feedback_value == "confused":
        increment_mistake(student_id, subject, concept_ids, mistake_tag="concept_unclear")

    log_interaction(
        student_id=student_id,
        subject=subject,
        interaction_type="feedback",
        question_text=question_text or "(feedback)",
        concept_ids=concept_ids,
        outcome=feedback_value,
    )

    return jsonify({
        "message": "✅ Feedback saved",
        "student_id": student_id,
        "subject": subject,
        "concept_ids": concept_ids,
        "feedback": feedback_value
    }), 200

# =========================
if __name__ == "__main__":
    app.run(debug=True)