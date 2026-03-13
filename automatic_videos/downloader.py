"""
Downloader - Takes the sections array from handlescript.py and downloads
images for each section using the existing Brave Image Downloader.
Each section specifies how many images it needs based on its duration
(1 image per 8 seconds max).
"""

import os
import sys
import json
import time
from datetime import datetime

# Add parent directory to path so we can import the existing downloader
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
from brave_image_downloader import BraveImageDownloader


def download_section_images(sections, output_dir=None):
    """
    Download images for each section using the Brave Image Downloader.
    The number of images per section is determined by section['images_needed'].

    Args:
        sections: list of dicts from handlescript.process_script()
                  Each dict has: number, search_query, text, start_time, end_time, images_needed
        output_dir: base directory to store downloaded images (default: automatic_videos/images/)

    Returns:
        dict mapping section number -> folder path where images were saved
    """
    # Load environment variables for API key
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
    api_key = os.getenv('BRAVE_API_KEY')

    if not api_key:
        raise ValueError(
            "BRAVE_API_KEY not found. Please set it in the .env file "
            "in the project root directory."
        )

    # Set up output directory — unique timestamped folder per generation
    if output_dir is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = os.path.join(os.path.dirname(__file__), f'images_{timestamp}')
    os.makedirs(output_dir, exist_ok=True)

    # Create downloader instance and override its base folder
    downloader = BraveImageDownloader(api_key)
    downloader.base_folder = output_dir

    total_images = sum(s.get('images_needed', 1) for s in sections)
    print(f"\n{'='*60}")
    print(f"DOWNLOADING IMAGES FOR {len(sections)} SECTIONS")
    print(f"Total images to download: {total_images}")
    print(f"Output directory: {output_dir}")
    print(f"{'='*60}\n")

    section_folders = {}

    for section in sections:
        number = section['number']
        query = section['search_query']
        count = section.get('images_needed', 1)
        duration = section['end_time'] - section['start_time']

        print(f"\n--- Section {number:02d}: \"{query}\" ({duration:.1f}s, {count} image(s)) ---")

        # Download the required number of images for this section
        folder = downloader.download_images(query, count=count)

        if folder:
            # Rename the folder to include section number for ordering
            safe_query = query.replace(' ', '_').replace('/', '_').replace('\\', '_')
            numbered_folder_name = f"{number:02d}_{safe_query}"
            numbered_folder = os.path.join(output_dir, numbered_folder_name)

            # If the numbered folder already exists, use it as-is
            if folder != numbered_folder and not os.path.exists(numbered_folder):
                os.rename(folder, numbered_folder)
                folder = numbered_folder

            section_folders[number] = folder
            print(f"Section {number:02d} images saved to: {folder}")
        else:
            print(f"WARNING: No images downloaded for section {number:02d}")
            section_folders[number] = None

        # Be respectful between section downloads
        time.sleep(1)

    # Summary
    successful = sum(1 for v in section_folders.values() if v is not None)
    print(f"\n{'='*60}")
    print(f"DOWNLOAD COMPLETE: {successful}/{len(sections)} sections have images")
    print(f"{'='*60}")

    return section_folders


def download_from_json(json_path, output_dir=None):
    """
    Load sections from a JSON file (produced by handlescript.py) and download images.

    Args:
        json_path: path to sections.json
        output_dir: base directory for images

    Returns:
        dict mapping section number -> folder path
    """
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Sections file not found: {json_path}")

    with open(json_path, 'r', encoding='utf-8') as f:
        sections = json.load(f)

    return download_section_images(sections, output_dir)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python downloader.py <sections.json>")
        print("Example: python downloader.py sections.json")
        sys.exit(1)

    json_path = sys.argv[1]
    section_folders = download_from_json(json_path)

    # Save the folder mapping for video_builder to use
    mapping_path = os.path.join(os.path.dirname(json_path) or '.', 'image_folders.json')
    with open(mapping_path, 'w', encoding='utf-8') as f:
        json.dump(section_folders, f, indent=2)
    print(f"\nFolder mapping saved to {mapping_path}")
