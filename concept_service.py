# concept_service.py
from __future__ import annotations

import json
import re
from typing import List, Optional, Tuple

import numpy as np

from db import get_session, ConceptCatalog
from embedder import generate_embeddings

MAX_CONCEPTS = 20
SIM_THRESHOLD = 0.92  # raise => merges more strictly, lower => creates fewer distinct concepts


def _normalize_label(label: str) -> str:
    s = (label or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("–", "-").replace("—", "-")
    return s


def _normalize_subject(subject: str) -> str:
    s = (subject or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s or "general"


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _embed_text(text: str) -> Optional[np.ndarray]:
    pairs = generate_embeddings([text])
    if not pairs:
        return None
    return pairs[0][0]


def get_or_create_concept_ids(subject: str, concept_labels: List[str]) -> List[int]:
    """
    Subject-scoped concept catalog:
    - Same label can exist in different subjects.
    Returns concept_ids (ints).
    """
    subject_norm = _normalize_subject(subject)

    concept_labels = [c for c in (concept_labels or []) if isinstance(c, str) and c.strip()]
    if not concept_labels:
        concept_labels = ["general"]

    # limit + normalize labels
    concept_labels = [_normalize_label(x) for x in concept_labels][:MAX_CONCEPTS]

    session = get_session()
    try:
        # IMPORTANT: only compare/merge within the SAME subject
        existing = (
            session.query(ConceptCatalog)
            .filter(ConceptCatalog.subject == subject_norm)
            .all()
        )

        existing_items: List[Tuple[int, str, Optional[np.ndarray]]] = []
        for c in existing:
            emb = None
            if c.embedding_json:
                try:
                    emb = np.array(json.loads(c.embedding_json), dtype=np.float32)
                except Exception:
                    emb = None
            existing_items.append((c.concept_id, c.label, emb))

        concept_ids: List[int] = []

        for label in concept_labels:
            vec = _embed_text(label)

            best_id = None
            best_sim = -1.0

            if vec is not None:
                for cid, _, existing_vec in existing_items:
                    if existing_vec is None:
                        continue
                    sim = _cosine_sim(vec, existing_vec)
                    if sim > best_sim:
                        best_sim = sim
                        best_id = cid

            # merge within subject if similar enough
            if best_id is not None and best_sim >= SIM_THRESHOLD:
                concept_ids.append(best_id)
                continue

            emb_json = json.dumps(vec.tolist()) if vec is not None else None
            new_concept = ConceptCatalog(subject=subject_norm, label=label, embedding_json=emb_json)
            session.add(new_concept)
            session.commit()

            new_id = new_concept.concept_id
            existing_items.append((new_id, label, vec))
            concept_ids.append(new_id)

        return concept_ids
    finally:
        session.close()


def identify_concepts_from_vector(subject: str, query_vector: np.ndarray, top_k: int = 2) -> List[int]:
    """Find the most similar existing concept IDs for a given vector."""
    subject_norm = _normalize_subject(subject)
    session = get_session()
    try:
        existing = (
            session.query(ConceptCatalog)
            .filter(ConceptCatalog.subject == subject_norm)
            .all()
        )
        
        scored_concepts = []
        for c in existing:
            if not c.embedding_json:
                continue
            try:
                emb = np.array(json.loads(c.embedding_json), dtype=np.float32)
                sim = _cosine_sim(query_vector, emb)
                scored_concepts.append((sim, c.concept_id))
            except Exception:
                pass
                
        # sort by similarity descending
        scored_concepts.sort(key=lambda x: x[0], reverse=True)
        
        # take top_k that are above a reasonable threshold for matching sentences to concept labels
        return [cid for sim, cid in scored_concepts if sim > 0.4][:top_k]
    except Exception as e:
        print(f"Error matching concepts from vector: {e}")
        return []
    finally:
        session.close()