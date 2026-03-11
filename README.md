# Teacher AI Assistant

Teacher AI Assistant is an AI-powered educational platform designed to provide personalized learning experiences and streamline teacher workflows. It uses Retrieval-Augmented Generation (RAG) with the Gemini model to answer student doubts strictly based on uploaded teacher notes, evaluates student assignments automatically using customizable rubrics, and dynamically adapts its teaching style based on a student's individual mastery levels and past mistakes.

### Key Features
- **Syllabus-Bound Doubt Solving**: Students can ask questions, and the AI answers them using only the context from notes uploaded by the teacher.
- **Personalized Learning**: Tracks student progress on specific concepts, identifying weak areas and adapting responses (e.g., providing more step-by-step explanations or simpler analogies for struggling concepts).
- **Automated Assignment Evaluation**: Students upload assignments, which are automatically graded and evaluated against the teacher's uploaded rubric and notes.
- **Teacher Notes & Rubric Upload**: Teachers can easily upload their course materials (PDF/TXT), which are embedded and stored in a vector database for quick retrieval.

## Setup & Run

1.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run Application**
    ```bash
    python app.py
    ```
    Access at: [http://localhost:5000](http://localhost:5000)

## Utilities
- `python check_faiss.py` : Check vector store status.
- `python reset_faiss.py` : Clear vector store.
