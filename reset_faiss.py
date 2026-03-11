# Reset FAISS Index Script
# Run this to clear all FAISS data and start fresh

import os
import sys

print("="*60)
print("🔄 RESETTING FAISS VECTOR STORE")
print("="*60)

files_to_delete = ['faiss_index.bin', 'metadata.json']

for file in files_to_delete:
    if os.path.exists(file):
        try:
            os.remove(file)
            print(f"✅ Deleted: {file}")
        except Exception as e:
            print(f"❌ Could not delete {file}: {e}")
    else:
        print(f"ℹ️  {file} does not exist (already deleted)")

print("\n" + "="*60)
print("✅ RESET COMPLETE!")
print("="*60)
print("\nNext steps:")
print("1. Run: python app.py")
print("2. Visit: http://localhost:5000")
print("3. Upload fresh files - a new index will be created")
print("="*60)
