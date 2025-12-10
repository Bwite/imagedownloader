"""
Brave Search Image Downloader
Downloads images from Brave Search API to organized folders
"""

import requests
import os
import time
from urllib.parse import urlparse

class BraveImageDownloader:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.search.brave.com/res/v1/images/search"
        self.headers = {
            "Accept": "application/json",
            "X-Subscription-Token": api_key
        }
        self.base_folder = r"C:\Users\Admin\Pictures\BraveSearch"
        
    def search_images(self, query, count=50):
        """Search for images using Brave Search API"""
        params = {
            "q": query,
            "count": count
        }
        
        try:
            print(f"Searching for '{query}'...")
            response = requests.get(self.base_url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                print(f"❌ API Error {response.status_code}: {response.text}")
                return []
                
            data = response.json()
            results = data.get('results', [])
            print(f"✅ Found {len(results)} images")
            return results
            
        except Exception as e:
            print(f"❌ Search failed: {e}")
            return []
    
    def get_file_extension(self, url, content_type=None):
        """Get appropriate file extension from URL or content type"""
        # Try to get extension from URL
        parsed_url = urlparse(url)
        path = parsed_url.path
        if path and '.' in path:
            ext = path.split('.')[-1].lower()
            if ext in ['jpg', 'jpeg', 'png', 'gif']:
                return f".{ext}"
        
        # Try to get extension from content type
        if content_type:
            if 'jpeg' in content_type or 'jpg' in content_type:
                return '.jpg'
            elif 'png' in content_type:
                return '.png'
            elif 'gif' in content_type:
                return '.gif'
        
        # Default to jpg
        return '.jpg'
    
    def download_images(self, query, count=50):
        """Download images for a given query"""
        # Search for images
        results = self.search_images(query, count)
        if not results:
            return
        
        # Create folder based on search term
        folder_name = query.replace(' ', '_').replace('/', '_').replace('\\', '_')
        download_folder = os.path.join(self.base_folder, folder_name)
        os.makedirs(download_folder, exist_ok=True)
        print(f"📁 Created folder: {download_folder}")
        
        # Download each image
        downloaded = 0
        for i, img in enumerate(results, 1):
            try:
                # Get image URL from the result
                img_url = img.get('src')
                if not img_url:
                    print(f"⚠️ No image URL found for result {i}")
                    continue
                
                print(f"Downloading image {i}/{len(results)}...")
                
                # Download the image
                img_response = requests.get(img_url, timeout=15, stream=True)
                img_response.raise_for_status()
                
                # Get appropriate file extension
                content_type = img_response.headers.get('content-type', '')
                file_ext = self.get_file_extension(img_url, content_type)
                
                # Create filename
                filename = f"{folder_name}_{i:02d}{file_ext}"
                filepath = os.path.join(download_folder, filename)
                
                # Save the image
                with open(filepath, 'wb') as f:
                    for chunk in img_response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                file_size = os.path.getsize(filepath) / 1024  # Size in KB
                print(f"✅ Downloaded: {filename} ({file_size:.1f} KB)")
                downloaded += 1
                
                # Small delay to be respectful to servers
                time.sleep(0.5)
                
            except Exception as e:
                print(f"❌ Failed to download image {i}: {e}")
                continue
        
        print(f"\n🎉 Successfully downloaded {downloaded} out of {len(results)} images to {download_folder}")
        return download_folder

def main():
    # Your API key
    API_KEY = "BSAHie1ZI1j77ZpQVuu3DHLsVuDFnt6"
    
    # Create downloader instance
    downloader = BraveImageDownloader(API_KEY)
    
    # Interactive mode
    print("🖼️  Brave Image Downloader")
    print("=" * 40)
    
    while True:
        query = input("\nEnter search term (or 'quit' to exit): ").strip()
        
        if query.lower() in ['quit', 'exit', 'q']:
            print("👋 Goodbye!")
            break
            
        if not query:
            print("Please enter a search term.")
            continue
        
        try:
            count = int(input("Number of images to download (default 50): ") or "50")
            if count <= 0:
                count = 50
        except ValueError:
            count = 50
            
        # Download images
        folder = downloader.download_images(query, count)
        
        if folder:
            choice = input("\nOpen folder? (y/n): ").strip().lower()
            if choice in ['y', 'yes']:
                os.startfile(folder)  # Windows specific

if __name__ == "__main__":
    main()