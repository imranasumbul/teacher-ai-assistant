"""
Embedding Generation Module
Converts text chunks into embedding vectors using Sentence Transformers
"""

from sentence_transformers import SentenceTransformer
import numpy as np


class EmbeddingGenerator:
    """
    Generates embeddings for text chunks using Sentence Transformers
    """
    
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        """
        Initialize the embedding generator
        
        Args:
            model_name (str): Name of the Sentence Transformer model
                            Default: 'all-MiniLM-L6-v2' (fast, 384 dimensions)
        """
        print(f"\n🔄 Loading embedding model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        print(f"✅ Model loaded successfully!")
        print(f"   📊 Embedding dimension: {self.embedding_dim}")
    
    def generate_embeddings(self, chunks):
        """
        Generate embeddings for a list of text chunks
        
        Args:
            chunks (list): List of text chunks
            
        Returns:
            list: List of tuples (embedding_vector, chunk_text)
        """
        if not chunks:
            print("⚠️  No chunks to embed")
            return []
        
        print("\n" + "="*80)
        print("🧠 GENERATING EMBEDDINGS")
        print("="*80)
        print(f"   📝 Number of chunks: {len(chunks)}")
        print(f"   🔄 Processing...")
        
        # Generate embeddings for all chunks at once (batch processing)
        embeddings = self.model.encode(chunks, show_progress_bar=False)
        
        # Create list of (embedding, chunk_text) pairs
        embedding_pairs = []
        for i, (embedding, chunk) in enumerate(zip(embeddings, chunks)):
            embedding_pairs.append((embedding, chunk))
        
        print(f"   ✅ Embeddings generated successfully!")
        print(f"   📊 Embedding dimension: {self.embedding_dim}")
        print(f"   🔢 Total embeddings created: {len(embedding_pairs)}")
        print(f"   💾 Each embedding size: {embeddings[0].nbytes} bytes")
        
        # Show sample embedding info
        print("\n" + "-"*80)
        print("📊 SAMPLE EMBEDDING INFO:")
        print("-"*80)
        print(f"   First embedding shape: {embeddings[0].shape}")
        print(f"   First embedding (first 5 values): {embeddings[0][:5]}")
        print(f"   Associated chunk preview: {chunks[0][:100]}...")
        print("="*80 + "\n")
        
        return embedding_pairs
    
    def get_embedding_dimension(self):
        """
        Get the dimension of the embeddings
        
        Returns:
            int: Embedding dimension
        """
        return self.embedding_dim


# Global instance (will be initialized when first used)
_embedding_generator = None

def get_embedding_generator():
    """
    Get or create the global embedding generator instance
    
    Returns:
        EmbeddingGenerator: The embedding generator instance
    """
    global _embedding_generator
    if _embedding_generator is None:
        _embedding_generator = EmbeddingGenerator()
    return _embedding_generator


def generate_embeddings(chunks):
    """
    Convenience function to generate embeddings
    
    Args:
        chunks (list): List of text chunks
        
    Returns:
        list: List of tuples (embedding_vector, chunk_text)
    """
    generator = get_embedding_generator()
    return generator.generate_embeddings(chunks)


if __name__ == "__main__":
    # Test the embedder
    test_chunks = [
        "Machine learning is a subset of artificial intelligence.",
        "Deep learning uses neural networks with multiple layers."
    ]
    
    generator = EmbeddingGenerator()
    embeddings = generator.generate_embeddings(test_chunks)
    print(f"\nTest complete: Generated {len(embeddings)} embeddings")
