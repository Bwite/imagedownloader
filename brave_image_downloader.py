"""
Image Downloader - Downloads images from SerpAPI (Google) with Brave as fallback
"""

import requests
import os
import time
from urllib.parse import urlparse
from PIL import Image


# Minimum image dimensions (width, height)
MIN_IMAGE_SIZE = (640, 360)


class SerpAPIImageDownloader:
    """Download images using SerpAPI (Google Images)."""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://serpapi.com/search"
    
    def search_images(self, query, count=50):
        """Search for images using SerpAPI Google Images."""
        min_w, min_h = MIN_IMAGE_SIZE
        
        params = {
            "engine": "google_images",
            "q": query,
            "num": min(count * 3, 100),  # Request extra for filtering
            "api_key": self.api_key,
            "safe": "off",
            "imgsz": "l",  # Large images
        }
        
        try:
            print(f"SerpAPI: Searching for '{query}'...")
            response = requests.get(self.base_url, params=params, timeout=30)
            
            if response.status_code != 200:
                print(f"SerpAPI Error {response.status_code}: {response.text[:200]}")
                return []
            
            data = response.json()
            results = data.get('images_results', [])
            
            # Pre-filter by dimensions
            filtered = []
            for img in results:
                w = img.get('original_width', 0)
                h = img.get('original_height', 0)
                if w >= min_w and h >= min_h:
                    filtered.append(img)
            
            if not filtered and results:
                filtered = results  # Fallback to unfiltered
            
            print(f"SerpAPI: Found {len(filtered)} images (filtered from {len(results)})")
            return filtered
            
        except Exception as e:
            print(f"SerpAPI search failed: {e}")
            return []


class BraveImageDownloader:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.search.brave.com/res/v1/images/search"
        self.headers = {
            "Accept": "application/json",
            "X-Subscription-Token": api_key
        }
        self.base_folder = os.path.join(os.getcwd(), "downloads")
        
    def search_images(self, query, count=50, min_size=None):
        """Search for images using Brave Search API, requesting large images and pre-filtering small ones."""
        request_count = min(max(count * 3, 20), 150)

        # Determine minimum quality for pre-filtering
        min_w, min_h = MIN_IMAGE_SIZE

        params = {
            "q": query,
            "count": request_count,
            "safesearch": "off",
            "size": "Large",
        }

        try:
            print(f"Searching for '{query}' (size=Large)...")
            response = requests.get(self.base_url, headers=self.headers, params=params)

            if response.status_code != 200:
                print(f"API Error {response.status_code}, retrying without size filter...")
                del params['size']
                response = requests.get(self.base_url, headers=self.headers, params=params)
                if response.status_code != 200:
                    print(f"API Error {response.status_code}: {response.text}")
                    return []

            data = response.json()
            results = data.get('results', [])

            # Pre-filter: skip results where reported dimensions are too small
            filtered = []
            for img in results:
                props = img.get('properties', {})
                if isinstance(props, dict):
                    w = props.get('width')
                    h = props.get('height')
                    if w and h:
                        try:
                            if int(w) < min_w or int(h) < min_h:
                                continue
                        except (ValueError, TypeError):
                            pass
                filtered.append(img)

            if not filtered and results:
                filtered = results  # fallback to unfiltered if all were too small

            print(f"Found {len(filtered)} images (filtered from {len(results)})")
            return filtered

        except Exception as e:
            print(f"Search failed: {e}")
            return []

    def get_file_extension(self, url, content_type=None):
        """Get appropriate file extension from URL or content type"""
        # Try to get extension from URL
        parsed_url = urlparse(url)
        path = parsed_url.path
        if path and '.' in path:
            ext = path.split('.')[-1].lower()
            if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                return f".{ext}"
        
        
        if content_type:
            if 'jpeg' in content_type or 'jpg' in content_type:
                return '.jpg'
            elif 'png' in content_type:
                return '.png'
            elif 'gif' in content_type:
                return '.gif'
            elif 'webp' in content_type:
                return '.webp'
        
        # Default to jpg
        return '.jpg'
    
    def download_images(self, query, count=50):
        """Download images for a given query, retrying from extra results on failure."""
        # Request extra results so we have fallbacks if some fail
        search_count = max(count * 3, 20)
        results = self.search_images(query, search_count)
        if not results:
            return
        
        # Create folder based on search term
        folder_name = query.replace(' ', '_').replace('/', '_').replace('\\', '_')
        download_folder = os.path.join(self.base_folder, folder_name)
        os.makedirs(download_folder, exist_ok=True)
        print(f"📁 Created folder: {download_folder}")
        
       
        downloaded = 0
        result_idx = 0
        while downloaded < count and result_idx < len(results):
            img = results[result_idx]
            result_idx += 1
            try:
                # Get image URL - prefer full-size properties.url
                img_url = None
                if 'properties' in img and isinstance(img['properties'], dict):
                    img_url = img['properties'].get('url')
                if not img_url and 'thumbnail' in img and isinstance(img['thumbnail'], dict):
                    img_url = img['thumbnail'].get('src')
                if not img_url:
                    img_url = img.get('src')
                if not img_url:
                    print(f"  No URL for result {result_idx}, trying next...")
                    continue
                
                print(f"Downloading image {downloaded+1}/{count} (result {result_idx}/{len(results)})...")
                
                # Download the image
                img_response = requests.get(img_url, timeout=15, stream=True)
                img_response.raise_for_status()
                
                # Get appropriate file extension
                content_type = img_response.headers.get('content-type', '')
                file_ext = self.get_file_extension(img_url, content_type)
                
                # Create filename
                filename = f"{folder_name}_{downloaded+1:02d}{file_ext}"
                filepath = os.path.join(download_folder, filename)
                
                # Save the image
                with open(filepath, 'wb') as f:
                    for chunk in img_response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Enforce minimum image quality
                min_w, min_h = MIN_IMAGE_SIZE
                try:
                    with Image.open(filepath) as pil_img:
                        w, h = pil_img.size
                        if w < min_w or h < min_h:
                            os.remove(filepath)
                            print(f"  Too small ({w}x{h}, need {min_w}x{min_h}), trying next...")
                            continue
                except Exception:
                    pass

                file_size = os.path.getsize(filepath) / 1024  # Size in KB
                print(f"✅ Downloaded: {filename} ({file_size:.1f} KB)")
                downloaded += 1
                
                # Small delay to be respectful to servers
                time.sleep(0.5)
                
            except Exception as e:
                print(f"  Failed (result {result_idx}): {e} — trying next...")
                continue
        
        if downloaded < count:
            print(f"⚠️ Only got {downloaded}/{count} images (ran out of results)")
        print(f"\n🎉 Successfully downloaded {downloaded} images to {download_folder}")
        return download_folder


class ImageDownloader:
    """Combined image downloader that tries SerpAPI (Google) first, then Brave as fallback."""
    
    def __init__(self, serpapi_key=None, brave_key=None):
        self.serpapi = SerpAPIImageDownloader(serpapi_key) if serpapi_key else None
        self.brave = BraveImageDownloader(brave_key) if brave_key else None
        self.base_folder = os.path.join(os.getcwd(), "downloads")
    
    def get_file_extension(self, url, content_type=None):
        """Get appropriate file extension from URL or content type"""
        parsed_url = urlparse(url)
        path = parsed_url.path
        if path and '.' in path:
            ext = path.split('.')[-1].lower().split('?')[0]
            if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                return f".{ext}"
        
        if content_type:
            if 'jpeg' in content_type or 'jpg' in content_type:
                return '.jpg'
            elif 'png' in content_type:
                return '.png'
            elif 'gif' in content_type:
                return '.gif'
            elif 'webp' in content_type:
                return '.webp'
        
        return '.jpg'
    
    def download_images(self, query, count=50, download_folder=None):
        """Download images, trying SerpAPI first then Brave."""
        results = []
        source = None
        
        # Try SerpAPI first
        if self.serpapi:
            results = self.serpapi.search_images(query, count * 3)
            if results:
                source = 'serpapi'
        
        # Fall back to Brave
        if not results and self.brave:
            print("Falling back to Brave Search...")
            results = self.brave.search_images(query, count * 3)
            if results:
                source = 'brave'
        
        if not results:
            print(f"No results from any source for '{query}'")
            return None
        
        # Create folder
        if download_folder is None:
            folder_name = query.replace(' ', '_').replace('/', '_').replace('\\', '_')
            download_folder = os.path.join(self.base_folder, folder_name)
        os.makedirs(download_folder, exist_ok=True)
        
        downloaded = 0
        result_idx = 0
        while downloaded < count and result_idx < len(results):
            img = results[result_idx]
            result_idx += 1
            
            try:
                # Get image URL based on source
                if source == 'serpapi':
                    img_url = img.get('original')
                    if not img_url:
                        img_url = img.get('thumbnail')
                else:  # Brave
                    img_url = None
                    if 'properties' in img and isinstance(img['properties'], dict):
                        img_url = img['properties'].get('url')
                    if not img_url and 'thumbnail' in img and isinstance(img['thumbnail'], dict):
                        img_url = img['thumbnail'].get('src')
                    if not img_url:
                        img_url = img.get('src')
                
                if not img_url:
                    continue
                
                # Download the image
                img_response = requests.get(img_url, timeout=15, stream=True, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                img_response.raise_for_status()
                
                # Get extension and create filename
                content_type = img_response.headers.get('content-type', '')
                file_ext = self.get_file_extension(img_url, content_type)
                folder_name = os.path.basename(download_folder)
                filename = f"{folder_name}_{downloaded+1:02d}{file_ext}"
                filepath = os.path.join(download_folder, filename)
                
                # Save the image
                with open(filepath, 'wb') as f:
                    for chunk in img_response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Verify minimum quality
                min_w, min_h = MIN_IMAGE_SIZE
                try:
                    with Image.open(filepath) as pil_img:
                        w, h = pil_img.size
                        if w < min_w or h < min_h:
                            os.remove(filepath)
                            continue
                except Exception:
                    pass
                
                file_size = os.path.getsize(filepath) / 1024
                print(f"✅ Downloaded: {filename} ({file_size:.1f} KB)")
                downloaded += 1
                time.sleep(0.3)
                
            except Exception as e:
                continue
        
        if downloaded < count:
            print(f"⚠️ Only got {downloaded}/{count} images")
        print(f"Downloaded {downloaded} images to {download_folder}")
        return download_folder


def main():
    # Get API key from environment variable
    API_KEY = os.getenv('BRAVE_API_KEY')
    
    if not API_KEY:
        print("Error: BRAVE_API_KEY not found in environment variables.")
        print("Please create a .env file with your API key or set the environment variable.")
        return
    
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
                os.startfile(folder)  

if __name__ == "__main__":
    main()