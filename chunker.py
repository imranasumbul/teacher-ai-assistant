"""
Text Chunking Module
Splits text into manageable chunks of 300-500 words for embedding
"""

import re


def chunk_text(text, target_words=400, min_words=300, max_words=500):
    """
    Split text into chunks of approximately 300-500 words
    
    Args:
        text (str): Text to be chunked
        target_words (int): Target number of words per chunk (default: 400)
        min_words (int): Minimum words per chunk (default: 300)
        max_words (int): Maximum words per chunk (default: 500)
        
    Returns:
        list: List of text chunks
    """
    if not text or not text.strip():
        return []
    
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Split into words
    words = text.split()
    
    if len(words) <= max_words:
        # If text is short enough, return as single chunk
        return [text]
    
    chunks = []
    current_chunk = []
    current_word_count = 0
    
    for word in words:
        current_chunk.append(word)
        current_word_count += 1
        
        # When we reach target size, try to find a good breaking point
        if current_word_count >= target_words:
            # Look ahead for sentence ending (period, question mark, exclamation)
            if word.endswith(('.', '!', '?')) or current_word_count >= max_words:
                # Save this chunk
                chunks.append(' '.join(current_chunk))
                current_chunk = []
                current_word_count = 0
    
    # Add remaining words as final chunk (if any)
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    # Print chunk information to console
    print("\n" + "="*80)
    print(f"📊 TEXT CHUNKING COMPLETE")
    print("="*80)
    print(f"   📝 Total words: {len(words)}")
    print(f"   🔢 Total chunks: {len(chunks)}")
    print(f"   📏 Chunk size range: {min_words}-{max_words} words (target: {target_words})")
    
    # Show word counts for each chunk
    chunk_word_counts = [len(chunk.split()) for chunk in chunks]
    print(f"   📊 Actual chunk sizes: {chunk_word_counts}")
    
    # Print first 2 chunks
    print("\n" + "-"*80)
    print("📄 FIRST 2 CHUNKS:")
    print("-"*80)
    
    for i, chunk in enumerate(chunks[:2], 1):
        word_count = len(chunk.split())
        preview = chunk[:150] + "..." if len(chunk) > 150 else chunk
        print(f"\nChunk {i} ({word_count} words):")
        print(f"   {preview}")
    
    if len(chunks) > 2:
        print(f"\n   ... and {len(chunks) - 2} more chunk(s)")
    
    print("="*80 + "\n")
    
    return chunks


def get_chunk_stats(chunks):
    """
    Get statistics about chunks
    
    Args:
        chunks (list): List of text chunks
        
    Returns:
        dict: Statistics about the chunks
    """
    if not chunks:
        return {
            'total_chunks': 0,
            'total_words': 0,
            'avg_words_per_chunk': 0,
            'min_words': 0,
            'max_words': 0
        }
    
    word_counts = [len(chunk.split()) for chunk in chunks]
    
    return {
        'total_chunks': len(chunks),
        'total_words': sum(word_counts),
        'avg_words_per_chunk': sum(word_counts) / len(word_counts),
        'min_words': min(word_counts),
        'max_words': max(word_counts)
    }


if __name__ == "__main__":
    # Test the chunker
    sample_text = "Machine learning is a subset of artificial intelligence. " * 100
    chunks = chunk_text(sample_text)
    print(f"Created {len(chunks)} chunks from sample text")
