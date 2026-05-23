from db import (
    init_db,
    get_session,
    Student,
    ConceptCatalog,
    ConceptMastery,
    MistakePattern,
    Interaction,
    Assignment,
    Question
)

import os

# Init DB
init_db()
session = get_session()

print("\n📁 DB FILE LOCATION:")
print(os.path.abspath("app.db"))

# =====================================================
# STUDENTS
# =====================================================
print("\n================ STUDENTS ================\n")
students = session.query(Student).all()

if not students:
    print("No students found.")

for s in students:
    print(
        f"id={s.student_id}, "
        f"name={s.name}, "
        f"class={s.class_code}, "
        f"created={s.created_at}"
    )

# =====================================================
# CONCEPT CATALOG
# =====================================================
print("\n================ CONCEPT CATALOG ================\n")
concepts = session.query(ConceptCatalog).all()

if not concepts:
    print("No concepts found.")

for c in concepts:
    print(
        f"id={c.concept_id}, "
        f"subject={c.subject}, "
        f"label={c.label}"
    )

# =====================================================
# CONCEPT MASTERY
# =====================================================
print("\n================ CONCEPT MASTERY ================\n")
mastery = session.query(ConceptMastery).all()

if not mastery:
    print("No mastery records found.")

for m in mastery:
    print(
        f"student={m.student_id}, "
        f"subject={m.subject}, "
        f"concept_id={m.concept_id}, "
        f"mastery={m.mastery}"
    )

# =====================================================
# MISTAKE PATTERNS
# =====================================================
print("\n================ MISTAKE PATTERNS ================\n")
mistakes = session.query(MistakePattern).all()

if not mistakes:
    print("No mistake records found.")

for m in mistakes:
    print(
        f"student={m.student_id}, "
        f"subject={m.subject}, "
        f"concept_id={m.concept_id}, "
        f"tag={m.mistake_tag}, "
        f"count={m.count}"
    )

# =====================================================
# INTERACTIONS
# =====================================================
print("\n================ INTERACTIONS ================\n")
interactions = session.query(Interaction).all()

if not interactions:
    print("No interactions found.")

for i in interactions:
    print(
        f"id={i.id}, "
        f"student={i.student_id}, "
        f"type={i.type}, "
        f"subject={i.subject}, "
        f"outcome={i.outcome}"
    )

# =====================================================
# ASSIGNMENTS
# =====================================================
print("\n================ ASSIGNMENTS ================\n")
assignments = session.query(Assignment).all()

if not assignments:
    print("No assignments found.")

for a in assignments:
    print(
        f"id={a.assignment_id}, "
        f"subject={a.subject}, "
        f"title={a.title}"
    )

# =====================================================
# QUESTIONS
# =====================================================
print("\n================ QUESTIONS ================\n")
questions = session.query(Question).all()

if not questions:
    print("No questions found.")

for q in questions:
    print(
        f"id={q.question_id}, "
        f"assignment_id={q.assignment_id}, "
        f"text={q.question_text}\n"
        f"rubric={q.rubric_text}\n"
    )

# =====================================================
# ASSIGNMENT → QUESTIONS (IMPORTANT VIEW)
# =====================================================
print("\n================ ASSIGNMENT → QUESTIONS ================\n")

for a in assignments:
    print(f"\nAssignment {a.assignment_id}: {a.title}")

    qs = session.query(Question).filter_by(assignment_id=a.assignment_id).all()

    if not qs:
        print("   No questions found.")
    else:
        for i, q in enumerate(qs, start=1):
            print(f"   Q{i}: {q.question_text}")
            print(f"       Rubric: {q.rubric_text}\n")

# =====================================================
session.close()

print("\n✅ Done viewing database.\n")