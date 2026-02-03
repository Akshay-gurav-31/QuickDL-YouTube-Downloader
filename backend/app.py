"""
Flask Backend Application for YouTube Video Downloader.
Handles video information retrieval and file downloading using yt-dlp.
"""

import os
import time
from typing import Dict, Any, Union, Tuple
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
import yt_dlp

# === CONSTANTS ===
DOWNLOAD_DIR = 'downloads'
DEFAULT_PORT = 5000
DEFAULT_QUALITY = '1080p'
HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500

# Error Messages
ERR_URL_REQUIRED = 'URL is required'
ERR_FETCH_INFO = 'Could not fetch video info. Please check the URL.'
ERR_FILE_NOT_FOUND = 'File not found after download'

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Ensure download directory exists
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)


def format_duration(duration_seconds: Union[int, float]) -> str:
    """
    Formats duration in seconds to MM:SS string format.
    
    Args:
        duration_seconds: Duration in seconds.
        
    Returns:
        Formatted time string (e.g., "05:30").
    """
    if not isinstance(duration_seconds, (int, float)):
        return str(duration_seconds)
        
    minutes = int(duration_seconds // 60)
    seconds = int(duration_seconds % 60)
    return f"{minutes}:{seconds:02d}"


def get_ydl_opts(download: bool = False, output_template: str = None) -> Dict[str, Any]:
    """
    Generates options for yt-dlp.
    
    Args:
        download: Whether to download the video or just fetch info.
        output_template: Template for the output filename (required if download=True).
        
    Returns:
        Dictionary of yt-dlp options.
    """
    opts = {
        'quiet': True,
        'no_warnings': True,
    }
    
    if download:
        opts.update({
            'quiet': False,
            'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]', # Default fallback
            'outtmpl': output_template,
            'merge_output_format': 'mp4',
        })
        
    return opts


def get_quality_format_string(quality: str) -> str:
    """
    Returns the yt-dlp format string based on requested quality.
    
    Args:
        quality: Requested quality (e.g., '1080p', '720p').
        
    Returns:
        Format string for yt-dlp.
    """
    height = quality.replace('p', '')
    if height in ['1080', '720', '480', '360']:
        return f'bestvideo[height<={height}]+bestaudio/best[height<={height}]'
    return 'best'


@app.route('/')
def index() -> Tuple[Any, int]:
    """Health check route."""
    return jsonify({
        'status': 'online',
        'message': 'QuickDL Backend is running',
        'version': '1.0.0'
    }), HTTP_OK


@app.route('/api/info', methods=['POST'])
def get_video_info() -> Tuple[Union[Response, str], int]:
    """
    retrieves metadata for a given YouTube URL.
    
    Returns:
        JSON response with video details or error message.
    """
    data = request.get_json()
    url = data.get('url')
    
    if not url:
        return jsonify({'error': ERR_URL_REQUIRED}), HTTP_BAD_REQUEST
        
    try:
        opts = get_ydl_opts(download=False)
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            video_data = {
                'title': info.get('title', 'Unknown Title'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': format_duration(info.get('duration')),
                'author': info.get('uploader', 'Unknown Author'),
                'webpage_url': info.get('webpage_url', url)
            }
            return jsonify(video_data)
            
    except Exception as error:
        print(f"Error fetching info: {error}")
        return jsonify({'error': ERR_FETCH_INFO}), HTTP_BAD_REQUEST


@app.route('/api/download', methods=['GET'])
def download_video() -> Tuple[Union[Response, str], int]:
    """
    Downloads a video with the specified quality.
    
    Expects 'url' and 'quality' query parameters.
    Returns:
        File attachment or error message.
    """
    url = request.args.get('url')
    quality = request.args.get('quality', DEFAULT_QUALITY)
    
    if not url:
        return jsonify({'error': ERR_URL_REQUIRED}), HTTP_BAD_REQUEST
        
    try:
        # Generate unique filename using timestamp
        timestamp = int(time.time())
        output_template = os.path.join(DOWNLOAD_DIR, f'%(title)s_{timestamp}.%(ext)s')
        
        # Configure options
        opts = get_ydl_opts(download=True, output_template=output_template)
        opts['format'] = get_quality_format_string(quality)
        
        filename = None
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Resolve the final filename
            if 'requested_downloads' in info:
                filename = info['requested_downloads'][0]['filepath']
            else:
                filename = ydl.prepare_filename(info)
                # Handle potential extension change due to merge (e.g. mkv -> mp4)
                base, ext = os.path.splitext(filename)
                if ext != '.mp4':
                     filename = base + '.mp4'

        if filename and os.path.exists(filename):
            try:
                return send_file(filename, as_attachment=True)
            except Exception as file_error:
                 return jsonify({'error': str(file_error)}), HTTP_INTERNAL_SERVER_ERROR
        else:
            return jsonify({'error': ERR_FILE_NOT_FOUND}), HTTP_INTERNAL_SERVER_ERROR
            
    except Exception as error:
        print(f"Download error: {error}")
        return jsonify({'error': str(error)}), HTTP_INTERNAL_SERVER_ERROR


if __name__ == '__main__':
    print(f"Starting Flask server on http://localhost:{DEFAULT_PORT}")
    app.run(debug=True, port=DEFAULT_PORT)
