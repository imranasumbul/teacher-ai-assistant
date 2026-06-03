import os
import json
import re

from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
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

from flask_login import LoginManager, login_user, logout_user, login_required, current_user

# DB init
from db import init_db, get_session, User, Question, Assignment, StudentSubmission
init_db()

# Plagiarism checker
from plagiarism_checker import check_plagiarism


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
from assignment_checker import evaluate_assignment_batch

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-this-in-prod")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login_page"

@login_manager.user_loader
def load_user(user_id):
    session = get_session()
    try:
        return session.get(User, user_id)
    finally:
        session.close()

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
    print("WARNING: GEMINI_API_KEY not set")
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

@app.route("/login_page")
def login_page():
    if current_user.is_authenticated:
        if current_user.role == "teacher":
            return redirect(url_for("teacher_notes"))
        else:
            return redirect(url_for("student_doubt"))
    return render_template("login.html")

@app.route("/student_doubt")
@login_required
def student_doubt():
    if current_user.role != "student":
        return redirect(url_for("home"))
    return render_template("student_doubt.html")

@app.route('/assignment_ques_rubrics_upload')
@login_required
def assignment_ques_rubrics_upload():
    if current_user.role != "teacher":
        return redirect(url_for("home"))
    return render_template('assignment_ques_rubrics_upload.html')

@app.route('/assignment_answer_upload')
@login_required
def assignment_answer_upload():

    db = get_session()
    assignments = db.query(Assignment).all()
    db.close()

    return render_template(
        'assignment_answer_upload.html',
        assignments=assignments
    )

@app.route("/teacher_notes")
@login_required
def teacher_notes():
    if current_user.role != "teacher":
        return redirect(url_for("home"))
    return render_template("teacher_notes.html")

# =========================
# Auth API Endpoints
# =========================
@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or request.form
    user_id = data.get("id", "").strip()
    name = data.get("name", "").strip()
    password = data.get("password", "").strip()
    role = data.get("role", "").strip().lower() # 'student' or 'teacher'
    
    if not user_id or not password or role not in ("student", "teacher"):
        return jsonify({"error": "Missing or invalid fields"}), 400

    session = get_session()
    try:
        # Check if ID already exists
        existing_user = session.get(User, user_id)
        if existing_user:
            return jsonify({"error": "User ID already taken"}), 409

        # Instantiate new User
        new_user = User(id=user_id, name=name, role=role)
        new_user.set_password(password)

        if role == "student":
            new_user.class_code = data.get("class_code", "").strip() or None
        elif role == "teacher":
            new_user.subject = data.get("subject", "").strip() or None

        session.add(new_user)
        session.commit()
        return jsonify({"message": f"Successfully registered {role}"}), 201
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or request.form
    user_id = data.get("id", "").strip()
    password = data.get("password", "").strip()

    if not user_id or not password:
        return jsonify({"error": "Credentials required"}), 400

    session = get_session()
    try:
        user = session.get(User, user_id)
        if not user or not user.check_password(password):
            return jsonify({"error": "Invalid User ID or Password"}), 401

        login_user(user) # Saves active session in client cookie
        
        # Guide frontend where to redirect based on role
        redirect_url = "/teacher_notes" if user.role == "teacher" else "/student_doubt"
        return jsonify({"message": "Login successful", "role": user.role, "redirect": redirect_url}), 200
    finally:
        session.close()

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))

# =========================
# Upload Teacher Notes (ONLY)
# =========================
@app.route("/upload_notes", methods=["POST"])
def upload_notes():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Only PDF and txt allowed"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    print(f"✅ Uploaded teacher notes: {filename}")

    try:
        extracted_text = extract_text(filepath)

        if not extracted_text:
            return jsonify({"error": "Could not extract text from PDF"}), 400

        chunks = chunk_text(extracted_text)

        if not chunks:
            return jsonify({"error": "Chunking failed"}), 400

        embedding_pairs = generate_embeddings(chunks)

        if not embedding_pairs:
            return jsonify({"error": "Embedding failed"}), 400

        save_to_vector_store(embedding_pairs, filename)

        return jsonify({
            "message": "Teacher notes uploaded successfully",
            "chunks": len(chunks)
        }), 200

    except Exception as e:
        print("❌ Upload processing error:", str(e))
        return jsonify({"error": str(e)}), 500


# =========================
# Evaluate Assignment
# =========================
@app.route("/evaluate_assignment", methods=["POST"])
@login_required
def evaluate_assignment_route():

    if current_user.role != "student":
        return jsonify({"error": "Access Denied"}), 403

    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]

    # FIXED
    assignment_id = request.form.get("assignment_id")

    subject = request.form.get("subject", "general").strip()

    if not assignment_id:
        return jsonify({"error": "assignment_id is required"}), 400

    db = get_session()
    try:
        existing_submission = db.query(StudentSubmission).filter_by(
            student_id=current_user.id,
            assignment_id=assignment_id
        ).first()
        if existing_submission:
            return jsonify({"error": "You have already submitted this assignment. Multiple submissions are not allowed."}), 403
    finally:
        db.close()

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Only PDF and txt allowed"}), 400

    filename = secure_filename(file.filename)

    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    file.save(filepath)

    print(f"✅ Uploaded assignment: {filename}")

    try:

        # Extract student answer text
        student_answer_text = extract_text(filepath)

        # Parse answers A1:, A2:, A3:
        answers_split = re.split(r"A\d+[:.)]?", student_answer_text)

        if len(answers_split) > 1:
            answers_split = answers_split[1:]

        answers = [a.strip() for a in answers_split if a.strip()]

        db = get_session()

        questions = db.query(Question).filter_by(
            assignment_id=assignment_id
        ).all()

        db.close()

        if not questions:
            return jsonify({
                "error": "No questions found for this assignment_id"
            }), 404

        student_id = current_user.id

        get_or_create_student(student_id)

        store = get_vector_store()

        assignment_data = {"questions": []}

        for i, q in enumerate(questions):

            ans = answers[i] if i < len(answers) else ""

            # RAG Retrieval
            context_str = ""

            embedding_pairs = generate_embeddings([q.question_text])

            if embedding_pairs:

                query_vector = embedding_pairs[0][0]

                rag_results = store.search(query_vector, k=3) if store else []

                retrieved_texts = [
                    r.get("chunk_text", "")
                    for r in rag_results
                ]

                context_str = "\n\n".join(
                    [t for t in retrieved_texts if t]
                ).strip()

            assignment_data["questions"].append({
                "id": i,
                "question": q.question_text,
                "rubric": q.rubric_text,
                "answer": ans,
                "context": context_str
            })

        # Batch Evaluation
        batch_res = evaluate_assignment_batch(assignment_data)

        if "error" in batch_res:
            return jsonify({
                "error": batch_res["error"]
            }), 500

        final_results = []

        for item in batch_res.get("results", []):

            q_id = item.get("id")

            if q_id is None or q_id >= len(questions) or q_id < 0:
                continue

            q = questions[q_id]

            ans = assignment_data["questions"][q_id]["answer"]

            concepts = item.get("concepts", [])

            concept_ids = []

            score = item.get("score", 0)

            max_score = item.get("max_score", 10)

            # Plagiarism check MUST happen before logging/mastery
            plagiarism_result = {
                "is_plagiarized": False,
                "matched_student_id": None,
                "similarity_score": 0.0
            }
            if ans.strip():
                ans_embeddings = generate_embeddings([ans])
                if ans_embeddings:
                    ans_vec = ans_embeddings[0][0]
                    # Fetch past submissions for this assignment and question
                    db = get_session()
                    try:
                        past_subs = db.query(StudentSubmission).filter(
                            StudentSubmission.assignment_id == assignment_id,
                            StudentSubmission.question_text == q.question_text,
                            StudentSubmission.student_id != student_id
                        ).all()
                        
                        plagiarism_result = check_plagiarism(ans_vec, past_subs)
                        
                        # Save current submission
                        new_sub = StudentSubmission(
                            assignment_id=assignment_id,
                            student_id=student_id,
                            question_text=q.question_text,
                            answer_text=ans,
                            embedding_json=json.dumps(ans_vec.tolist())
                        )
                        db.add(new_sub)
                        db.commit()
                    except Exception as pe:
                        print("Plagiarism check error:", pe)
                    finally:
                        db.close()

            # Deduct marks if plagiarized
            if plagiarism_result["is_plagiarized"]:
                score = 0
                if "missing_points" not in item:
                    item["missing_points"] = []
                item["missing_points"].append("Zero marks awarded due to plagiarism detected.")

            if concepts:

                concept_ids = get_or_create_concept_ids(
                    q.subject,
                    concepts
                )

                percent = score / max_score if max_score > 0 else 0

                feedback_val = (
                    "understood"
                    if percent >= 0.7
                    else "confused"
                )

                update_mastery(
                    student_id,
                    q.subject,
                    concept_ids,
                    feedback_val
                )

                mistakes = item.get("mistakes", [])

                for m in mistakes:

                    increment_mistake(
                        student_id,
                        q.subject,
                        concept_ids,
                        mistake_tag=m
                    )

            log_interaction(
                student_id=student_id,
                subject=q.subject,
                interaction_type="assignment_evaluated",
                question_text=q.question_text,
                concept_ids=concept_ids,
                outcome=f"scored_{score}_{max_score}"
            )

            final_results.append({
                "question": q.question_text,
                "answer": ans,
                "score": score,
                "max_score": max_score,
                "concepts": concepts,
                "mistakes": item.get("mistakes", []),
                "feedback": {
                    "correct_points": item.get("correct_points", []),
                    "missing_points": item.get("missing_points", []),
                    "improvements": item.get("improvements", [])
                },
                "plagiarism": plagiarism_result
            })

        return jsonify(final_results), 200

    except Exception as e:

        print("❌ Evaluation error:", str(e))

        return jsonify({
            "error": str(e)
        }), 500



# =========================
# Ask Doubt (RAG + Personalization)
# =========================
@app.route("/ask", methods=["POST"])
@login_required
def ask_question():
    if current_user.role != "student":
        return jsonify({"error": "Access Denied"}), 403
    if gemini_client is None:
        return jsonify({"error": "Gemini not configured"}), 500

    data = request.get_json(silent=True) or {}
    debug = bool(data.get("debug", False))

    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Question required"}), 400

    student_id = current_user.id
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
@login_required
def feedback():
    if current_user.role != "student":
        return jsonify({"error": "Access Denied"}), 403
    data = request.get_json(silent=True) or {}

    student_id = current_user.id
    subject = (data.get("subject") or "general").strip()
    question_text = (data.get("question_text") or "").strip()

    feedback_value = (data.get("feedback") or "").strip().lower()  # understood / confused
    concept_ids = data.get("concept_ids")

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

@app.route("/upload_assignment_pdf", methods=["POST"])
@login_required
def upload_assignment_pdf():

    if current_user.role != "teacher":
        return jsonify({"error": "Access Denied"}), 403

    if "assignment_file" not in request.files or "rubric_file" not in request.files:
        return jsonify({"error": "Both assignment and rubric files required"}), 400

    assignment_file = request.files["assignment_file"]
    rubric_file = request.files["rubric_file"]

    subject = request.form.get("subject")

    assignment_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        assignment_file.filename
    )

    rubric_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        rubric_file.filename
    )

    assignment_file.save(assignment_path)
    rubric_file.save(rubric_path)

    try:

        assignment_text = extract_text(assignment_path)
        rubric_text = extract_text(rubric_path)

        questions_split = re.split(r"Q\d+[:.)]?", assignment_text)

        if len(questions_split) > 1:
            questions_split = questions_split[1:]

        questions = [q.strip() for q in questions_split if q.strip()]

        rubric_parts_split = re.split(r"Q\d+[:.)]?", rubric_text)

        if len(rubric_parts_split) > 1:
            rubric_parts_split = rubric_parts_split[1:]

        rubric_parts = [r.strip() for r in rubric_parts_split if r.strip()]

        db = get_session()

        duplicate_by_title = db.query(Assignment).filter_by(
            title=assignment_file.filename
        ).first()

        if duplicate_by_title:
            db.close()
            return jsonify({
                "error": "Assignment already exists with this title."
            }), 400

        # FIXED DUPLICATE CHECK
        all_assignments = db.query(Assignment).all()

        for existing_assignment in all_assignments:

            existing_qs = db.query(Question).filter_by(
                assignment_id=existing_assignment.assignment_id
            ).all()

            existing_questions = [
                q.question_text for q in existing_qs
            ]

            if existing_questions and existing_questions == questions:
                db.close()

                return jsonify({
                    "error": "Assignment already exists with these exact questions."
                }), 400

        assignment = Assignment(
            subject=subject,
            title=assignment_file.filename
        )

        db.add(assignment)
        db.commit()

        assignment_id = assignment.assignment_id

        saved_questions = []

        for i, q in enumerate(questions):

            rubric_for_q = rubric_parts[i] if i < len(rubric_parts) else ""

            new_q = Question(
                assignment_id=assignment_id,
                subject=subject,
                question_text=q,
                rubric_text=rubric_for_q,
                concept_ids_json="[]"
            )

            db.add(new_q)
            saved_questions.append(q)

        db.commit()
        db.close()

        return jsonify({
            "message": "Assignment stored successfully",
            "assignment_id": assignment_id,
            "questions": saved_questions,
            "questions_stored": len(saved_questions)
        }), 200

    except Exception as e:
        print("❌ Assignment Upload Error:", str(e))
        return jsonify({"error": str(e)}), 500



# =========================
if __name__ == "__main__":
    app.run(debug=True)