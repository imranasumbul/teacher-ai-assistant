"""
FAISS Vector Store Module
Manages FAISS index for storing and retrieving embeddings
"""

import faiss  # type: ignore
import numpy as np
import json
import os
from typing import List, Dict, Tuple, Optional, Any


class VectorStore:
    """
    Manages FAISS index for vector similarity search
    """
    
    def __init__(self, dimension: int = 384) -> None:
        """
        Initialize the vector store
        
        Args:
            dimension (int): Dimension of the embeddings (default: 384 for all-MiniLM-L6-v2)
        """
        self.dimension: int = dimension
        self.index: Optional[Any] = None  # faiss.Index type
        self.metadata: List[Dict[str, Any]] = []  # Store chunk texts and other metadata
        self.index_path: str = "faiss_index.bin"
        self.metadata_path: str = "metadata.json"
        
    def create_index(self) -> None:
        """
        Create a new FAISS index
        Uses IndexFlatL2 for exact similarity search
        """
        print(f"\n🔧 Creating FAISS index (dimension: {self.dimension})...")
        self.index = faiss.IndexFlatL2(self.dimension)
        print(f"✅ FAISS index created successfully!")
        
    def add_embeddings(self, embedding_pairs: List[Tuple[Any, str]], filename: str = "") -> None:
        """
        Add embeddings to the FAISS index
        
        Args:
            embedding_pairs (list): List of (embedding, chunk_text) tuples
            filename (str): Source filename for metadata
        """
        if self.index is None:
            self.create_index()
        
        print("\n" + "="*80)
        print("💾 ADDING EMBEDDINGS TO FAISS INDEX")
        print("="*80)
        
        # Extract embeddings and texts
        embeddings = []
        for item in embedding_pairs:
            # Defensive unpack: item must be a (embedding, chunk_text) tuple
            if isinstance(item, (list, tuple)) and len(item) == 2:
                embedding, chunk_text = item
            else:
                print(f"⚠️  Skipping malformed embedding item: {type(item)}")
                continue
            embeddings.append(embedding)
            self.metadata.append({
                "chunk_text": chunk_text,
                "source_file": filename,
                "chunk_id": len(self.metadata)
            })
        
        # Convert to numpy array and add to index
        embeddings_array = np.array(embeddings).astype('float32')
        self.index.add(embeddings_array)
        
        print(f"   ✅ Added {len(embeddings)} embeddings to index")
        print(f"   📊 Total embeddings in index: {self.index.ntotal}")
        print(f"   📝 Total metadata entries: {len(self.metadata)}")
        print("="*80 + "\n")
        
    def save(self) -> None:
        """
        Save the FAISS index and metadata to disk
        """
        print("\n" + "="*80)
        print("💾 SAVING FAISS INDEX TO DISK")
        print("="*80)
        
        # Save FAISS index
        faiss.write_index(self.index, self.index_path)
        print(f"   ✅ FAISS index saved to: {self.index_path}")
        
        # Save metadata
        with open(self.metadata_path, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)
        print(f"   ✅ Metadata saved to: {self.metadata_path}")
        
        # Show file sizes
        index_size = os.path.getsize(self.index_path) / 1024  # KB
        metadata_size = os.path.getsize(self.metadata_path) / 1024  # KB
        
        print(f"\n   📊 INDEX STATISTICS:")
        print(f"      • Total vectors: {self.index.ntotal}")
        print(f"      • Vector dimension: {self.dimension}")
        print(f"      • Index file size: {index_size:.2f} KB")
        print(f"      • Metadata file size: {metadata_size:.2f} KB")
        print(f"      • Total size: {(index_size + metadata_size):.2f} KB")
        print("="*80 + "\n")
        
    def load(self) -> bool:
        """
        Load the FAISS index and metadata from disk
        
        Returns:
            bool: True if loaded successfully, False otherwise
        """
        if not os.path.exists(self.index_path) or not os.path.exists(self.metadata_path):
            print("⚠️  No existing index found. Will create new one on first upload.")
            return False
        
        print(f"\n📂 Loading existing FAISS index from disk...")
        
        # Load FAISS index
        self.index = faiss.read_index(self.index_path)
        
        # Load metadata
        with open(self.metadata_path, 'r', encoding='utf-8') as f:
            self.metadata = json.load(f)
        
        print(f"   ✅ Index loaded: {self.index.ntotal} vectors")
        print(f"   ✅ Metadata loaded: {len(self.metadata)} entries\n")
        
        return True
    
    def get_index_size(self) -> int:
        """
        Get the number of vectors in the index
        
        Returns:
            int: Number of vectors
        """
        if self.index is None:
            return 0
        return self.index.ntotal

    def search(self, query_vector: np.ndarray, k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for similar chunks
        
        Args:
            query_vector (np.ndarray): Query embedding vector
            k (int): Number of results to return
            
        Returns:
            list: List of dictionaries with chunk data and similarity scores
        """
        if self.index is None or self.index.ntotal == 0:
            return []
            
        # Reshape query vector if needed
        if len(query_vector.shape) == 1:
            query_vector = query_vector.reshape(1, -1)
            
        # Search
        distances, indices = self.index.search(query_vector.astype('float32'), k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx == -1:  # No more results
                continue
            
            if idx < len(self.metadata):
                result = self.metadata[idx].copy()
                result['distance'] = float(distances[0][i])
                results.append(result)
            
        return results


# Global vector store instance
_vector_store = None

def get_vector_store() -> VectorStore:
    """
    Get or create the global vector store instance
    
    Returns:
        VectorStore: The vector store instance
    """
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
        _vector_store.load()  # Try to load existing index
    return _vector_store


def save_to_vector_store(embedding_pairs: List[Tuple[Any, str]], filename: str = "") -> None:
    """
    Convenience function to save embeddings to vector store
    
    Args:
        embedding_pairs (list): List of (embedding, chunk_text) tuples
        filename (str): Source filename
    """
    store = get_vector_store()
    store.add_embeddings(embedding_pairs, filename)
    store.save()


if __name__ == "__main__":
    # Test the vector store
    print("FAISS Vector Store Module - Ready to use")
