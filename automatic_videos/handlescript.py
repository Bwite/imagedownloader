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
from mutagen import File as AudioFile
from dotenv import load_dotenv
from openai import OpenAI

# Load env from project root
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

GROQ_API_KEY = os.getenv('GROQ_API_KEY')
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in .env file")

groq_client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")


def get_audio_duration(audio_path):
    """Get duration of an audio file in seconds using mutagen."""
    audio = AudioFile(audio_path)
    if audio is None or audio.info is None:
        raise ValueError(f"Could not read audio file: {audio_path}")
    return audio.info.length


def transcribe_audio(audio_path):
    """
    Transcribe audio using Groq's Whisper API with word-level timestamps.
    Returns the full transcript text and a list of word objects with timestamps.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    print(f"Transcribing audio: {audio_path}")
    print("This may take a moment...")

    with open(audio_path, 'rb') as audio_file:
        response = groq_client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=audio_file,
            response_format="verbose_json",
            timestamp_granularities=["word", "segment"],
        )

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


def generate_sections_with_groq(segments, full_transcript):
    """
    Send the timestamped segments to Groq and let AI decide how to split
    the video into visual sections. Each person mentioned gets their own
    image shown, and context (team, era, event) is respected.
    Returns a list of section dicts with start_time, end_time, search_query.
    """
    # Build timestamped segments for the prompt
    timed_segments = ""
    for i, seg in enumerate(segments):
        timed_segments += f"[{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['text'].strip()}\n"

    prompt = f"""You are a video editor deciding which images to show in a YouTube video, and WHEN to show them.

Here is the FULL transcript with timestamps:

{timed_segments}

Your job: Split this into visual SECTIONS. Each section = one image shown on screen.

CRITICAL RULES:
1. EVERY time a person's name is mentioned, they MUST get their own section with their image — even if it's only 1-2 seconds long. If the narrator says "players like Drogba, Anelka and Kalou", that's THREE separate sections (one image per player).
2. EVERY time a football team or club is mentioned by name (e.g. Chelsea, Barcelona, Real Madrid, Simba SC, TP Mazembe), it MUST get its own section with an image of that team — their badge, stadium, or team photo. If a sentence says "he moved from Chelsea to Liverpool", that requires sections for BOTH clubs.
3. CONTEXT MATTERS: If we talk about Sturridge at Chelsea, the query must be "Daniel Sturridge Chelsea FC photos". If we then discuss his move to Liverpool, the query becomes "Daniel Sturridge Liverpool FC photos". Always include the correct team/era/event context.
4. Each section should last between 1 and 8 seconds maximum. If a passage talks about the same thing for longer than 8 seconds, split it into multiple sections with the same or related queries.
5. The images MUST match what the narrator is saying AT THAT MOMENT. Don't show generic images when specific people/events/places/teams are being discussed.
6. Use the exact timestamps from the transcript — don't guess. Each section's start_time and end_time must come from the segment timestamps.
7. Sections must be contiguous — no gaps, no overlaps. One section's end_time = next section's start_time.
8. Every search query MUST end with "photos".
9. Keep search queries 4-8 words, specific, and searchable on Google/Brave Images.

RESPOND WITH ONLY a JSON array of objects, each with:
- "start_time": number (seconds)
- "end_time": number (seconds)  
- "search_query": string (ending in "photos")
- "text": string (the narration text for this section)

Example:
[
  {{"start_time": 0.0, "end_time": 3.5, "search_query": "Chelsea FC Stamford Bridge stadium photos", "text": "Chelsea Football Club has a rich history..."}},
  {{"start_time": 3.5, "end_time": 5.2, "search_query": "Didier Drogba Chelsea celebration photos", "text": "Star players like Didier Drogba,"}},
  {{"start_time": 5.2, "end_time": 6.8, "search_query": "Nicolas Anelka Chelsea FC photos", "text": "Nicolas Anelka,"}},
  {{"start_time": 6.8, "end_time": 8.5, "search_query": "Solomon Kalou Chelsea FC photos", "text": "and Solomon Kalou all played for the Blues."}}
]"""

    response = groq_client.chat.completions.create(
        model='llama-3.3-70b-versatile',
        messages=[
            {"role": "system", "content": "You are a professional video editor. Output only valid JSON. Be precise with timestamps."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )

    text = response.choices[0].message.content.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

    sections = json.loads(text)

    # Validate and fix queries
    for i, s in enumerate(sections):
        q = s.get('search_query', 'related topic photos')
        if not q.strip().lower().endswith('photos'):
            q = q.strip() + ' photos'
        sections[i]['search_query'] = q

    return sections


def process_audio(audio_path):
    """
    Main function: transcribes audio, sends timestamped segments to Groq
    which intelligently splits into visual sections (one image per person/topic),
    and returns the final sections list.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    audio_duration = get_audio_duration(audio_path)
    print(f"Audio duration: {audio_duration:.1f} seconds")

    # Transcribe the audio
    full_text, words, segments = transcribe_audio(audio_path)

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

    print(f"\nSending {len(segments)} timestamped segments to Groq for intelligent sectioning...")
    ai_sections = generate_sections_with_groq(segments, full_text)
    print(f"Groq created {len(ai_sections)} visual sections")

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
