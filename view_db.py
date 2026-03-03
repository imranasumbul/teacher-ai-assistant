from db import (
    init_db, 
    get_session,
    Student,
    ConceptCatalog,
    ConceptMastery,
    MistakePattern,
    Interaction,
)
init_db() 
session = get_session()

# -------------------------------------------------
print("\n================ STUDENTS ================\n")
students = session.query(Student).all()
if not students:
    print("No students found.")
for s in students:
    print(
        f"student_id={s.student_id}, "
        f"name={s.name}, "
        f"class_code={s.class_code}, "
        f"created_at={s.created_at}"
    )

# -------------------------------------------------
print("\n================ CONCEPT CATALOG ================\n")
concepts = session.query(ConceptCatalog).all()
if not concepts:
    print("No concepts found.")
for c in concepts:
    print(
        f"concept_id={c.concept_id}, "
        f"subject={c.subject}, "
        f"label={c.label}"
    )

# -------------------------------------------------
print("\n================ CONCEPT MASTERY ================\n")
mastery = session.query(ConceptMastery).all()
if not mastery:
    print("No mastery records found.")
for m in mastery:
    print(
        f"student_id={m.student_id}, "
        f"subject={m.subject}, "
        f"concept_id={m.concept_id}, "
        f"mastery={m.mastery}, "
        f"updated_at={m.updated_at}"
    )

# -------------------------------------------------
print("\n================ MISTAKE PATTERNS ================\n")
mistakes = session.query(MistakePattern).all()
if not mistakes:
    print("No mistake records found.")
for m in mistakes:
    print(
        f"student_id={m.student_id}, "
        f"subject={m.subject}, "
        f"concept_id={m.concept_id}, "
        f"tag={m.mistake_tag}, "
        f"count={m.count}, "
        f"last_seen={m.last_seen_at}"
    )

# -------------------------------------------------
print("\n================ INTERACTIONS ================\n")
interactions = session.query(Interaction).all()
if not interactions:
    print("No interactions found.")
for i in interactions:
    print(
        f"id={i.id}, "
        f"student={i.student_id}, "
        f"subject={i.subject}, "
        f"type={i.type}, "
        f"outcome={i.outcome}, "
        f"concepts={i.concepts_json}, "
        f"time={i.created_at}"
    )

# -------------------------------------------------
session.close()
print("\n✅ Done viewing database.\n")