# seed_dashboard_data.py
import os
import json
import random
from datetime import datetime, timedelta, timezone

from db import (
    init_db,
    get_session,
    User,
    ConceptCatalog,
    ConceptMastery,
    MistakePattern,
    Interaction,
)

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

def seed_data():
    print("Initializing Database...")
    init_db()
    session = get_session()
    
    try:
        # Clear existing data to ensure clean seeding
        print("Clearing existing tables...")
        session.query(Interaction).delete()
        session.query(MistakePattern).delete()
        session.query(ConceptMastery).delete()
        session.query(ConceptCatalog).delete()
        session.query(User).delete()
        session.commit()
        
        # 1. Create Teacher
        print("Creating Teacher...")
        teacher = User(
            id="teacher1",
            name="Teacher Alice",
            role="teacher",
            subject="Machine Learning"
        )
        teacher.set_password("password123")
        session.add(teacher)
        
        # 2. Create Students
        print("Creating Students...")
        students_info = [
            ("S1", "John Doe"),
            ("S2", "Jane Smith"),
            ("S3", "Bob Johnson"),
            ("S4", "Alice Williams"),
            ("S5", "Charlie Brown")
        ]
        students = []
        for sid, name in students_info:
            student = User(
                id=sid,
                name=name,
                role="student",
                class_code="ML-101"
            )
            student.set_password("password123")
            session.add(student)
            students.append(student)
            
        session.commit()
        
        # 3. Create Concept Catalog for Machine Learning
        print("Creating Machine Learning concepts...")
        concepts_labels = [
            "Overfitting",
            "Supervised Learning",
            "Classification",
            "Decision Trees",
            "Neural Networks",
            "Gradient Descent",
            "Feature Engineering",
            "Regularization",
            "Unsupervised Learning"
        ]
        
        concepts = []
        for label in concepts_labels:
            concept = ConceptCatalog(
                subject="Machine Learning",
                label=label
            )
            session.add(concept)
            concepts.append(concept)
            
        session.commit()
        
        # Re-query concepts to get their generated concept_ids
        concepts = session.query(ConceptCatalog).filter_by(subject="Machine Learning").all()
        
        # 4. Generate Concept Mastery records
        print("Seeding Concept Mastery...")
        # We want to create different average mastery scores for each concept.
        # Strongest: Supervised Learning (avg ~0.9), Feature Engineering (avg ~0.85)
        # Weakest: Overfitting (avg ~0.35), Gradient Descent (avg ~0.4), Regularization (avg ~0.45)
        # Let's seed varying levels of mastery for all 5 students.
        
        mastery_presets = {
            "Supervised Learning": [0.95, 0.90, 0.88, 0.92, 0.85],
            "Feature Engineering": [0.88, 0.82, 0.90, 0.85, 0.80],
            "Classification": [0.75, 0.70, 0.80, 0.65, 0.72],
            "Decision Trees": [0.65, 0.60, 0.55, 0.70, 0.58],
            "Neural Networks": [0.55, 0.50, 0.48, 0.62, 0.52],
            "Unsupervised Learning": [0.50, 0.55, 0.45, 0.52, 0.48],
            "Regularization": [0.45, 0.40, 0.50, 0.38, 0.42],
            "Gradient Descent": [0.42, 0.38, 0.45, 0.35, 0.40],
            "Overfitting": [0.35, 0.30, 0.40, 0.28, 0.32]
        }
        
        # Let's write them. Some are updated recently (last 3 days), others are older.
        now = utcnow()
        for concept in concepts:
            presets = mastery_presets.get(concept.label, [0.5, 0.5, 0.5, 0.5, 0.5])
            # For testing the recent filter:
            # Let's make "Overfitting", "Gradient Descent", "Regularization", and "Neural Networks" updated recently.
            # Make "Supervised Learning" and others updated 10 days ago.
            is_recent = concept.label in ["Overfitting", "Gradient Descent", "Regularization", "Neural Networks"]
            
            for idx, student in enumerate(students):
                days_ago = random.randint(0, 3) if is_recent else random.randint(9, 12)
                updated_at = now - timedelta(days=days_ago)
                
                mastery = ConceptMastery(
                    student_id=student.id,
                    subject="Machine Learning",
                    concept_id=concept.concept_id,
                    mastery=presets[idx],
                    updated_at=updated_at
                )
                session.add(mastery)
                
        session.commit()
        
        # 5. Generate Mistake Patterns
        print("Seeding Mistake Patterns...")
        # Let's seed common misconceptions for the weaker concepts
        mistake_details = [
            # concept, mistake_tag, count, is_recent
            ("Overfitting", "memorizing_training_data", 8, True),
            ("Overfitting", "noise_sensitivity", 5, True),
            ("Gradient Descent", "learning_rate_too_high", 10, True),
            ("Gradient Descent", "local_minima_stuck", 6, True),
            ("Regularization", "l1_vs_l2_confusion", 7, True),
            ("Neural Networks", "vanishing_gradients", 4, False),
            ("Decision Trees", "tree_depth_overfit", 3, False),
            ("Feature Engineering", "missing_imputation_error", 2, False),
        ]
        
        concept_map = {c.label: c.concept_id for c in concepts}
        
        for concept_label, tag, count, is_recent in mistake_details:
            cid = concept_map.get(concept_label)
            if not cid:
                continue
                
            # Distribute counts across students
            remaining = count
            for idx, student in enumerate(students):
                if remaining <= 0:
                    break
                # Last student gets remaining or a portion
                std_count = remaining if idx == len(students) - 1 else random.randint(0, min(remaining, 3))
                if std_count <= 0:
                    continue
                remaining -= std_count
                
                days_ago = random.randint(0, 3) if is_recent else random.randint(9, 12)
                last_seen = now - timedelta(days=days_ago)
                
                mistake = MistakePattern(
                    student_id=student.id,
                    subject="Machine Learning",
                    concept_id=cid,
                    mistake_tag=tag,
                    count=std_count,
                    last_seen_at=last_seen
                )
                session.add(mistake)
                
        session.commit()
        
        # 6. Generate Interactions over the last 30 days (for heatmap)
        print("Seeding Interactions (last 30 days)...")
        # Types: doubt, feedback, assignment_evaluated
        # Doubt outcomes: answered, out_of_syllabus
        # Feedback outcomes: understood, confused
        
        interaction_questions = {
            "Overfitting": [
                "What is overfitting?",
                "How do we prevent overfitting?",
                "Is high variance the same as overfitting?",
                "How does regularization stop overfitting?"
            ],
            "Gradient Descent": [
                "Why is my gradient descent converging so slowly?",
                "What is the difference between batch and stochastic gradient descent?",
                "What happens if the learning rate is too big?",
                "How does momentum help gradient descent?"
            ],
            "Supervised Learning": [
                "Definition of supervised learning",
                "Is regression supervised learning?",
                "What are some supervised learning algorithms?"
            ],
            "Neural Networks": [
                "What is backpropagation?",
                "What does ReLU activation function do?",
                "What is a hidden layer in a neural network?"
            ],
            "Decision Trees": [
                "How do decision trees split nodes?",
                "What is information gain in decision trees?",
                "What is pruning in decision trees?"
            ]
        }
        
        # Let's create a distributed timeline of interactions
        for day_idx in range(30):
            # 0 is today, 29 is 29 days ago
            interaction_date = now - timedelta(days=day_idx)
            
            # Random number of interactions on this day (e.g. 0 to 5)
            # Make some days high activity (e.g., just before an assignment)
            if day_idx in [2, 3, 10, 11, 18, 25]:
                num_interactions = random.randint(6, 12) # high study day
            else:
                num_interactions = random.randint(1, 4)
                
            for _ in range(num_interactions):
                student = random.choice(students)
                concept_label = random.choice(list(interaction_questions.keys()))
                cid = concept_map[concept_label]
                
                int_type = random.choice(["doubt", "feedback", "assignment_evaluated"])
                
                if int_type == "doubt":
                    question = random.choice(interaction_questions[concept_label])
                    outcome = random.choice(["answered", "answered", "not_in_syllabus_no_context"])
                elif int_type == "feedback":
                    question = "(feedback)"
                    outcome = random.choice(["understood", "understood", "confused"])
                else:
                    # assignment_evaluated
                    question = f"Evaluate Assignment Question for {concept_label}"
                    score = random.randint(3, 10)
                    outcome = f"scored_{score}_10"
                    
                interaction = Interaction(
                    student_id=student.id,
                    subject="Machine Learning",
                    type=int_type,
                    question_text=question,
                    concepts_json=json.dumps([cid]),
                    outcome=outcome,
                    created_at=interaction_date
                )
                session.add(interaction)
                
        session.commit()
        print("Database Seeded Successfully!")
        
    except Exception as e:
        session.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        session.close()

if __name__ == "__main__":
    seed_data()
