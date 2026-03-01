# personalization.py
from __future__ import annotations

import json
from typing import Dict, List, Tuple

from db import (
    get_session,
    Student,
    ConceptMastery,
    MistakePattern,
    Interaction,
)

DEFAULT_MASTERY = 0.5
DELTA_UNDERSTOOD = 0.08
DELTA_CONFUSED = -0.08


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def get_or_create_student(student_id: str, name: str | None = None, class_code: str | None = None) -> Student:
    session = get_session()
    try:
        s = session.query(Student).filter(Student.student_id == student_id).first()
        if s:
            # optional update if passed
            updated = False
            if name and not s.name:
                s.name = name
                updated = True
            if class_code and not s.class_code:
                s.class_code = class_code
                updated = True
            if updated:
                session.commit()
            return s

        s = Student(student_id=student_id, name=name, class_code=class_code)
        session.add(s)
        session.commit()
        return s
    finally:
        session.close()


def log_interaction(
    student_id: str,
    subject: str,
    interaction_type: str,   # "doubt" or "feedback"
    question_text: str,
    concept_ids: List[int],
    outcome: str,            # "answered" / "understood" / "confused"
) -> None:
    session = get_session()
    try:
        row = Interaction(
            student_id=student_id,
            subject=subject,
            type=interaction_type,
            question_text=question_text,
            concepts_json=json.dumps(concept_ids),
            outcome=outcome,
        )
        session.add(row)
        session.commit()
    finally:
        session.close()

from typing import Optional

def get_mastery_map(student_id: str, subject: str, concept_ids: Optional[List[int]] = None) -> Dict[int, float]:
    """
    If concept_ids is provided: returns mastery for those concepts (missing => DEFAULT_MASTERY).
    If concept_ids is None: returns mastery for ALL concepts this student has for this subject.
    """
    session = get_session()
    try:
        q = (
            session.query(ConceptMastery)
            .filter(
                ConceptMastery.student_id == student_id,
                ConceptMastery.subject == subject,
            )
        )

        # If caller wants only specific concepts
        if concept_ids is not None:
            mastery_map = {cid: DEFAULT_MASTERY for cid in concept_ids}
            if not concept_ids:
                return mastery_map

            rows = q.filter(ConceptMastery.concept_id.in_(concept_ids)).all()
            for r in rows:
                mastery_map[int(r.concept_id)] = float(r.mastery)
            return mastery_map

        # If caller wants subject-wide mastery map (only what exists in DB)
        rows = q.all()
        return {int(r.concept_id): float(r.mastery) for r in rows}
    finally:
        session.close()
from typing import Optional

def get_mistake_counts(
    student_id: str,
    subject: str,
    concept_ids: Optional[List[int]] = None,
    tag: str = "concept_unclear"
) -> Dict[int, int]:
    """
    If concept_ids is provided: returns counts for those concepts (missing => 0).
    If concept_ids is None: returns counts for ALL concepts with this tag for this subject.
    """
    session = get_session()
    try:
        q = (
            session.query(MistakePattern)
            .filter(
                MistakePattern.student_id == student_id,
                MistakePattern.subject == subject,
                MistakePattern.mistake_tag == tag,
            )
        )

        if concept_ids is not None:
            counts = {cid: 0 for cid in concept_ids}
            if not concept_ids:
                return counts

            rows = q.filter(MistakePattern.concept_id.in_(concept_ids)).all()
            for r in rows:
                counts[int(r.concept_id)] = int(r.count)
            return counts

        rows = q.all()
        return {int(r.concept_id): int(r.count) for r in rows}
    finally:
        session.close()
        
def update_mastery(student_id: str, subject: str, concept_ids: List[int], feedback: str) -> None:
    """
    feedback: "understood" or "confused"
    Updates mastery rows (upsert).
    """
    if not concept_ids:
        return

    delta = DELTA_UNDERSTOOD if feedback == "understood" else DELTA_CONFUSED

    session = get_session()
    try:
        for cid in concept_ids:
            row = (
                session.query(ConceptMastery)
                .filter(
                    ConceptMastery.student_id == student_id,
                    ConceptMastery.subject == subject,
                    ConceptMastery.concept_id == cid,
                )
                .first()
            )
            if row is None:
                row = ConceptMastery(
                    student_id=student_id,
                    subject=subject,
                    concept_id=cid,
                    mastery=clamp01(DEFAULT_MASTERY + delta),
                )
                session.add(row)
            else:
                row.mastery = clamp01(float(row.mastery) + delta)

        session.commit()
    finally:
        session.close()


def increment_mistake(
    student_id: str,
    subject: str,
    concept_ids: List[int],
    mistake_tag: str = "concept_unclear",
) -> None:
    """
    Upsert and count++ for MistakePattern.
    """
    if not concept_ids:
        return

    session = get_session()
    try:
        for cid in concept_ids:
            row = (
                session.query(MistakePattern)
                .filter(
                    MistakePattern.student_id == student_id,
                    MistakePattern.subject == subject,
                    MistakePattern.concept_id == cid,
                    MistakePattern.mistake_tag == mistake_tag,
                )
                .first()
            )
            if row is None:
                row = MistakePattern(
                    student_id=student_id,
                    subject=subject,
                    concept_id=cid,
                    mistake_tag=mistake_tag,
                    count=1,
                )
                session.add(row)
            else:
                row.count = int(row.count) + 1

        session.commit()
    finally:
        session.close()

def build_personalization_instruction(
    subject,
    avg_mastery,
    mastery_map,
    weak_concepts,
    mistake_counts,
    cold_start=False
):
    if cold_start:
        return (
            f"Student learning profile for subject '{subject}': no prior data.\n"
            "Teaching style:\n"
            "- Use clear and simple language.\n"
            "- Answer in 2 to 3 short sentences.\n"
            "- Define one key term if helpful.\n"
            "- No bullet points.\n"
            "- Focus on conceptual clarity."
        )

    # ---------- mastery based adaptation ----------
    if avg_mastery < 0.4:
        base_style = (
            "Student has LOW mastery.\n"
            "- Use very simple language.\n"
            "- Explain step-by-step.\n"
            "- Answer in 3 to 4 sentences.\n"
            "- Define key terms.\n"
            "- Avoid jargon.\n"
        )
    elif avg_mastery < 0.7:
        base_style = (
            "Student has MODERATE mastery.\n"
            "- Use clear explanation.\n"
            "- Answer in 2 to 3 sentences.\n"
            "- Include brief clarification if needed.\n"
        )
    else:
        base_style = (
            "Student has HIGH mastery.\n"
            "- Answer concisely.\n"
            "- 1 or 2 sentences maximum.\n"
            "- Focus on final idea, minimal explanation.\n"
        )

    # ---------- weakness emphasis ----------
    if weak_concepts:
        weakness_note = (
            "Student has weak understanding in some topics.\n"
            "- Add one clarifying phrase to prevent confusion.\n"
        )
    else:
        weakness_note = ""

    # ---------- mistake awareness ----------
    if mistake_counts:
        mistake_note = (
            "Student previously made mistakes in this subject.\n"
            "- Avoid ambiguous wording.\n"
            "- Emphasize correctness clearly.\n"
        )
    else:
        mistake_note = ""

    return f"Teaching style rules:\n{base_style}{weakness_note}{mistake_note}- No bullet points."