"""
Debug script to test Brave Search API
"""

import requests

API_KEY = "BSAHie1ZI1j77ZpQVuu3DHLsVuDFnt6"

# Test web search first (simpler endpoint)
print("Testing Brave Web Search API...")
url = "https://api.search.brave.com/res/v1/web/search"
headers = {
    "Accept": "application/json",
    "X-Subscription-Token": API_KEY
}
params = {
    "q": "beautiful mountains",
    "count": 5
}

try:
    response = requests.get(url, headers=headers, params=params)
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    if response.status_code != 200:
        print(f"Error Response: {response.text}")
    else:
        data = response.json()
        print("✅ Web search API works!")
        print(f"Found {len(data.get('web', {}).get('results', []))} web results")
except Exception as e:
    print(f"❌ Web search failed: {e}")

print("\n" + "="*50 + "\n")

# Test image search
print("Testing Brave Image Search API...")
url = "https://api.search.brave.com/res/v1/images/search"
headers = {
    "Accept": "application/json",
    "X-Subscription-Token": API_KEY
}
params = {
    "q": "Jackie Chan",
    "count": 5
}

try:
    response = requests.get(url, headers=headers, params=params)
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    if response.status_code != 200:
        print(f"Error Response: {response.text}")
    else:
        data = response.json()
        print("✅ Image search API works!")
        print(f"Found {len(data.get('results', []))} image results")
        if data.get('results'):
            first_result = data['results'][0]
            print(f"First result keys: {list(first_result.keys())}")
            
            # Test folder creation
            import os
            search_term = "mountains"
            base_folder = r"C:\Users\Admin\Pictures\BraveSearch"
            download_folder = os.path.join(base_folder, search_term)
            os.makedirs(download_folder, exist_ok=True)
            print(f"✅ Created folder: {download_folder}")
except Exception as e:
    print(f"❌ Image search failed: {e}")