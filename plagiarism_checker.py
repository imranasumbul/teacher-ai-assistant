import json
import numpy as np

def check_plagiarism(new_embedding, past_submissions, threshold=0.85):
    """
    Check if a new embedding matches any past submissions above a certain threshold.
    
    Args:
        new_embedding (np.array or list): The embedding vector for the new answer.
        past_submissions (list of StudentSubmission): Past submissions from the DB.
        threshold (float): Cosine similarity threshold to flag as plagiarism.
        
    Returns:
        dict: {
            "is_plagiarized": bool,
            "matched_student_id": str or None,
            "similarity_score": float
        }
    """
    if not past_submissions:
        return {
            "is_plagiarized": False,
            "matched_student_id": None,
            "similarity_score": 0.0
        }
        
    new_vec = np.array(new_embedding)
    # Normalize the new vector for cosine similarity
    new_norm = np.linalg.norm(new_vec)
    if new_norm > 0:
        new_vec = new_vec / new_norm

    best_score = 0.0
    matched_student = None

    for sub in past_submissions:
        try:
            past_vec = np.array(json.loads(sub.embedding_json))
            past_norm = np.linalg.norm(past_vec)
            if past_norm > 0:
                past_vec = past_vec / past_norm
            
            # Cosine similarity for normalized vectors is just the dot product
            similarity = float(np.dot(new_vec, past_vec))
            
            if similarity > best_score:
                best_score = similarity
                matched_student = sub.student_id
                
        except Exception as e:
            print(f"Error parsing embedding for submission {sub.submission_id}: {e}")
            continue

    is_plagiarized = best_score >= threshold

    return {
        "is_plagiarized": is_plagiarized,
        "matched_student_id": matched_student if is_plagiarized else None,
        "similarity_score": round(best_score, 4)
    }
