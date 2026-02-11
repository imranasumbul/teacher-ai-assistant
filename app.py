from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import os
from dotenv import load_dotenv

load_dotenv()
from extractor import extract_text
from chunker import chunk_text
from embedder import generate_embeddings
from vector_store import save_to_vector_store, get_vector_store
import google.generativeai as genai

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'txt'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Configure Gemini API
GOOGLE_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GOOGLE_API_KEY:
    print("❌ WARNING: GEMINI_API_KEY environment variable not set!")
else:
    genai.configure(api_key=GOOGLE_API_KEY)

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if file has allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def home():
    return render_template('index.html')

@app.route("/upload", methods=['POST'])
def upload_file():
    """
    Upload endpoint for teacher notes (PDF and .txt files only)
    """
    # Check if file is in request
    if 'file' not in request.files:
        return jsonify({"error": "No file part in request"}), 400
    
    file = request.files['file']
    
    # Check if file is selected
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    # Validate file extension
    if not allowed_file(file.filename):
        return jsonify({"error": "Only PDF and .txt files are allowed"}), 400
    
    # Save file
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    # Print success message to console
    print(f"✅ FILE UPLOADED SUCCESSFULLY: {filename}")
    print(f"   Saved to: {filepath}")
    
    # Extract text from uploaded file
    try:
        extracted_text = extract_text(filepath)
        text_length = len(extracted_text)
        
        # Chunk the extracted text
        chunks = chunk_text(extracted_text)
        
        # Generate embeddings for chunks
        embedding_pairs = generate_embeddings(chunks)
        
        # Save embeddings to FAISS vector store
        save_to_vector_store(embedding_pairs, filename)
        
        # Extract just the embeddings and chunks for response
        embedding_dim = embedding_pairs[0][0].shape[0] if embedding_pairs else 0
        
        return jsonify({
            "message": "✅ PHASE 1 COMPLETE - File uploaded, processed, and saved to vector store!",
            "filename": filename,
            "filepath": filepath,
            "text_length": text_length,
            "total_chunks": len(chunks),
            "total_embeddings": len(embedding_pairs),
            "embedding_dimension": embedding_dim,
            "vector_store_saved": True,
            "chunk_preview": chunks[0][:150] if chunks else ""
        }), 200
    
    except Exception as e:
        print(f"❌ ERROR PROCESSING FILE: {str(e)}")
        return jsonify({
            "error": f"File uploaded but processing failed: {str(e)}"
        }), 500

@app.route("/ask", methods=['POST'])
def ask_question():
    """
    Step 9: Accept student question
    """
    data = request.get_json()
    if not data or 'question' not in data:
        return jsonify({"error": "Question is required"}), 400
        
    question = data['question'].strip()
    if not question:
        return jsonify({"error": "Question cannot be empty"}), 400
        
    print(f"\n❓ Student Question: {question}")
    
    try:
        # Step 10: Generate embedding
        # generate_embeddings returns list of (embedding, text) tuples
        embedding_pairs = generate_embeddings([question])
        if not embedding_pairs:
            return jsonify({"error": "Failed to generate embedding"}), 500
            
        query_vector = embedding_pairs[0][0]
        
        # Step 11: Retrieve relevant chunks
        store = get_vector_store()
        results = store.search(query_vector, k=5)
        
        # Log retrieved chunks
        print("\n🔍 Retrieved Context:")
        retrieved_texts = []
        for i, res in enumerate(results):
            text = res['chunk_text']
            retrieved_texts.append(text)
            print(f"Chunk {i+1} (dist={res.get('distance', 0):.4f}): {text[:100]}...")
            
        context_str = "\n\n".join(retrieved_texts)
        
        # Step 12: Prompt Engineering
        system_instructions = (
            "You are a teacher assistant. You must answer ONLY using the provided teacher notes.\n"
            "If the answer is not found in the notes, respond exactly with:\n"
            "'Not in syllabus'"
        )
        
        prompt = f"""{system_instructions}

Teacher Notes:
{context_str}

Student Question:
{question}"""

        # Step 13: LLM Call
        try:
            # model = genai.GenerativeModel('gemini-1.5-flash')
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3
                )
            )
            
            answer = response.text.strip()
            print(f"🤖 LLM Answer: {answer}")
            
            return jsonify({"answer": answer})
            
        except Exception as llm_err:
            print(f"❌ LLM Error: {str(llm_err)}")
            return jsonify({"error": f"LLM Error: {str(llm_err)}"}), 500

    except Exception as e:
        print(f"❌ Error processing question: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
