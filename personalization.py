# personalization.py
from __future__ import annotations

import json
from typing import Dict, List, Tuple, Optional

from db import (
    get_session,
    Student,
    ConceptMastery,
    MistakePattern,
    Interaction,
)
from db import ConceptCatalog

def get_concept_labels(concept_ids: List[int]) -> Dict[int, str]:
    session = get_session()
    try:
        rows = session.query(ConceptCatalog).filter(
            ConceptCatalog.concept_id.in_(concept_ids)
        ).all()
        return {r.concept_id: r.label for r in rows}
    finally:
        session.close()

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
            if name and s.name != name:
                s.name = name
                updated = True
            if class_code and s.class_code != class_code:
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

    concept_ids = list(set(concept_ids))

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

    concept_ids = list(set(concept_ids))

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
    subject: str,
    avg_mastery: float,
    mastery_map: Dict[int, float],
    weak_concepts: List[Tuple[int, float]] | None,
    mistake_counts: Dict[int, int] | None,
    cold_start: bool = False
) -> str:
    # --- summarize confusion level ---
    mistake_counts = mistake_counts or {}
    total_mistakes = sum(int(v) for v in mistake_counts.values()) if mistake_counts else 0

    # small helper: list a few weak concepts ids (optional)
    weak_ids = [cid for cid, score in (weak_concepts or [])]
    label_map = get_concept_labels(weak_ids) if weak_ids else {}
    weak_labels = [label_map.get(cid, str(cid)) for cid in weak_ids]

    if cold_start:
        # Cold start: keep it simple but consistent with your /ask RULES
        return (
            f"Student learning profile for subject '{subject}': no prior data.\n"
            "Teaching style rules:\n"
            "- Use clear, simple language.\n"
            "- Answer in 2 short sentences.\n"
            "- Define ONE key term if helpful.\n"
            "- Do not use bullet points in the final answer.\n"
            "- Focus on conceptual clarity."
        )

    # ---------- mastery based adaptation ----------
    if avg_mastery < 0.4:
        base_style = (
            "Student has LOW mastery.\n"
            "Teaching style rules:\n"
            "- Use very simple language.\n"
            "- Explain step-by-step.\n"
            "- Prefer 3 to 5 short sentences.\n"
            "- Define key terms.\n"
            "- Avoid jargon.\n"
        )
    elif avg_mastery < 0.7:
        base_style = (
            "Student has MODERATE mastery.\n"
            "Teaching style rules:\n"
            "- Use clear explanation.\n"
            "- Prefer 2 to 4 short sentences.\n"
            "- Add a brief clarification if needed.\n"
        )
    else:
        base_style = (
            "Student has HIGH mastery.\n"
            "Teaching style rules:\n"
            "- Answer concisely.\n"
            "- Prefer 1 to 2 sentences.\n"
            "- Focus on the final idea.\n"
        )

    # ---------- weakness emphasis ----------
    if weak_concepts:
        weakness_note = (
            f"Student has weaker topics: {', '.join(weak_labels[:3])}.\n"
            "- Add ONE clarifying phrase to prevent confusion.\n"
        )
    else:
        weakness_note = ""

    # ---------- mistake awareness (LEVELS) ----------
    # This is the key upgrade: visible prompt changes as mistakes increase.
    if total_mistakes >= 4:
        mistake_note = (
            "Student has repeated confusion recently.\n"
            "- Start with: 'In simple words:'\n"
            "- Use 3 to 5 short sentences.\n"
            "- Include ONE tiny example.\n"
            "- End with a quick check question: 'Does this make sense?'\n"
        )
    elif total_mistakes >= 2:
        mistake_note = (
            "Student has been confused more than once.\n"
            "- Rephrase the core idea once in simpler words.\n"
            "- Include ONE tiny example.\n"
        )
    elif total_mistakes >= 1:
        mistake_note = (
            "Student was confused before.\n"
            "- Avoid ambiguous wording.\n"
            "- Add one short clarification.\n"
        )
    else:
        mistake_note = ""

    return (
        f"{base_style}"
        f"{weakness_note}"
        f"{mistake_note}"
        "Final answer formatting:\n"
        "- Do not use bullet points.\n"
        "- Keep sentences short.\n"
    )