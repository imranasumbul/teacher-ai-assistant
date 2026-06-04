# dashboard_service.py
from datetime import datetime, timedelta, timezone
import json
from typing import Dict, List, Any, Optional
from sqlalchemy import func, desc

from db import (
    get_session,
    ConceptCatalog,
    ConceptMastery,
    MistakePattern,
    Interaction,
)

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

def get_class_engagement(subject: str) -> Dict[str, Any]:
    """
    Returns engagement data:
    1. Daily interaction counts for the last 30 days (heatmap/timeline)
    2. Breakdown of interaction types (doubt, feedback, assignment_evaluated)
    """
    session = get_session()
    try:
        # Determine 30 days ago
        now = utcnow()
        thirty_days_ago = now - timedelta(days=30)

        # 1. Timeline of interactions (daily count)
        # We query all interactions for this subject in the last 30 days
        interactions = (
            session.query(Interaction)
            .filter(
                Interaction.subject == subject,
                Interaction.created_at >= thirty_days_ago
            )
            .order_by(Interaction.created_at.asc())
            .all()
        )

        # Group by date in YYYY-MM-DD
        daily_counts = {}
        # Pre-populate all last 30 days with 0 to ensure no gaps
        for i in range(30):
            d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            daily_counts[d] = 0

        type_counts = {"doubt": 0, "feedback": 0, "assignment_evaluated": 0}

        for ix in interactions:
            # Format date (assuming timezone-aware or naive datetimes)
            date_str = ix.created_at.strftime("%Y-%m-%d")
            if date_str in daily_counts:
                daily_counts[date_str] += 1
            else:
                daily_counts[date_str] = 1

            # Count types
            t = ix.type
            if t in type_counts:
                type_counts[t] += 1
            else:
                type_counts[t] = type_counts.get(t, 0) + 1

        # Format timeline list sorted by date ascending
        timeline = [{"date": k, "count": v} for k, v in sorted(daily_counts.items())]

        return {
            "timeline": timeline,
            "types": type_counts,
            "total_interactions": len(interactions)
        }
    finally:
        session.close()

def get_concept_mastery_stats(subject: str, recent_only: bool = False) -> Dict[str, Any]:
    """
    Returns top 5 strongest and top 5 weakest concepts based on average mastery.
    If recent_only is True, filters to concepts updated in the last 7 days.
    """
    session = get_session()
    try:
        now = utcnow()
        seven_days_ago = now - timedelta(days=7)

        # Base query for concept mastery
        query = session.query(
            ConceptMastery.concept_id,
            func.avg(ConceptMastery.mastery).label("avg_mastery"),
            func.count(ConceptMastery.student_id).label("student_count")
        ).filter(ConceptMastery.subject == subject)

        if recent_only:
            # Only concepts updated recently (updated_at in the last 7 days)
            query = query.filter(ConceptMastery.updated_at >= seven_days_ago)

        # Group by concept_id
        stats = query.group_by(ConceptMastery.concept_id).all()

        if not stats:
            return {"strongest": [], "weakest": []}

        # Fetch concept labels
        concept_ids = [s[0] for s in stats]
        concepts = session.query(ConceptCatalog).filter(ConceptCatalog.concept_id.in_(concept_ids)).all()
        concept_map = {c.concept_id: c.label for c in concepts}

        # Build list of statistics
        mastery_list = []
        for s in stats:
            cid = s[0]
            avg = float(s[1]) if s[1] is not None else 0.5
            lbl = concept_map.get(cid, f"Concept #{cid}")
            mastery_list.append({
                "concept_id": cid,
                "label": lbl,
                "avg_mastery": round(avg, 3),
                "student_count": s[2]
            })

        # Sort by avg_mastery descending
        mastery_list.sort(key=lambda x: x["avg_mastery"], reverse=True)

        # Strongest are highest scores, weakest are lowest scores
        # We cap at 5
        strongest = mastery_list[:5]
        # Weakest are sorted ascending (lowest first)
        weakest = sorted(mastery_list, key=lambda x: x["avg_mastery"])[:5]

        return {
            "strongest": strongest,
            "weakest": weakest
        }
    finally:
        session.close()

def get_common_mistakes(subject: str, recent_only: bool = False) -> List[Dict[str, Any]]:
    """
    Returns a list of mistakes aggregated by concept and tag, sorted by total occurrences.
    If recent_only is True, filters to mistakes seen/updated in the last 7 days.
    """
    session = get_session()
    try:
        now = utcnow()
        seven_days_ago = now - timedelta(days=7)

        query = session.query(
            MistakePattern.concept_id,
            MistakePattern.mistake_tag,
            func.sum(MistakePattern.count).label("total_count")
        ).filter(MistakePattern.subject == subject)

        if recent_only:
            query = query.filter(MistakePattern.last_seen_at >= seven_days_ago)

        mistakes = (
            query.group_by(MistakePattern.concept_id, MistakePattern.mistake_tag)
            .order_by(desc("total_count"))
            .all()
        )

        if not mistakes:
            return []

        # Get labels
        concept_ids = list(set([m[0] for m in mistakes]))
        concepts = session.query(ConceptCatalog).filter(ConceptCatalog.concept_id.in_(concept_ids)).all()
        concept_map = {c.concept_id: c.label for c in concepts}

        result = []
        for m in mistakes:
            cid = m[0]
            tag = m[1]
            total = int(m[2]) if m[2] is not None else 0
            lbl = concept_map.get(cid, f"Concept #{cid}")
            result.append({
                "concept_id": cid,
                "concept_label": lbl,
                "mistake_tag": tag,
                "count": total
            })

        return result
    finally:
        session.close()

def search_concepts_by_subject(subject: str, search_query: str) -> List[Dict[str, Any]]:
    """
    Fuzzy search for concepts in a subject's catalog.
    """
    session = get_session()
    try:
        # Search matching label
        results = (
            session.query(ConceptCatalog)
            .filter(
                ConceptCatalog.subject == subject,
                ConceptCatalog.label.like(f"%{search_query}%")
            )
            .limit(10)
            .all()
        )
        return [{"concept_id": r.concept_id, "label": r.label} for r in results]
    finally:
        session.close()

def get_concept_drilldown(subject: str, concept_id: int) -> Dict[str, Any]:
    """
    Returns a comprehensive overview of a single concept:
    1. Average class mastery
    2. Specific mistake patterns for this concept
    3. Historical timeline of interactions associated with this concept
    """
    session = get_session()
    try:
        # Get concept label
        concept = session.query(ConceptCatalog).filter_by(concept_id=concept_id, subject=subject).first()
        if not concept:
            return {"error": "Concept not found"}

        # 1. Average class mastery
        mastery_stats = (
            session.query(
                func.avg(ConceptMastery.mastery).label("avg_mastery"),
                func.count(ConceptMastery.student_id).label("student_count")
            )
            .filter(
                ConceptMastery.concept_id == concept_id,
                ConceptMastery.subject == subject
            )
            .first()
        )
        avg_mastery = float(mastery_stats[0]) if mastery_stats and mastery_stats[0] is not None else 0.5
        student_count = int(mastery_stats[1]) if mastery_stats and mastery_stats[1] is not None else 0

        # 2. Mistake patterns
        mistakes = (
            session.query(
                MistakePattern.mistake_tag,
                func.sum(MistakePattern.count).label("total_count")
            )
            .filter(
                MistakePattern.concept_id == concept_id,
                MistakePattern.subject == subject
            )
            .group_by(MistakePattern.mistake_tag)
            .order_by(desc("total_count"))
            .all()
        )
        mistake_list = [{"tag": m[0], "count": int(m[1])} for m in mistakes]

        # 3. Historical timeline of interactions
        # Fetch all interactions for this subject
        all_interactions = (
            session.query(Interaction)
            .filter(Interaction.subject == subject)
            .order_by(Interaction.created_at.desc())
            .all()
        )

        # Filter in Python by checking if concept_id in concepts_json
        relevant_interactions = []
        for ix in all_interactions:
            try:
                cids = json.loads(ix.concepts_json)
                if isinstance(cids, list) and concept_id in cids:
                    # Get student name
                    student_name = ix.student.name if ix.student else ix.student_id
                    relevant_interactions.append({
                        "student_id": ix.student_id,
                        "student_name": student_name or ix.student_id,
                        "type": ix.type,
                        "question_text": ix.question_text,
                        "outcome": ix.outcome,
                        "created_at": ix.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    })
            except Exception:
                continue

        return {
            "concept_id": concept_id,
            "label": concept.label,
            "avg_mastery": round(avg_mastery, 3),
            "student_count": student_count,
            "mistakes": mistake_list,
            "interactions": relevant_interactions[:15] # limit to recent 15
        }
    finally:
        session.close()
