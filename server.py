"""
Flask Backend Server for Ultimate Download Machine
Connects the HTML frontend with the Brave Image Downloader
"""

from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
import os
import threading
import time
import requests
import zipfile
import io
import uuid
from urllib.parse import urlparse
from brave_image_downloader import BraveImageDownloader

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Initialize the downloader
API_KEY = "BSAHie1ZI1j77ZpQVuu3DHLsVuDFnt6"
downloader = BraveImageDownloader(API_KEY)

# Store download status for each session
download_status = {}
# Lock for thread-safe access to download_status
status_lock = threading.Lock()

def get_file_extension(url, content_type=None):
    """Get appropriate file extension from URL or content type"""
    # Try to get extension from URL
    parsed_url = urlparse(url)
    path = parsed_url.path
    if path and '.' in path:
        ext = path.split('.')[-1].lower()
        if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp']:
            return f".{ext}"
    
    # Try to get extension from content type
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

@app.route('/')
def home():
    """Serve the main HTML page"""
    return app.send_static_file('index.html')

@app.route('/test')
def test():
    """Serve the test HTML page"""
    return app.send_static_file('test.html')

@app.route('/web')
def web():
    """Serve the web deployment version"""
    return app.send_static_file('web.html')

@app.route('/debug-search', methods=['POST'])
def debug_search():
    """Debug endpoint to see API response structure"""
    try:
        data = request.get_json()
        query = data.get('query', 'test')
        
        results = downloader.search_images(query, 1)
        
        if results:
            # Return first result structure for debugging
            return jsonify({
                'success': True,
                'result_count': len(results),
                'first_result': results[0],
                'available_fields': list(results[0].keys())
            })
        else:
            return jsonify({'error': 'No results found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def download_worker(session_id, query, count):
    """Background worker to download images and create ZIP"""
    try:
        download_status[session_id]['status'] = 'searching'
        download_status[session_id]['message'] = 'Searching for images...'

        # Search for images
        results = downloader.search_images(query, count)

        if not results:
            with status_lock:
                download_status[session_id]['status'] = 'failed'
                download_status[session_id]['message'] = 'No images found for this query'
            return

        with status_lock:
            download_status[session_id]['status'] = 'downloading'
            download_status[session_id]['total'] = len(results)
            download_status[session_id]['downloaded'] = 0
            download_status[session_id]['failed'] = 0
            download_status[session_id]['message'] = f'Downloading {len(results)} images...'

        # Create ZIP file in memory
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for i, img in enumerate(results, 1):
                try:
                    # Get image URL from Brave API response
                    img_url = None

                    if 'properties' in img and isinstance(img['properties'], dict):
                        img_url = img['properties'].get('url')

                    if not img_url and 'thumbnail' in img and isinstance(img['thumbnail'], dict):
                        img_url = img['thumbnail'].get('src')

                    if not img_url:
                        download_status[session_id]['failed'] += 1
                        continue

                    # Download image with headers to avoid blocking
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                    img_response = requests.get(img_url, timeout=15, stream=True, headers=headers)
                    img_response.raise_for_status()

                    # Get file extension
                    content_type = img_response.headers.get('content-type', '')
                    file_ext = get_file_extension(img_url, content_type)

                    # Create filename
                    safe_query = query.replace(' ', '_').replace('/', '_').replace('\\', '_')
                    filename = f"{safe_query}_{i:02d}{file_ext}"

                    # Add image to ZIP
                    zip_file.writestr(filename, img_response.content)
                    download_status[session_id]['downloaded'] += 1
                    download_status[session_id]['progress'] = download_status[session_id]['downloaded']
                    download_status[session_id]['message'] = f'Downloaded {download_status[session_id]["downloaded"]}/{download_status[session_id]["total"]} images'

                except Exception as e:
                    with status_lock:
                        download_status[session_id]['failed'] += 1
                    continue

        # Store the ZIP buffer
        zip_buffer.seek(0)
        download_status[session_id]['zip_buffer'] = zip_buffer
        download_status[session_id]['zip_filename'] = f"{query.replace(' ', '_').replace('/', '_').replace('\\', '_')}_images.zip"
        download_status[session_id]['status'] = 'completed'
        download_status[session_id]['message'] = f'Successfully downloaded {download_status[session_id]["downloaded"]} images'

    except Exception as e:
        download_status[session_id]['status'] = 'failed'
        download_status[session_id]['message'] = str(e)

@app.route('/download', methods=['POST'])
def start_download():
    """Start background download and return session ID"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        count = int(data.get('count', 20))

        # Validation
        if not query:
            return jsonify({'error': 'Query is required'}), 400

        if count < 1 or count > 50:
            return jsonify({'error': 'Count must be between 1 and 50'}), 400

        # Create session
        session_id = str(uuid.uuid4())
        download_status[session_id] = {
            'status': 'starting',
            'message': 'Initializing download...',
            'query': query,
            'count': count,
            'progress': 0,
            'total': 0,
            'downloaded': 0,
            'failed': 0
        }

        # Start background download
        thread = threading.Thread(target=download_worker, args=(session_id, query, count))
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'Download started'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/status/<session_id>')
def get_status(session_id):
    """Get download status for a session"""
    if session_id not in download_status:
        return jsonify({'error': 'Session not found'}), 404

    # Create a copy of the status without the zip_buffer (not JSON serializable)
    status = download_status[session_id].copy()
    status.pop('zip_buffer', None)  # Remove the BytesIO object

    return jsonify(status)

@app.route('/download/<session_id>')
def download_zip(session_id):
    """Download the ZIP file for a completed session"""
    if session_id not in download_status:
        return jsonify({'error': 'Session not found'}), 404

    status = download_status[session_id]
    if status['status'] != 'completed':
        return jsonify({'error': 'Download not completed yet'}), 400

    if 'zip_buffer' not in status:
        return jsonify({'error': 'ZIP file not available'}), 500

    # Return the ZIP file
    status['zip_buffer'].seek(0)
    return send_file(
        status['zip_buffer'],
        mimetype='application/zip',
        as_attachment=True,
        download_name=status['zip_filename']
    )

@app.route('/open-folder/<session_id>')
def open_folder(session_id):
    """Placeholder for opening folder (not applicable for web version)"""
    return jsonify({'success': True, 'message': 'Folder opening not supported in web version'})





if __name__ == '__main__':
    print("🚀 Starting Ultimate Download Machine Server...")
    print("🌐 Web App: http://localhost:5000/web")
    print("📁 Images download directly to user's device as ZIP")
    print("🚀 Ready for web deployment!")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)