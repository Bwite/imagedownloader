"""
Settings Server - Serves the settings HTML page and handles
audio upload + settings save + pipeline launch.
"""

import os
import sys
import json
import subprocess
import shutil
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
import webbrowser
import threading

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
SETTINGS_PATH = os.path.join(SCRIPT_DIR, 'settings.json')
PYTHON_EXE = os.path.join(PROJECT_DIR, '.venv', 'Scripts', 'python.exe')


class SettingsHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SCRIPT_DIR, **kwargs)

    def do_POST(self):
        if self.path == '/api/generate':
            self.handle_generate()
        else:
            self.send_error(404)

    def handle_generate(self):
        content_type = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in content_type:
            self.send_json({'success': False, 'error': 'Invalid content type'})
            return

        # Parse multipart form data
        boundary = content_type.split('boundary=')[1]
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length)

        # Simple multipart parser
        parts = body.split(('--' + boundary).encode())
        audio_data = None
        audio_filename = None
        settings_json = None

        for part in parts:
            if b'Content-Disposition' not in part:
                continue
            header_end = part.find(b'\r\n\r\n')
            if header_end == -1:
                continue
            header = part[:header_end].decode('utf-8', errors='replace')
            data = part[header_end + 4:]
            # Strip trailing \r\n
            if data.endswith(b'\r\n'):
                data = data[:-2]

            if 'name="audio"' in header:
                # Extract filename
                if 'filename="' in header:
                    fn_start = header.index('filename="') + 10
                    fn_end = header.index('"', fn_start)
                    audio_filename = header[fn_start:fn_end]
                audio_data = data
            elif 'name="settings"' in header:
                settings_json = data.decode('utf-8')

        if not audio_data or not audio_filename:
            self.send_json({'success': False, 'error': 'No audio file received'})
            return

        if not settings_json:
            self.send_json({'success': False, 'error': 'No settings received'})
            return

        try:
            settings = json.loads(settings_json)
        except json.JSONDecodeError:
            self.send_json({'success': False, 'error': 'Invalid settings JSON'})
            return

        # Clean old audio files from automatic_videos folder
        audio_exts = ('.m4a', '.mp3', '.wav', '.ogg', '.flac', '.aac')
        for f in os.listdir(SCRIPT_DIR):
            if f.lower().endswith(audio_exts):
                try:
                    os.remove(os.path.join(SCRIPT_DIR, f))
                except PermissionError:
                    pass  # skip files locked by another process

        # Save the uploaded audio file
        audio_path = os.path.join(SCRIPT_DIR, audio_filename)
        with open(audio_path, 'wb') as f:
            f.write(audio_data)

        # Save settings
        settings['audio_file'] = audio_filename
        with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2)

        print(f"\nAudio saved: {audio_path}")
        print(f"Settings saved: {SETTINGS_PATH}")
        print(f"\nSettings: {json.dumps(settings, indent=2)}")

        # Launch the pipeline in a new terminal
        bat_path = os.path.join(SCRIPT_DIR, 'make_video.bat')
        subprocess.Popen(
            ['cmd', '/c', 'start', 'cmd', '/k', bat_path],
            cwd=PROJECT_DIR
        )

        self.send_json({'success': True, 'message': 'Pipeline started'})

    def send_json(self, data):
        body = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Suppress noisy GET logs for static files
        if 'POST' in str(args):
            super().log_message(format, *args)


def main():
    port = 8899
    server = HTTPServer(('127.0.0.1', port), SettingsHandler)
    url = f'http://localhost:{port}/settings.html'
    print(f"\n{'='*50}")
    print(f"  Auto Video Generator — Settings Server")
    print(f"  Open: {url}")
    print(f"{'='*50}\n")

    # Open browser after a short delay
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()


if __name__ == '__main__':
    main()
