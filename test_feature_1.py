import requests
import json
import time

BASE_URL = "http://127.0.0.1:5000"

def test_ask_question(question, expected_status=200):
    print(f"\n❓ Asking: {question}")
    url = f"{BASE_URL}/ask"
    payload = {"question": question}
    
    try:
        response = requests.post(url, json=payload)
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   🤖 Answer: {data.get('answer')}")
        else:
            print(f"   ❌ Error: {response.text}")
            
        return response
    except Exception as e:
        print(f"   ❌ Connection Error: {str(e)}")
        return None

if __name__ == "__main__":
    print("🧪 Testing Phase 2: Teacher-Guided Doubt Solving")
    print("="*60)
    
    # 1. Test basic question
    # Assuming the previous PDF (Machine Learning) is still uploaded
    test_ask_question("What is Artificial Bee Colony Optimization?")
    
    # 2. Test irrelevant question
    test_ask_question("What is the capital of France?")
    
    # 3. Test empty question
    test_ask_question("", expected_status=400)
    
    print("\n✅ Test Complete")
