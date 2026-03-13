"""
Video Builder - Combines downloaded section images with the audio narration
to produce a final video. Each section's images are shown for that section's
timestamp duration, with smooth crossfade transitions.
"""

import os
import sys
import json
import glob
import random
import numpy as np
import requests
import time
from moviepy import (
    ImageClip, AudioFileClip, concatenate_videoclips,
    ColorClip, VideoClip, CompositeVideoClip
)
from moviepy.video.fx import CrossFadeIn, FadeIn, FadeOut, SlideIn, SlideOut
from PIL import Image
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


# ---- Settings loading ----
SETTINGS_PATH = os.path.join(os.path.dirname(__file__), 'settings.json')

def load_settings():
    """Load settings from settings.json, returning defaults if not found."""
    defaults = {
        'resolution': '1080p',
        'fps': 24,
        'ken_burns_scale': 1.15,
        'transition_duration': 0.5,
        'transition_types': ['crossfade'],
        'bitrate': '5000k',
    }
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
            saved = json.load(f)
        defaults.update(saved)
    return defaults

# Load settings at module level so all functions can use them
_settings = load_settings()

# Output video settings (from settings.json)
if _settings['resolution'] == '720p':
    VIDEO_WIDTH = 1280
    VIDEO_HEIGHT = 720
else:
    VIDEO_WIDTH = 1920
    VIDEO_HEIGHT = 1080

FPS = int(_settings['fps'])
CROSSFADE_DURATION = float(_settings['transition_duration'])
KB_SCALE = float(_settings['ken_burns_scale'])
TRANSITION_TYPES = _settings['transition_types']
BITRATE = _settings['bitrate']

# Cache for downloaded fallback images
_fallback_cache = {}


def get_main_subject():
    """Extract the main subject from settings (first tag or from description)."""
    settings = load_settings()
    tags = settings.get('tags', [])
    if tags:
        return tags[0]  # First tag is usually the main subject
    
    # Try to extract from description (first capitalized name-like words)
    description = settings.get('description', '')
    if description:
        # Return first few words as fallback subject
        words = description.split()[:3]
        return ' '.join(words) if words else None
    return None


def download_fallback_image(subject, folder_path):
    """Download a fallback image for the given subject using SerpAPI or Brave."""
    if not subject:
        return None
    
    # Check cache first
    cache_key = subject.lower()
    if cache_key in _fallback_cache and os.path.exists(_fallback_cache[cache_key]):
        return _fallback_cache[cache_key]
    
    serpapi_key = os.getenv('SERPAPI_API_KEY')
    brave_key = os.getenv('BRAVE_API_KEY')
    
    if not serpapi_key and not brave_key:
        return None
    
    print(f"  Downloading fallback image for: {subject}")
    
    # Try SerpAPI first
    img_url = None
    if serpapi_key:
        try:
            params = {
                "engine": "google_images",
                "q": subject,
                "num": 5,
                "api_key": serpapi_key,
                "safe": "off",
                "imgsz": "l",
            }
            response = requests.get("https://serpapi.com/search", params=params, timeout=15)
            if response.status_code == 200:
                results = response.json().get('images_results', [])
                if results:
                    img_url = results[0].get('original')
        except Exception:
            pass
    
    # Fall back to Brave
    if not img_url and brave_key:
        try:
            headers = {"Accept": "application/json", "X-Subscription-Token": brave_key}
            params = {"q": subject, "count": 5, "safesearch": "off", "size": "Large"}
            response = requests.get("https://api.search.brave.com/res/v1/images/search", 
                                   headers=headers, params=params, timeout=15)
            if response.status_code == 200:
                results = response.json().get('results', [])
                if results:
                    img = results[0]
                    if 'properties' in img and isinstance(img['properties'], dict):
                        img_url = img['properties'].get('url')
                    if not img_url:
                        img_url = img.get('src')
        except Exception:
            pass
    
    if not img_url:
        return None
    
    # Download the image
    try:
        img_response = requests.get(img_url, timeout=15, stream=True, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        img_response.raise_for_status()
        
        # Determine extension
        content_type = img_response.headers.get('content-type', '')
        ext = '.jpg'
        if 'png' in content_type:
            ext = '.png'
        elif 'webp' in content_type:
            ext = '.webp'
        
        # Save to folder
        safe_name = subject.replace(' ', '_').replace('/', '_')[:30]
        filepath = os.path.join(folder_path, f"_fallback_{safe_name}{ext}")
        
        with open(filepath, 'wb') as f:
            for chunk in img_response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Verify it's valid
        if is_valid_image(filepath):
            _fallback_cache[cache_key] = filepath
            print(f"  ✅ Downloaded fallback: {os.path.basename(filepath)}")
            return filepath
        else:
            os.remove(filepath)
            return None
            
    except Exception as e:
        print(f"  Failed to download fallback: {e}")
        return None


def is_valid_image(image_path):
    """Check if an image file is valid and not corrupted."""
    try:
        with Image.open(image_path) as img:
            img.verify()  # Verify it's a valid image
        # Re-open and try to load pixels (verify doesn't catch all issues)
        with Image.open(image_path) as img:
            img.load()
        return True
    except Exception:
        return False


def get_images_from_folder(folder_path):
    """Get sorted list of valid image files from a folder. Downloads fallback for corrupt images."""
    if not folder_path or not os.path.exists(folder_path):
        return []

    extensions = ('*.jpg', '*.jpeg', '*.png', '*.webp', '*.gif')
    images = []
    for ext in extensions:
        images.extend(glob.glob(os.path.join(folder_path, ext)))

    images.sort()
    
    # Filter out corrupted images, replacing with fallback if possible
    valid_images = []
    main_subject = get_main_subject()
    
    for img_path in images:
        # Skip any existing fallback images in the count
        if '_fallback_' in os.path.basename(img_path):
            if is_valid_image(img_path):
                valid_images.append(img_path)
            continue
            
        if is_valid_image(img_path):
            valid_images.append(img_path)
        else:
            print(f"  Warning: Corrupt image: {os.path.basename(img_path)}")
            # Try to download a fallback image of the main subject
            if main_subject:
                fallback = download_fallback_image(main_subject, folder_path)
                if fallback:
                    valid_images.append(fallback)
                else:
                    print(f"  Could not download fallback, skipping...")
            else:
                print(f"  No main subject for fallback, skipping...")
    
    return valid_images


def prepare_ken_burns_image(image_path):
    """
    Load and scale image larger than the video frame so Ken Burns
    has room to zoom/pan.
    """
    img = Image.open(image_path).convert('RGB')
    img_w, img_h = img.size

    target_w = int(VIDEO_WIDTH * KB_SCALE)
    target_h = int(VIDEO_HEIGHT * KB_SCALE)

    # Cover-scale to the larger target
    ratio = max(target_w / img_w, target_h / img_h)
    new_w = int(img_w * ratio)
    new_h = int(img_h * ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    # Center crop to the scaled dimensions
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    img = img.crop((left, top, left + target_w, top + target_h))

    return np.array(img)


def create_ken_burns_clip(image_path, duration):
    """
    Create a clip with Ken Burns (slow zoom + pan) motion.
    A random motion direction is chosen for each image.
    """
    img_array = prepare_ken_burns_image(image_path)
    img_h, img_w = img_array.shape[:2]

    # Random start/end zoom (1.0 = full video size, KB_SCALE = full image)
    zoom_start = random.uniform(1.0, 1.08)
    zoom_end = random.uniform(1.0, 1.08)
    # Ensure visible motion
    if abs(zoom_start - zoom_end) < 0.03:
        zoom_end = zoom_start + random.choice([-0.06, 0.06])
        zoom_end = max(1.0, min(zoom_end, KB_SCALE - 0.01))

    # Random pan positions (0..1 across available space)
    pan_x_start = random.uniform(0.15, 0.85)
    pan_x_end = random.uniform(0.15, 0.85)
    pan_y_start = random.uniform(0.15, 0.85)
    pan_y_end = random.uniform(0.15, 0.85)

    def make_frame(t):
        progress = t / max(duration, 0.001)
        # Smooth ease-in-out
        progress = 0.5 - 0.5 * np.cos(np.pi * progress)

        zoom = zoom_start + (zoom_end - zoom_start) * progress
        crop_w = min(int(VIDEO_WIDTH * zoom), img_w)
        crop_h = min(int(VIDEO_HEIGHT * zoom), img_h)

        avail_x = max(img_w - crop_w, 0)
        avail_y = max(img_h - crop_h, 0)

        px = pan_x_start + (pan_x_end - pan_x_start) * progress
        py = pan_y_start + (pan_y_end - pan_y_start) * progress

        x = int(avail_x * px)
        y = int(avail_y * py)

        cropped = img_array[y:y + crop_h, x:x + crop_w]
        resized = Image.fromarray(cropped).resize(
            (VIDEO_WIDTH, VIDEO_HEIGHT), Image.LANCZOS
        )
        return np.array(resized)

    clip = VideoClip(make_frame, duration=duration)
    clip = clip.with_fps(FPS)
    return clip


def _pick_transition_effect(duration):
    """
    Pick a random transition effect from the configured types.
    Returns a list of moviepy effects to apply to the clip.
    """
    if not TRANSITION_TYPES or 'none' in TRANSITION_TYPES:
        available = [t for t in TRANSITION_TYPES if t != 'none']
        if not available:
            return []
        chosen = random.choice(available)
    else:
        chosen = random.choice(TRANSITION_TYPES)

    if chosen == 'crossfade':
        return [CrossFadeIn(duration)]
    elif chosen == 'fade_black':
        return [FadeIn(duration)]
    elif chosen == 'slide_left':
        return [SlideIn(duration, 'right')]  # slides in from right = appears from left
    elif chosen == 'slide_right':
        return [SlideIn(duration, 'left')]
    elif chosen == 'slide_up':
        return [SlideIn(duration, 'bottom')]
    elif chosen == 'slide_down':
        return [SlideIn(duration, 'top')]
    else:
        return [CrossFadeIn(duration)]


def build_section_clip(image_paths, duration):
    """
    Build a clip for one section with Ken Burns on every image
    and crossfade transitions between them.
    """
    if not image_paths:
        return ColorClip(
            size=(VIDEO_WIDTH, VIDEO_HEIGHT),
            color=(0, 0, 0)
        ).with_duration(duration)

    num_images = len(image_paths)

    if num_images == 1:
        return create_ken_burns_clip(image_paths[0], duration)

    # Account for crossfade overlaps when calculating per-image duration
    total_overlap = (num_images - 1) * CROSSFADE_DURATION
    time_per_image = (duration + total_overlap) / num_images

    # Ensure each image shows for at least 1.5 s (room for crossfade)
    if time_per_image < 1.5 and num_images > 1:
        num_images = max(1, int(duration / 1.5))
        image_paths = image_paths[:num_images]
        if num_images == 1:
            return create_ken_burns_clip(image_paths[0], duration)
        total_overlap = (num_images - 1) * CROSSFADE_DURATION
        time_per_image = (duration + total_overlap) / num_images

    # Build each Ken Burns clip with transition, placed at staggered starts
    clips = []
    current_start = 0
    for idx, img_path in enumerate(image_paths):
        clip = create_ken_burns_clip(img_path, time_per_image)
        if idx > 0:
            effects = _pick_transition_effect(CROSSFADE_DURATION)
            if effects:
                clip = clip.with_effects(effects)
        clip = clip.with_start(current_start)
        clips.append(clip)
        current_start += time_per_image - CROSSFADE_DURATION

    return CompositeVideoClip(
        clips, size=(VIDEO_WIDTH, VIDEO_HEIGHT)
    ).with_duration(duration)


def build_video(sections, section_folders, audio_path, output_path="output.mp4"):
    """
    Main function: build the final video from sections, their images, and audio.

    Args:
        sections: list of section dicts from handlescript.py
        section_folders: dict mapping section number -> image folder path
        audio_path: path to the narration audio file
        output_path: where to save the final video
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    print(f"\n{'='*60}")
    print("BUILDING VIDEO")
    print(f"{'='*60}")
    print(f"Sections: {len(sections)}")
    print(f"Audio: {audio_path}")
    print(f"Output: {output_path}\n")

    # Load audio
    audio = AudioFileClip(audio_path)

    # Build clips for each section
    section_clips = []
    for section in sections:
        number = section['number']
        start = section['start_time']
        end = section['end_time']
        duration = end - start

        # Get images for this section
        folder = section_folders.get(str(number)) or section_folders.get(number)
        images = get_images_from_folder(folder)

        print(f"  Section {number:02d}: {len(images)} images, "
              f"{duration:.1f}s ({start:.1f}s - {end:.1f}s) "
              f"| \"{section['search_query']}\"")

        clip = build_section_clip(images, duration)
        section_clips.append(clip)

    # Concatenate all section clips
    print("\nConcatenating sections...")
    video = concatenate_videoclips(section_clips, method="compose")

    # Attach audio
    video = video.with_audio(audio)

    # Ensure video duration matches audio
    video = video.with_duration(audio.duration)

    # Write the final video
    print(f"Rendering video to {output_path}...")
    video.write_videofile(
        output_path,
        fps=FPS,
        codec='libx264',
        audio_codec='aac',
        bitrate=BITRATE,
        threads=4,
        logger='bar',
        ffmpeg_params=['-pix_fmt', 'yuv420p', '-movflags', '+faststart']
    )

    # Cleanup
    video.close()
    audio.close()
    for clip in section_clips:
        clip.close()

    print(f"\nVideo saved to: {output_path}")
    return output_path


def build_from_files(sections_json, folders_json, audio_path, output_path="output.mp4"):
    """
    Build video from JSON files (produced by handlescript.py and downloader.py).
    """
    with open(sections_json, 'r', encoding='utf-8') as f:
        sections = json.load(f)

    with open(folders_json, 'r', encoding='utf-8') as f:
        section_folders = json.load(f)

    return build_video(sections, section_folders, audio_path, output_path)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python video_builder.py <sections.json> <image_folders.json> <audio_file> [output.mp4]")
        print("Example: python video_builder.py sections.json image_folders.json narration.mp3 final_video.mp4")
        sys.exit(1)

    sections_json = sys.argv[1]
    folders_json = sys.argv[2]
    audio_path = sys.argv[3]
    output = sys.argv[4] if len(sys.argv) > 4 else "output.mp4"

    build_from_files(sections_json, folders_json, audio_path, output)
