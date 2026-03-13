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


def generate_search_queries_with_groq(sections_text, full_transcript):
    """
    Send all sections to Groq in one call and get back a list of
    descriptive, searchable image queries (one per section), each ending in 'photos'.
    The full transcript is provided for context.
    """
    numbered = ""
    for i, text in enumerate(sections_text, 1):
        numbered += f"\n[{i:02d}] {text}\n"

    prompt = f"""You are helping generate image search queries for a YouTube video.

Here is the FULL transcript of the video for context — read it first so you understand
the overall topic, the people involved, and the story being told:

--- FULL TRANSCRIPT ---
{full_transcript}
--- END TRANSCRIPT ---

Now, the transcript has been split into numbered sections below. For each section, generate ONE short,
specific, highly searchable image query that captures the KEY visual concept of that section.

IMPORTANT: Every query must be relevant to the OVERALL VIDEO TOPIC above. Keep the main subject,
people, and theme in mind when choosing queries — don't generate generic queries that ignore the
video's context.

RULES:
- Every query MUST end with the word "photos"
- Use real names of people, places, clubs, competitions, events when mentioned
- Be specific and descriptive (e.g. "Mbwana Samatta celebrating goal Aston Villa photos" not "footballer scoring photos")
- Keep queries between 4-8 words (including "photos")
- The query should return relevant images when searched on Google/Brave image search
- If the section mentions a specific event, include the year if available
- Do NOT use generic filler words — every word should help find the right image
- Remember the video's main subject when generating ALL queries

SECTIONS:
{numbered}

Respond with ONLY a JSON array of strings, one query per section, in order. Example format:
["Mbwana Samatta Simba SC football photos", "TP Mazembe football stadium photos", ...]

Return exactly {len(sections_text)} queries."""

    response = groq_client.chat.completions.create(
        model='llama-3.3-70b-versatile',
        messages=[
            {"role": "system", "content": "You are a helpful assistant that outputs only valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    text = response.choices[0].message.content.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

    queries = json.loads(text)

    if len(queries) != len(sections_text):
        print(f"WARNING: Groq returned {len(queries)} queries for {len(sections_text)} sections")
        while len(queries) < len(sections_text):
            queries.append("related topic photos")
        queries = queries[:len(sections_text)]

    for i, q in enumerate(queries):
        if not q.strip().lower().endswith('photos'):
            queries[i] = q.strip() + ' photos'

    return queries


def process_audio(audio_path, max_sentences_per_section=3):
    """
    Main function: transcribes audio, segments the transcript into sections
    with accurate timestamps, and generates image search queries.

    Args:
        audio_path: path to the narration audio file
        max_sentences_per_section: max segments grouped per section

    Returns:
        list of dicts with number, search_query, text, start_time, end_time, images_needed
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    audio_duration = get_audio_duration(audio_path)
    print(f"Audio duration: {audio_duration:.1f} seconds")

    # Transcribe the audio
    full_text, words, segments = transcribe_audio(audio_path)

    print(f"\nTranscript preview: {full_text[:200]}...")

    # Group into sections using segments (preferred) or words (fallback)
    if segments:
        print(f"\nUsing {len(segments)} Whisper segments for timing")
        raw_sections = group_segments_into_sections(segments, max_sentences_per_section)
    elif words:
        print(f"\nUsing {len(words)} word-level timestamps for timing")
        raw_sections = group_words_into_sections(words, audio_duration, max_sentences_per_section)
    else:
        raise ValueError("Transcription returned no words or segments")

    print(f"Grouped into {len(raw_sections)} sections")

    # Fill gaps by extending each section's end to the next section's start.
    # This keeps images on screen through any silence, rather than showing
    # the next topic's images before the narrator gets there.
    raw_sections[0]['start_time'] = 0.0
    for i in range(len(raw_sections) - 1):
        gap_end = raw_sections[i + 1]['start_time']
        if raw_sections[i]['end_time'] < gap_end:
            raw_sections[i]['end_time'] = gap_end
    raw_sections[-1]['end_time'] = audio_duration

    # Extract section texts for query generation
    sections_text = [s['text'] for s in raw_sections]

    # Generate search queries
    print("Generating search queries with Groq AI...")
    search_queries = generate_search_queries_with_groq(sections_text, full_text)

    MAX_SECONDS_PER_IMAGE = 8

    sections = []
    for i, raw in enumerate(raw_sections):
        duration = raw['end_time'] - raw['start_time']
        images_needed = max(1, math.ceil(duration / MAX_SECONDS_PER_IMAGE))

        section = {
            "number": i + 1,
            "search_query": search_queries[i],
            "text": raw['text'],
            "start_time": round(raw['start_time'], 2),
            "end_time": round(raw['end_time'], 2),
            "images_needed": images_needed,
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
        print(f"       Time: {s['start_time']:.1f}s - {s['end_time']:.1f}s ({duration:.1f}s) | {s['images_needed']} image(s)")
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
