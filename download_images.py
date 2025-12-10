"""
Brave Image Search and Download Tool
Author: DownloadImages from brave
Description: Search for images using Brave Search API and download them locally.
"""

import requests
import os
from urllib.parse import urlparse
import time
from pathlib import Path

class BraveImageDownloader:
    def __init__(self, api_key):
        """Initialize the Brave Image Downloader with API key."""
        self.api_key = api_key
        self.base_url = "https://api.search.brave.com/res/v1/images/search"
        self.headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key
        }
        
    def search_images(self, query, count=20, safesearch="moderate", country="us", search_lang="en"):
        """
        Search for images using Brave Search API.
        
        Args:
            query (str): Search query
            count (int): Number of images to retrieve (max 20)
            safesearch (str): Safe search setting (strict, moderate, off)
            country (str): Country code for search results
            search_lang (str): Language for search results
            
        Returns:
            dict: API response containing image results
        """
        params = {
            "q": query,
            "count": min(count, 20),  # Brave API has a maximum of 20 results per request
            "safesearch": safesearch,
            "country": country,
            "search_lang": search_lang,
            "spellcheck": 1
        }
        
        try:
            print(f"🔍 Searching for '{query}' images...")
            response = requests.get(self.base_url, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            if 'results' in data:
                print(f"✅ Found {len(data['results'])} images for '{query}'")
                return data
            else:
                print("❌ No results found in API response")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Error searching for images: {e}")
            return None
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return None
    
    def get_file_extension(self, url, content_type=None):
        """
        Determine file extension from URL or content type.
        
        Args:
            url (str): Image URL
            content_type (str): HTTP Content-Type header
            
        Returns:
            str: File extension
        """
        # Try to get extension from URL
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()
        
        if path.endswith(('.jpg', '.jpeg', '.png', '.gif')):
            return path.split('.')[-1]
        
        # Try to get extension from content type
        if content_type:
            content_type = content_type.lower()
            if 'jpeg' in content_type or 'jpg' in content_type:
                return 'jpg'
            elif 'png' in content_type:
                return 'png'
            elif 'gif' in content_type:
                return 'gif'
            
        
        # Default to jpg if we can't determine
        return 'jpg'
    
    def download_image(self, image_url, filename, timeout=10):
        """
        Download a single image from URL.
        
        Args:
            image_url (str): URL of the image to download
            filename (str): Local filename to save the image
            timeout (int): Request timeout in seconds
            
        Returns:
            bool: True if download successful, False otherwise
        """
        try:
            response = requests.get(image_url, timeout=timeout, stream=True)
            response.raise_for_status()
            
            # Get file extension based on content type
            content_type = response.headers.get('content-type', '')
            extension = self.get_file_extension(image_url, content_type)
            
            # Add extension if not already present
            if not filename.lower().endswith(f'.{extension}'):
                filename = f"{filename}.{extension}"
            
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            return True
            
        except requests.exceptions.Timeout:
            print(f"⏰ Timeout downloading image from {image_url}")
            return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Error downloading image from {image_url}: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error downloading {image_url}: {e}")
            return False
    
    def download_images(self, query, count=20, download_dir="downloads"):
        """
        Search for images and download them.
        
        Args:
            query (str): Search query
            count (int): Number of images to download
            download_dir (str): Directory to save images
            
        Returns:
            tuple: (successful_downloads, failed_downloads)
        """
        # Create download directory
        Path(download_dir).mkdir(exist_ok=True)
        
        # Search for images
        search_results = self.search_images(query, count)
        if not search_results or 'results' not in search_results:
            print("❌ No search results to download")
            return 0, 0
        
        images = search_results['results']
        successful_downloads = 0
        failed_downloads = 0
        
        print(f"📥 Starting download of {len(images)} images...")
        
        for i, img in enumerate(images, 1):
            # Get image URL - try properties.url first, then thumbnail.src as fallback
            image_url = None
            if 'properties' in img and img['properties'] and 'url' in img['properties']:
                image_url = img['properties']['url']
            elif 'thumbnail' in img and img['thumbnail'] and 'src' in img['thumbnail']:
                image_url = img['thumbnail']['src']
            
            if not image_url:
                print(f"❌ No valid image URL found for result {i}")
                failed_downloads += 1
                continue
            
            # Create filename
            safe_query = "".join(c for c in query if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_query = safe_query.replace(' ', '_')
            filename = os.path.join(download_dir, f"{safe_query}_{i}")
            
            # Download image
            print(f"📥 Downloading image {i}/{len(images)}: {filename}")
            
            if self.download_image(image_url, filename):
                successful_downloads += 1
                print(f"✅ Successfully downloaded image {i}")
            else:
                failed_downloads += 1
                print(f"❌ Failed to download image {i}")
            
            # Add small delay to be respectful to servers
            time.sleep(0.5)
        
        print(f"\n📊 Download Summary:")
        print(f"✅ Successfully downloaded: {successful_downloads} images")
        print(f"❌ Failed downloads: {failed_downloads} images")
        print(f"📁 Images saved in: {os.path.abspath(download_dir)}")
        
        return successful_downloads, failed_downloads

def main():
    """Main function to run the image downloader."""
    # Configuration
    API_KEY = "BSAHie1ZI1j77ZpQVuu3DHLsVuDFnt6"  # Your Brave Search API key
    
    print("🚀 Brave Image Downloader")
    print("=" * 50)
    
    # Get user input
    query = input("🔍 Enter search query: ").strip()
    if not query:
        print("❌ Please enter a valid search query")
        return
    
    try:
        count = int(input("📊 Number of images to download (max 20, default 20): ") or "20")
        count = min(max(count, 1), 20)  # Ensure count is between 1 and 20
    except ValueError:
        count = 20
        print("⚠️ Invalid number entered, using default: 20")
    
    download_dir = input("📁 Download directory (default 'downloads'): ").strip() or "downloads"
    
    print(f"\n🎯 Configuration:")
    print(f"   Query: {query}")
    print(f"   Count: {count}")
    print(f"   Directory: {download_dir}")
    print(f"   API Key: {API_KEY[:10]}...")
    
    # Initialize downloader and start downloading
    downloader = BraveImageDownloader(API_KEY)
    successful, failed = downloader.download_images(query, count, download_dir)
    
    if successful > 0:
        print(f"\n🎉 Download complete! Check the '{download_dir}' folder for your images.")
    else:
        print(f"\n😞 No images were downloaded successfully.")

if __name__ == "__main__":
    main()