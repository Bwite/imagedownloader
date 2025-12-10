"""
Simple Brave Image Search and Download Example
This script demonstrates how to use the Brave Search API to search and download images.
"""

import requests
import os
from pathlib import Path
import time

# Configuration
API_KEY = "BSAHie1ZI1j77ZpQVuu3DHLsVuDFnt6"
QUERY = "curtis 50 cent jackson"  # Change this to your desired search query
COUNT = 20  # Number of images to download (max 20)
BASE_FOLDER = r"C:\Users\Admin\Pictures\BraveSearch"

def search_and_download_images():
    """Search for images using Brave API and download them."""
    
    # Create download directory based on search term
    folder_name = QUERY.replace(' ', '_').replace('/', '_').replace('\\', '_')
    download_dir = os.path.join(BASE_FOLDER, folder_name)
    Path(download_dir).mkdir(parents=True, exist_ok=True)
    print(f"📁 Created folder: {download_dir}")
    
    # Brave Image Search API endpoint
    url = "https://api.search.brave.com/res/v1/images/search"
    
    # Headers for authentication
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip", 
        "X-Subscription-Token": API_KEY
    }
    
    # Search parameters (simplified to avoid 422 error)
    params = {
        "q": QUERY,
        "count": COUNT
    }
    
    print(f"🔍 Searching for '{QUERY}' images using Brave Search API...")
    
    try:
        # Make API request
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if 'results' not in data:
            print("❌ No results found in API response")
            return
        
        images = data['results']
        print(f"✅ Found {len(images)} images")
        
        successful_downloads = 0
        failed_downloads = 0
        
        # Download each image
        for i, img in enumerate(images, 1):
            # Get image URL (try properties.url first, then thumbnail.src)
            image_url = None
            if 'properties' in img and img['properties'] and 'url' in img['properties']:
                image_url = img['properties']['url']
            elif 'thumbnail' in img and img['thumbnail'] and 'src' in img['thumbnail']:
                image_url = img['thumbnail']['src']
            
            if not image_url:
                print(f"❌ No valid URL for image {i}")
                failed_downloads += 1
                continue
            
            # Create filename
            filename = os.path.join(download_dir, f"{folder_name}_{i:02d}.jpg")
            
            print(f"📥 Downloading image {i}/{len(images)}: {os.path.basename(filename)}")
            
            try:
                # Download image
                img_response = requests.get(image_url, timeout=10)
                img_response.raise_for_status()
                
                # Save image
                with open(filename, 'wb') as f:
                    f.write(img_response.content)
                
                successful_downloads += 1
                print(f"✅ Downloaded image {i}")
                
            except Exception as e:
                print(f"❌ Failed to download image {i}: {str(e)}")
                failed_downloads += 1
            
            # Small delay to be respectful
            time.sleep(0.5)
        
        # Summary
        print(f"\n📊 Download Summary:")
        print(f"✅ Successfully downloaded: {successful_downloads} images")
        print(f"❌ Failed downloads: {failed_downloads} images")
        print(f"📁 Images saved in: {download_dir}")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ API request failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    print("🚀 Brave Image Downloader - Simple Example")
    print("=" * 50)
    search_and_download_images()