# Architecture & Data Flow Diagrams

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE (HTML/CSS)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐│
│  │   Home Page  │  │ Student Doubt│  │  Assignment  │  │ Teacher Notes││
│  │   Dashboard  │  │   Solver     │  │  Evaluator   │  │   Manager    ││
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘│
└─────────────────┬───────────────────────────────────────────────────────┘
                  │ HTTP Requests
                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    FLASK API SERVER (app.py)                            │
│  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐  │
│  │ /upload_notes     │  │ /ask (doubt)      │  │ /evaluate_assignment
│  │ /feedback         │  │ /feedback         │  │ Routes             │
│  └───────────────────┘  └───────────────────┘  └───────────────────┘  │
└──┬──────────────────────────────────────────────────────────────────────┘
   │
   ├─────────────────────────────┬──────────────────────────────┬────────────────┐
   │                             │                              │                │
   ▼                             ▼                              ▼                ▼
┌──────────────┐       ┌──────────────────┐      ┌──────────────┐    ┌──────────────────┐
│  EXTRACTION  │       │  EMBEDDING       │      │  VECTOR      │    │   PERSONALIZATION│
│  LAYER       │       │  GENERATION      │      │  DATABASE    │    │   ENGINE         │
│              │       │  (Sentence Trans)│      │  (FAISS)     │    │                  │
│ • extractor  │───→   │                  │───→  │              │    │ • concept_service│
│ • chunker    │       │ all-MiniLM-L6-v2 │      │ faiss_index  │    │ • personalization│
└──────────────┘       │ (384-dim)        │      │ .bin         │    │ • mistakepatterns│
                       │                  │      │              │    │ • masterytracking│
                       └──────────────────┘      └──────────────┘    └──────────────────┘
                                                       ▲
                                                       │ Vector Search
                                                       │
                                                       ▼
                                           ┌──────────────────────┐
                                           │   GEMINI API        │
                                           │   (LLM)             │
                                           │                     │
                                           │ Answer + Concepts   │
                                           └──────────────────────┘
                                                       │
                                                       ▼
                                           ┌──────────────────────┐
                                           │   SQLITE DATABASE   │
                                           │                     │
                                           │ • Students          │
                                           │ • ConceptCatalog    │
                                           │ • ConceptMastery    │
                                           │ • Interactions      │
                                           │ • MistakePatterns   │
                                           └──────────────────────┘
```

## 🔄 Doubt Solving Flow (Detailed)

```
STUDENT QUESTION
       │
       ▼
┌──────────────────────────────┐
│ 1. Generate Embedding        │
│    question → 384-dim vector │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ 2. Vector Search in FAISS           │
│    Find k=5 most similar chunks      │
│    from teacher notes                │
└──────────────┬───────────────────────┘
               │
       ┌───────┴───────┐
       │               │
    FOUND          NOT FOUND
    CHUNKS         CHUNKS
       │               │
       ▼               ▼
   CONTINUE      RETURN "Not in
                  Syllabus"
       │
       ▼
┌──────────────────────────────────────┐
│ 3. Identify Concepts                │
│    What concepts is student asking? │
│    (Uses concept embedding vectors) │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ 4. Get Student Mastery              │
│    Query concept_mastery from DB    │
│    Find weak areas (score < 0.5)    │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ 5. Build Personalization Instruction│
│    IF weak → detailed, step-by-step │
│    IF strong → concise, advanced    │
│    IF cold_start → neutral tone     │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ 6. Prompt Gemini API with:          │
│    • Retrieved context chunks       │
│    • Personalization instruction    │
│    • Student question               │
│    • Extract JSON: answer+concepts  │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ 7. Parse Response                   │
│    Extract:                         │
│    - answer (string)                │
│    - concept_labels (list)          │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ 8. Map Concepts to DB               │
│    concept_labels → concept_ids     │
│    (Create new if doesn't exist)    │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ 9. Log Interaction                  │
│    Store: student_id, subject,      │
│    question, concept_ids, outcome   │
└──────────────┬───────────────────────┘
               │
               ▼
    RETURN ANSWER + CONCEPT_IDS
    (Student clicks: "understood" or "confused")
               │
               ▼
    ┌──────────────────────────┐
    │ 10. FEEDBACK LOOP        │
    │                          │
    │ IF "understood":         │
    │  ↳ mastery += 0.08       │
    │                          │
    │ IF "confused":           │
    │  ↳ mastery -= 0.08       │
    │  ↳ log as mistake        │
    └──────────────────────────┘
               │
               ▼
    NEXT TIME SAME CONCEPT:
    Personalization adapts! 🎯
```

## 📊 Database Schema

```
┌─────────────────────────────────────────────────────────────────────┐
│                           SQLITE DATABASE                           │
└─────────────────────────────────────────────────────────────────────┘
        │                    │                    │                   │
        ▼                    ▼                    ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Student    │    │ Concept      │    │  Concept     │    │ Mistake      │
│              │    │ Catalog      │    │  Mastery     │    │ Pattern      │
│ PK: id       │    │              │    │              │    │              │
│ student_id   │    │ PK: id       │    │ PK: id       │    │ PK: id       │
│ name         │    │ subject      │    │ student_id   │    │ student_id   │
│ class_code   │    │ label        │    │ concept_id   │    │ concept_id   │
│ created_at   │    │ description  │    │ mastery_score│    │ count        │
│              │    │              │    │ updated_at   │    │ mistake_tag  │
│              │    │              │    │              │    │ last_seen    │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
        │                    ▲                    ▲                   ▲
        │                    │                    │                   │
        │                    └────────────────────┴───────────────────┘
        │                              │
        │              ┌───────────────┴──────────────┐
        │              │                              │
        ▼              ▼                              ▼
    ┌──────────────────────────────────────────────────────────┐
    │              Interaction                                 │
    │  (Audit log of all student activities)                  │
    │                                                          │
    │ PK: id                                                   │
    │ student_id (FK → Student)                               │
    │ subject                                                  │
    │ type ("doubt" or "feedback")                             │
    │ question_text                                            │
    │ concepts_json (list of concept_ids)                      │
    │ outcome ("answered" / "understood" / "confused")         │
    │ created_at                                               │
    └──────────────────────────────────────────────────────────┘
```

## 🗂️ File Organization

```
teacher-ai-assistant/
│
├── app.py                    ← Flask app, all routes
├── requirements.txt          ← Dependencies
│
├── CORE MODULES:
│   ├── extractor.py         ← Extract text from PDF/TXT
│   ├── chunker.py           ← Split into smart chunks
│   ├── embedder.py          ← Generate 384-dim vectors
│   ├── vector_store.py      ← FAISS management
│   │
│   ├── concept_service.py   ← Map concepts to IDs
│   ├── personalization.py   ← Track mastery & adapt
│   ├── db.py                ← Database models & session
│   ├── assignment_checker.py ← AI-powered evaluation
│
├── FRONTEND:
│   ├── static/css/
│   │   └── static.css
│   └── templates/
│       ├── index.html           (Dashboard)
│       ├── student_doubt.html   (Q&A interface)
│       ├── assignment_upload.html (Evaluation)
│       └── teacher_notes.html   (Upload materials)
│
├── DATA & UTILITIES:
│   ├── faiss_index.bin       ← Vector database (persisted)
│   ├── metadata.json         ← Chunk metadata
│   ├── app.db                ← SQLite database
│   ├── evaluation_rules.txt  ← Teacher rubric
│
├── TESTING:
│   ├── test_feature_1.py
│   ├── test_assignment.py
│   ├── test_feedback.py
│   └── test_assignment_evaluation.py
│
└── UTILITIES:
    ├── check_faiss.py        ← Inspect vector store
    ├── reset_faiss.py        ← Clear vector store
    ├── check_db.py           ← Inspect database
    └── view_db.py            ← View DB contents
```

## 🔐 Data Privacy & Security

```
┌─────────────────────────────────────────────────────┐
│         SECURITY & PRIVACY LAYERS                   │
└─────────────────────────────────────────────────────┘

1. FILE UPLOAD SECURITY:
   ├─ werkzeug.secure_filename → prevent path traversal
   ├─ Allowed extensions check (.pdf, .txt only)
   └─ Files stored in /uploads folder

2. API KEY SECURITY:
   ├─ GEMINI_API_KEY in .env (not committed)
   ├─ python-dotenv loads at startup
   └─ Never exposed in responses

3. DATABASE:
   ├─ SQLAlchemy ORM → prevents SQL injection
   ├─ Connection pooling via session management
   └─ Validation at model level

4. FUTURE (Phase 2):
   ├─ JWT authentication for users
   ├─ Role-based access (teacher/student)
   ├─ Encrypted passwords
   ├─ HTTPS only
   └─ Data encryption at rest
```

## 📈 Scalability Path

```
CURRENT (1-10 students)
└─ Flask + SQLite + FAISS-CPU
   └─ Single machine deployment
      └─ Good for prototyping

    ⬇️ (After optimization)

SCALING (10-100 students)
└─ FastAPI + PostgreSQL + FAISS-GPU
   └─ Single server with better resources
      └─ Caching layer (Redis)

    ⬇️ (After growth)

PRODUCTION (100-1000 students)
└─ Microservices + K8s + Pinecone
   └─ Multiple servers
      └─ Load balancer
         └─ Message queue (Celery)
            └─ Real-time updates (WebSockets)

    ⬇️ (After success)

ENTERPRISE (1000+ students)
└─ Full cloud native
   └─ Multi-region
      └─ Advanced caching
         └─ Fine-tuned models
            └─ Advanced analytics (MLflow)
```
