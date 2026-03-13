"""
Script Handler - Transcribes audio narration using Groq Whisper, segments
the transcript into numbered sections with accurate word-level timestamps,
and generates descriptive image search queries via Groq AI.
"""

import re
import os
import sys
import json
import math
import time
from mutagen import File as AudioFile
from dotenv import load_dotenv
from openai import OpenAI
import google.generativeai as genai

# Load env from project root
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in .env file")

groq_client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")

# Configure Gemini if available
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), 'settings.json')

def load_settings():
    """Load settings from settings.json, returning defaults if not found."""
    defaults = {
        'resolution': '1080p',
        'fps': 24,
        'max_image_duration': 8,
        'ken_burns_scale': 1.15,
        'min_image_quality': '360p',
        'bitrate': '5000k',
        'transition_duration': 0.5,
        'transition_types': ['crossfade'],
        'description': '',
        'tags': [],
    }
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
            saved = json.load(f)
        defaults.update(saved)
    return defaults


def get_audio_duration(audio_path):
    """Get duration of an audio file in seconds using mutagen."""
    audio = AudioFile(audio_path)
    if audio is None or audio.info is None:
        raise ValueError(f"Could not read audio file: {audio_path}")
    return audio.info.length


def transcribe_audio(audio_path, description=''):
    """
    Transcribe audio using Groq's Whisper API with word-level timestamps.
    Falls back to OpenAI Whisper if Groq fails with a server error.
    If a description is provided, it's used as a prompt to guide transcription
    accuracy (correcting names, places, etc.).
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    print(f"Transcribing audio: {audio_path}")
    if description:
        print(f"Using description to guide transcription...")
    print("This may take a moment...")

    # Try Groq models in order: turbo first (faster), then regular (more stable)
    groq_models = ['whisper-large-v3-turbo', 'whisper-large-v3']
    response = None
    retry_delay = 5  # seconds
    last_error = None
    
    for model in groq_models:
        groq_kwargs = {
            'model': model,
            'response_format': 'verbose_json',
            'timestamp_granularities': ['word', 'segment'],
        }
        if description:
            groq_kwargs['prompt'] = description[:810]
        
        try:
            with open(audio_path, 'rb') as audio_file:
                groq_kwargs['file'] = audio_file
                response = groq_client.audio.transcriptions.create(**groq_kwargs)
            print(f"Transcribed using Groq {model}")
            break  # Success, exit model loop
        except Exception as e:
            last_error = e
            error_str = str(e)
            is_server_error = '500' in error_str or 'Internal Server Error' in error_str or '503' in error_str
            
            if is_server_error:
                print(f"Groq {model} failed with server error, trying next model...")
                time.sleep(retry_delay)
                continue
            else:
                raise
    
    # If all Groq models failed, raise error
    if response is None:
        raise RuntimeError("All Groq Whisper models failed with server errors") from last_error

    full_text = response.text
    words = []
    if hasattr(response, 'words') and response.words:
        for w in response.words:
            words.append({
                "word": w.word if hasattr(w, 'word') else w.get('word', ''),
                "start": w.start if hasattr(w, 'start') else w.get('start', 0),
                "end": w.end if hasattr(w, 'end') else w.get('end', 0),
            })

    segments = []
    if hasattr(response, 'segments') and response.segments:
        for seg in response.segments:
            segments.append({
                "text": seg.text if hasattr(seg, 'text') else seg.get('text', ''),
                "start": seg.start if hasattr(seg, 'start') else seg.get('start', 0),
                "end": seg.end if hasattr(seg, 'end') else seg.get('end', 0),
            })

    print(f"Transcription complete: {len(words)} words, {len(segments)} segments")
    return full_text, words, segments


def group_segments_into_sections(segments, max_segments_per_section=3):
    """
    Group Whisper segments (roughly sentences) into sections.
    Each section gets accurate start/end times from the first/last segment.
    """
    if not segments:
        return []

    sections = []
    current_segs = [segments[0]]

    for i in range(1, len(segments)):
        if len(current_segs) >= max_segments_per_section:
            text = ' '.join(s['text'].strip() for s in current_segs)
            sections.append({
                "text": text,
                "start_time": current_segs[0]['start'],
                "end_time": current_segs[-1]['end'],
            })
            current_segs = [segments[i]]
        else:
            current_segs.append(segments[i])

    if current_segs:
        text = ' '.join(s['text'].strip() for s in current_segs)
        sections.append({
            "text": text,
            "start_time": current_segs[0]['start'],
            "end_time": current_segs[-1]['end'],
        })

    return sections


def group_words_into_sections(words, audio_duration, max_sentences_per_section=3):
    """
    Fallback: group words into sections by detecting sentence boundaries
    (periods, question marks, exclamation marks) in the word stream.
    Uses actual word timestamps for accurate timing.
    """
    if not words:
        return []

    # Build sentences from words using punctuation
    sentences = []
    current_words = []

    for w in words:
        current_words.append(w)
        if w['word'].rstrip().endswith(('.', '!', '?')):
            sentences.append({
                "text": ' '.join(cw['word'] for cw in current_words),
                "start_time": current_words[0]['start'],
                "end_time": current_words[-1]['end'],
            })
            current_words = []

    # Any remaining words form the last sentence
    if current_words:
        sentences.append({
            "text": ' '.join(cw['word'] for cw in current_words),
            "start_time": current_words[0]['start'],
            "end_time": current_words[-1]['end'],
        })

    # Group sentences into sections
    sections = []
    current_group = [sentences[0]]

    for i in range(1, len(sentences)):
        if len(current_group) >= max_sentences_per_section:
            text = ' '.join(s['text'].strip() for s in current_group)
            sections.append({
                "text": text,
                "start_time": current_group[0]['start_time'],
                "end_time": current_group[-1]['end_time'],
            })
            current_group = [sentences[i]]
        else:
            current_group.append(sentences[i])

    if current_group:
        text = ' '.join(s['text'].strip() for s in current_group)
        sections.append({
            "text": text,
            "start_time": current_group[0]['start_time'],
            "end_time": current_group[-1]['end_time'],
        })

    return sections


def generate_sections_with_groq(segments, full_transcript, settings):
    """
    Send the script + Whisper timestamps to Groq to split into visual sections.
    The description field IS the script — used as ground truth text.
    Whisper timestamps are used only for timing reference.
    The AI determines natural section durations based on content flow.
    """
    max_dur = settings.get('max_image_duration', 12)
    tags = settings.get('tags', [])
    description = settings.get('description', '')

    # Build timing reference from Whisper segments
    timing_ref = ""
    for seg in segments:
        timing_ref += f"[{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['text'].strip()}\n"

    first_start = segments[0]['start'] if segments else 0.0
    last_end = segments[-1]['end'] if segments else 0.0

    tags_block = ""
    if tags:
        tags_block = f"\nIMPORTANT TAGS — These people, clubs, and countries MUST get their own image sections whenever mentioned or relevant:\n{', '.join(tags)}\n"

    # Use the script (description) as the authoritative text
    script_text = description.strip() if description.strip() else full_transcript

    prompt = f"""You are a video editor deciding which images to show in a YouTube video, and WHEN to show them.
{tags_block}
HERE IS THE EXACT SCRIPT (this is the authoritative text — use this for all text content):

{script_text}

HERE ARE THE AUDIO TIMESTAMPS from speech recognition (use ONLY for timing — the text may have errors):

{timing_ref}

The audio runs from {first_start:.1f}s to {last_end:.1f}s.

Your job: Split the SCRIPT into visual SECTIONS. Each section = one image shown on screen.
Match each section of the script to the appropriate timestamps by aligning the content.

CRITICAL RULES:
1. Use the SCRIPT text as the definitive text — ignore any misspellings in the timestamps section.
2. EVERY time a person's name is mentioned, they MUST get their own section — even if brief.
3. EVERY time a football team or club is mentioned by name, it MUST get its own section.
4. CONTEXT MATTERS: Always include the correct team/era/event context in search queries.
5. NATURAL DURATION: Let the section duration FLOW with the narration. A section should last as long as the narrator talks about that topic:
   - Quick name mention (2-4 seconds): person briefly mentioned in passing
   - Medium discussion (5-10 seconds): topic explained with some detail
   - Extended coverage (10-{max_dur} seconds): major topic or detailed explanation
   - LISTEN to the pacing — match the image timing to when the narrator naturally moves to the next topic
6. The images MUST match what the narrator is saying AT THAT MOMENT.
7. Align timestamps by matching script content to the speech recognition text.
8. Sections must be contiguous — no gaps, no overlaps.
9. SEARCH QUERY RULES:
   - Use the person's FULL NAME (e.g. "John Obi Mikel" not "Mikel")
   - Include team/club context (e.g. "John Obi Mikel Chelsea midfielder")
   - For events use descriptive terms (e.g. "Chelsea vs Barcelona Champions League 2012")
   - Keep queries 3-7 words, specific, likely to return high-quality images
   - Do NOT end queries with "photos" or "images"
   - NEVER use the same search query twice — every section MUST have a unique query. Vary by adding context like position, era, event, team, or action.{chr(10) + '10. The following tags MUST have their images shown: ' + ', '.join(tags) if tags else ''}

RESPOND WITH ONLY a JSON array of objects, each with:
- "start_time": number (seconds)
- "end_time": number (seconds)
- "search_query": string (unique descriptive image search query — NO DUPLICATES)
- "text": string (the exact SCRIPT text for this section)

Example:
[
  {{"start_time": 0.0, "end_time": 5.2, "search_query": "Chelsea FC Stamford Bridge stadium", "text": "Chelsea Football Club has a rich history at Stamford Bridge..."}},
  {{"start_time": 5.2, "end_time": 12.8, "search_query": "Didier Drogba Chelsea celebration goal", "text": "Players like Didier Drogba defined an era..."}}
]"""

    print("Generating sections with Groq AI...")
    response = groq_client.chat.completions.create(
        model='llama-3.3-70b-versatile',
        messages=[
            {"role": "system", "content": "You are a professional video editor. Output only valid JSON. Be precise with timestamps. Match section durations to the natural flow of the narration."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    text = response.choices[0].message.content.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

    sections = json.loads(text)

    # Validate queries and enforce uniqueness
    seen_queries = set()
    for i, s in enumerate(sections):
        q = s.get('search_query', '').strip()
        if not q:
            q = 'related topic'
        # Deduplicate: append context variation if query was already used
        base_q = q
        counter = 2
        while q.lower() in seen_queries:
            q = f"{base_q} variant {counter}"
            counter += 1
        seen_queries.add(q.lower())
        sections[i]['search_query'] = q

    return sections


def generate_sections_with_gemini(segments, full_transcript, settings):
    """
    Send the script + Whisper timestamps to Gemini to split into visual sections.
    The description field IS the script — used as ground truth text.
    Whisper timestamps are used only for timing reference.
    The AI determines natural section durations based on content flow.
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not configured")
    
    max_dur = settings.get('max_image_duration', 12)
    tags = settings.get('tags', [])
    description = settings.get('description', '')

    # Build timing reference from Whisper segments
    timing_ref = ""
    for seg in segments:
        timing_ref += f"[{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['text'].strip()}\n"

    first_start = segments[0]['start'] if segments else 0.0
    last_end = segments[-1]['end'] if segments else 0.0

    tags_block = ""
    if tags:
        tags_block = f"\nIMPORTANT TAGS — These people, clubs, and countries MUST get their own image sections whenever mentioned or relevant:\n{', '.join(tags)}\n"

    # Use the script (description) as the authoritative text
    script_text = description.strip() if description.strip() else full_transcript

    prompt = f"""You are a video editor deciding which images to show in a YouTube video, and WHEN to show them.
{tags_block}
HERE IS THE EXACT SCRIPT (this is the authoritative text — use this for all text content):

{script_text}

HERE ARE THE AUDIO TIMESTAMPS from speech recognition (use ONLY for timing — the text may have errors):

{timing_ref}

The audio runs from {first_start:.1f}s to {last_end:.1f}s.

Your job: Split the SCRIPT into visual SECTIONS. Each section = one image shown on screen.
Match each section of the script to the appropriate timestamps by aligning the content.

CRITICAL RULES:
1. Use the SCRIPT text as the definitive text — ignore any misspellings in the timestamps section.
2. EVERY time a person's name is mentioned, they MUST get their own section — even if brief.
3. EVERY time a football team or club is mentioned by name, it MUST get its own section.
4. CONTEXT MATTERS: Always include the correct team/era/event context in search queries.
5. NATURAL DURATION: Let the section duration FLOW with the narration. A section should last as long as the narrator talks about that topic:
   - Quick name mention (2-4 seconds): person briefly mentioned in passing
   - Medium discussion (5-10 seconds): topic explained with some detail
   - Extended coverage (10-{max_dur} seconds): major topic or detailed explanation
   - LISTEN to the pacing — match the image timing to when the narrator naturally moves to the next topic
6. The images MUST match what the narrator is saying AT THAT MOMENT.
7. Align timestamps by matching script content to the speech recognition text.
8. Sections must be contiguous — no gaps, no overlaps.
9. SEARCH QUERY RULES:
   - Use the person's FULL NAME (e.g. "John Obi Mikel" not "Mikel")
   - Include team/club context (e.g. "John Obi Mikel Chelsea midfielder")
   - For events use descriptive terms (e.g. "Chelsea vs Barcelona Champions League 2012")
   - Keep queries 3-7 words, specific, likely to return high-quality images
   - Do NOT end queries with "photos" or "images"
   - NEVER use the same search query twice — every section MUST have a unique query. Vary by adding context like position, era, event, team, or action.{chr(10) + '10. The following tags MUST have their images shown: ' + ', '.join(tags) if tags else ''}

RESPOND WITH ONLY a JSON array of objects, each with:
- "start_time": number (seconds)
- "end_time": number (seconds)
- "search_query": string (unique descriptive image search query — NO DUPLICATES)
- "text": string (the exact SCRIPT text for this section)

Example:
[
  {{"start_time": 0.0, "end_time": 5.2, "search_query": "Chelsea FC Stamford Bridge stadium", "text": "Chelsea Football Club has a rich history at Stamford Bridge..."}},
  {{"start_time": 5.2, "end_time": 12.8, "search_query": "Didier Drogba Chelsea celebration goal", "text": "Players like Didier Drogba defined an era..."}}
]"""

    print("Generating sections with Gemini AI...")
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.3,
        )
    )

    text = response.text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

    sections = json.loads(text)

    # Validate queries and enforce uniqueness
    seen_queries = set()
    for i, s in enumerate(sections):
        q = s.get('search_query', '').strip()
        if not q:
            q = 'related topic'
        # Deduplicate: append context variation if query was already used
        base_q = q
        counter = 2
        while q.lower() in seen_queries:
            q = f"{base_q} variant {counter}"
            counter += 1
        seen_queries.add(q.lower())
        sections[i]['search_query'] = q

    return sections


def generate_sections(segments, full_transcript, settings):
    """
    Try Gemini first for sectioning, fall back to Groq on failure.
    """
    # Try Gemini first
    if GEMINI_API_KEY:
        try:
            return generate_sections_with_gemini(segments, full_transcript, settings)
        except Exception as e:
            print(f"Gemini failed: {e}")
            print("Falling back to Groq...")
    
    # Fall back to Groq
    return generate_sections_with_groq(segments, full_transcript, settings)


def process_audio(audio_path):
    """
    Main function: transcribes audio, sends timestamped segments to Groq
    which intelligently splits into visual sections (one image per person/topic),
    and returns the final sections list.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    settings = load_settings()
    description = settings.get('description', '')
    print(f"Settings loaded (script: {'yes (' + str(len(description)) + ' chars)' if description else 'none'}, tags: {len(settings.get('tags', []))})") 

    audio_duration = get_audio_duration(audio_path)
    print(f"Audio duration: {audio_duration:.1f} seconds")

    # Transcribe the audio (pass description to guide Whisper)
    full_text, words, segments = transcribe_audio(audio_path, description=settings.get('description', ''))

    print(f"\nTranscript preview: {full_text[:200]}...")

    # We need segments with timestamps for the AI sectioning
    if not segments:
        # Build pseudo-segments from words as fallback
        if words:
            print(f"\nNo segments from Whisper, building from {len(words)} words...")
            current_words = []
            segments = []
            for w in words:
                current_words.append(w)
                if w['word'].rstrip().endswith(('.', '!', '?')) or len(current_words) >= 20:
                    segments.append({
                        "text": ' '.join(cw['word'] for cw in current_words),
                        "start": current_words[0]['start'],
                        "end": current_words[-1]['end'],
                    })
                    current_words = []
            if current_words:
                segments.append({
                    "text": ' '.join(cw['word'] for cw in current_words),
                    "start": current_words[0]['start'],
                    "end": current_words[-1]['end'],
                })
        else:
            raise ValueError("Transcription returned no words or segments")

    # Filter out Whisper hallucinations — segments with nonsense text
    # Whisper often hallucinates garbage when audio has silence/noise at the end
    import unicodedata
    def _is_hallucinated(text):
        """Detect likely hallucinated segments from Whisper."""
        t = text.strip()
        if not t:
            return True
        # High ratio of non-Latin characters suggests hallucination
        non_ascii = sum(1 for c in t if ord(c) > 127)
        if len(t) > 0 and non_ascii / len(t) > 0.3:
            return True
        # Very short meaningless fragments (single numbers, single letters)
        if len(t) <= 2:
            return True
        return False

    original_count = len(segments)
    segments = [s for s in segments if not _is_hallucinated(s['text'])]
    if len(segments) < original_count:
        print(f"\nFiltered {original_count - len(segments)} hallucinated segments (keeping {len(segments)})")

    print(f"\nSending {len(segments)} timestamped segments for intelligent sectioning...")
    ai_sections = generate_sections(segments, full_text, settings)
    print(f"AI created {len(ai_sections)} visual sections")

    # Fix timing: ensure sections are contiguous and cover full audio
    if ai_sections:
        ai_sections[0]['start_time'] = 0.0
        for i in range(len(ai_sections) - 1):
            # Close gaps by extending previous section
            next_start = ai_sections[i + 1]['start_time']
            if ai_sections[i]['end_time'] < next_start:
                ai_sections[i]['end_time'] = next_start
            # Fix overlaps by trimming current section
            elif ai_sections[i]['end_time'] > next_start:
                ai_sections[i]['end_time'] = next_start
        ai_sections[-1]['end_time'] = audio_duration

    # Build final sections array
    sections = []
    for i, raw in enumerate(ai_sections):
        duration = raw['end_time'] - raw['start_time']
        if duration <= 0:
            continue

        section = {
            "number": len(sections) + 1,
            "search_query": raw['search_query'],
            "text": raw.get('text', ''),
            "start_time": round(raw['start_time'], 2),
            "end_time": round(raw['end_time'], 2),
            "images_needed": 1,  # One image per section now
        }
        sections.append(section)

    # Print summary
    total_images = sum(s['images_needed'] for s in sections)
    print(f"\n{'='*60}")
    print(f"SCRIPT SECTIONS ({len(sections)} total, {total_images} images to download)")
    print(f"{'='*60}")
    for s in sections:
        duration = s['end_time'] - s['start_time']
        print(f"\n  [{s['number']:02d}] {s['search_query']}")
        print(f"       Time: {s['start_time']:.1f}s - {s['end_time']:.1f}s ({duration:.1f}s)")
        print(f"       Text: {s['text'][:80]}{'...' if len(s['text']) > 80 else ''}")

    return sections


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python handlescript.py <audio_file>")
        print("Example: python handlescript.py narration.mp3")
        sys.exit(1)

    audio_path = sys.argv[1]

    sections = process_audio(audio_path)

    # Save sections to JSON
    output_dir = os.path.dirname(audio_path) or '.'
    output_path = os.path.join(output_dir, 'sections.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(sections, f, indent=2)
    print(f"\nSections saved to {output_path}")

    # Generate and save video title from first section's search query
    first_query = sections[0]['search_query'].replace(' photos', '').strip()
    title = re.sub(r'[^a-zA-Z0-9]+', '_', first_query).strip('_').lower() + '.mp4'
    title_path = os.path.join(output_dir, 'video_title.txt')
    with open(title_path, 'w', encoding='utf-8') as f:
        f.write(title)
    print(f"Video title: {title}")
    print(f"Title saved to {title_path}")
