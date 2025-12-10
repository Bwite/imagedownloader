import requests

API_KEY = "BSAHie1ZI1j77ZpQVuu3DHLsVuDFnt6"

url = "https://api.search.brave.com/res/v1/images/search"
headers = {
    "Accept": "application/json",
    "X-Subscription-Token": API_KEY
}
params = {
    "q": "mountains",
    "count": 1
}

response = requests.get(url, headers=headers, params=params)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    if data.get('results'):
        result = data['results'][0]
        print("\nFirst result structure:")
        print(f"Keys: {list(result.keys())}")
        print(f"\nFull result:\n{result}")
        
        # Check for image URLs
        print("\n" + "="*50)
        print("Image URL locations:")
        if 'thumbnail' in result:
            print(f"thumbnail: {result['thumbnail']}")
        if 'properties' in result:
            print(f"properties: {result['properties']}")
        if 'url' in result:
            print(f"url: {result['url']}")
