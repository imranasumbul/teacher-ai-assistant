# Check FAISS Index Status
# Run this to see if your FAISS index is empty or has data

import os

print("="*60)
print("📊 CHECKING FAISS INDEX STATUS")
print("="*60)

# Check if files exist
faiss_exists = os.path.exists('faiss_index.bin')
metadata_exists = os.path.exists('metadata.json')

print(f"\n📁 File Check:")
print(f"   faiss_index.bin: {'✅ EXISTS' if faiss_exists else '❌ NOT FOUND'}")
print(f"   metadata.json: {'✅ EXISTS' if metadata_exists else '❌ NOT FOUND'}")

if not faiss_exists and not metadata_exists:
    print("\n🎯 Status: EMPTY (No index created yet)")
    print("   → Upload a file to create your first index!")
elif faiss_exists:
    try:
        import faiss
        import json
        
        # Load and check FAISS index
        index = faiss.read_index('faiss_index.bin')
        total_vectors = index.ntotal
        dimension = index.d
        
        # Load metadata
        if metadata_exists:
            with open('metadata.json', 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                num_chunks = len(metadata)
        else:
            num_chunks = 0
        
        print(f"\n📊 Index Statistics:")
        print(f"   Total vectors: {total_vectors}")
        print(f"   Vector dimension: {dimension}")
        print(f"   Metadata entries: {num_chunks}")
        
        if total_vectors == 0:
            print("\n🎯 Status: EMPTY (Index exists but has no vectors)")
        else:
            print(f"\n🎯 Status: ACTIVE ({total_vectors} vectors indexed)")
            
            # Show unique source files
            if metadata_exists and metadata:
                sources = set(item['source_file'] for item in metadata)
                print(f"\n📚 Indexed Files ({len(sources)}):")
                for source in sorted(sources):
                    count = sum(1 for item in metadata if item['source_file'] == source)
                    print(f"   • {source} ({count} chunks)")
    
    except Exception as e:
        print(f"\n❌ Error reading index: {e}")
else:
    print("\n⚠️  Status: INCOMPLETE (Some files missing)")

print("="*60)
