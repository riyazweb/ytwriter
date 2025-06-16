import os
from flask import Flask, request, render_template_string, jsonify
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import google.generativeai as genai
from urllib.parse import urlparse, parse_qs # Import these explicitly for URL parsing
import markdown2 # Added: for converting Markdown to HTML. Install with: pip install markdown2

# --- Flask App Initialization ---
app = Flask(__name__)

# --- Gemini API Configuration ---
# IMPORTANT: Load the API key from environment variables.
# NEVER hardcode your API key directly in your source code.
# For example, on Linux/macOS: export GEMINI_API_KEY='your_api_key_here'
# On Windows (cmd): set GEMINI_API_KEY=your_api_key_here
# Or in a .env file if you use a library like python-dotenv (not included here for simplicity)
try:
    api_key ="AIzaSyALiGq131ysBLsheSLJMLBamsMVYGClPmk"
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found. Please set the environment variable.")
    genai.configure(api_key=api_key)
except ValueError as e:
    print(f"Error: {e}")
    print("AI summarization will not work without the API key.")
    # In a real app, you might want to stop here or disable AI features.
    # For now, let the app run but expect AI errors.

# --- HTML & CSS Template ---
# A single-page template for the user interface.
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouTube Video Summarizer ✨</title>
    <style>
        /* General body styling */
        body {
            background-color: #f8fafc; /* A very light grey, almost white */
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: #334155;
            margin: 0;
            padding: 20px;
            display: flex;
            justify-content: center;
            align-items: flex-start;
            min-height: 100vh;
        }

        /* Main container for the app */
        .container {
            width: 100%;
            max-width: 600px;
            background: #ffffff;
            border-radius: 16px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
            padding: 24px 32px;
            border: 1px solid #e2e8f0;
        }

        /* Header styling */
        h1 {
            text-align: center;
            font-size: 1.45em;
            color: #1e293b;
            margin-bottom: 24px;
        }

        /* Form styling */
        #summarize-form {
            display: flex;
            flex-direction: column;
        }

        /* Input field for the URL */
        input[type="text"] {
            width: 100%;
            padding: 14px;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            font-size: 1em;
            margin-bottom: 16px;
            background-color: #f8fafc;
            box-sizing: border-box; /* Important for consistent padding and width */
            transition: border-color 0.2s, box-shadow 0.2s;
        }
        input[type="text"]:focus {
            border-color: #4f46e5;
            box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
            outline: none;
        }

        /* Button styling */
        button {
            width: 100%;
            padding: 14px;
            background: red; /* A nice indigo color */
            color: #ffffff;
            border: none;
            border-radius: 8px;
            font-size: 1.1em;
            font-weight: 600;
            cursor: pointer;
            transition: background-color 0.2s;
        }
        button:hover {
            background: red;
        }
        button:disabled {
            background: red;
            cursor: not-allowed;
        }

        /* Loading spinner and message */
        .loading {
            text-align: center;
            margin-top: 24px;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 12px;
            color: #64748b;
        }
        .spinner {
            width: 32px;
            height: 32px;
            border: 4px solid #e2e8f0;
            border-top: 4px solid #4f46e5;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        /* Result display area */
        .result {
            margin-top: 24px;
            background: #f1f5f9;
            border-radius: 8px;
            padding: 16px;
            min-height: 50px;
            font-size: 1.03em;
            line-height: 1.6;
            white-space: pre-wrap; /* Preserves newlines and spaces */
            color: #1e293b;
            border: 1px solid #e2e8f0;
        }
        .result.error {
            color: #dc2626; /* Red color for error messages */
            font-weight: 500;
        }

        /* Keyframes for the spinner animation */
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>TRAIN WRITER🥳</h1>
        <form id="summarize-form" autocomplete="off">
            <input type="text" id="youtube-url" name="youtube_url" placeholder="Paste YouTube video URL here..." required>
            <button id="summarize-btn" type="button">Summarize! ✨</button>
        </form>
        <div id="loading" style="display:none;">
            <div class="spinner"></div>
            <span>making... Please wait! 🤖</span>
        </div>
        <div id="result" class="result"></div>
    </div>

    <script>
    document.addEventListener('DOMContentLoaded', function() {
        const form = document.getElementById('summarize-form');
        const btn = document.getElementById('summarize-btn');
        const resultDiv = document.getElementById('result');
        const loadingDiv = document.getElementById('loading');
        const urlInput = document.getElementById('youtube-url');

        // Main function to handle the click event
        const handleSummarize = async function() {
            resultDiv.textContent = '';
            resultDiv.classList.remove('error'); // Reset error class
            loadingDiv.style.display = 'flex';
            btn.disabled = true;
            
            const url = urlInput.value.trim(); // Trim whitespace from URL
            if (!url) {
                showError("Please paste a YouTube URL first.");
                return;
            }

            try {
                // Call the backend API
                const response = await fetch('/summarize', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ youtube_url: url })
                });

                if (!response.ok) {
                    // This catches HTTP errors like 400, 500 etc.
                    const errorData = await response.json().catch(() => ({ error: `Server error: ${response.status} ${response.statusText}` }));
                    throw new Error(errorData.error || `Server responded with status: ${response.status}`);
                }
                
                const data = await response.json();
                
                if (data.error) {
                    showError(data.error);
                } else {
                    // Use innerHTML to render line breaks from the summary
                    resultDiv.innerHTML = data.summary;
                }
            } catch (err) {
                console.error('Fetch Error:', err);
                showError('An unexpected error occurred: ' + err.message);
            } finally {
                // Hide loading and re-enable button
                loadingDiv.style.display = 'none';
                btn.disabled = false;
            }
        };
        
        // Helper function to display errors
        function showError(message) {
            resultDiv.textContent = '❌ ' + message;
            resultDiv.classList.add('error');
            loadingDiv.style.display = 'none';
            btn.disabled = false;
        }

        // Event listeners
        btn.onclick = handleSummarize;
        form.onsubmit = function(e) { 
            e.preventDefault(); // Prevent form submission from reloading page
            handleSummarize();
        };
    });
    </script>
</body>
</html>
"""

def extract_video_id(url):
    """Extracts the YouTube video ID from various URL formats."""
    if not url:
        return None
        
    try:
        parsed_url = urlparse(url)
        
        # Standard youtube.com/watch?v=...
        if 'youtube.com' in parsed_url.netloc:
            qs = parse_qs(parsed_url.query)
            if 'v' in qs and qs['v'][0] and len(qs['v'][0]) == 11:
                return qs['v'][0]
        
        # Shortened youtu.be/
        if 'youtu.be' in parsed_url.netloc:
            video_id = parsed_url.path.lstrip('/')
            if video_id and len(video_id) == 11:
                return video_id
                
        # /shorts/ or /embed/ links
        path_parts = parsed_url.path.strip('/').split('/')
        if len(path_parts) > 1 and path_parts[0] in ['shorts', 'embed'] and len(path_parts[1]) == 11:
            return path_parts[1]
            
    except Exception as e:
        print(f"Error parsing URL '{url}': {e}")
        
    return None

@app.route('/', methods=['GET'])
def index():
    """Renders the main page."""
    return render_template_string(HTML_TEMPLATE)

@app.route('/summarize', methods=['POST'])
def summarize():
    """Handles the summarization request."""
    data = request.get_json()
    url = data.get('youtube_url', '').strip() # Strip whitespace from URL
    
    # --- 1. Get Video ID ---
    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({'error': 'Invalid or unsupported YouTube URL. Please check and try again.'}), 400

    # --- 2. Fetch Transcript ---
    transcript_text = ""
    try:
        print(f"Attempting to fetch transcript for video ID: {video_id}")
        
        # Attempt to fetch Hindi transcript first
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['hi'])
            transcript_text = ' '.join([item['text'] for item in transcript_list])
            print(f"Hindi transcript fetched successfully. Length: {len(transcript_text)} characters.")
        except NoTranscriptFound:
            print("No Hindi transcript found, attempting English.")
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
            transcript_text = ' '.join([item['text'] for item in transcript_list])
            print(f"English transcript fetched successfully. Length: {len(transcript_text)} characters.")
            
    except TranscriptsDisabled:
        print(f"Error: Transcripts are disabled for video {video_id}.")
        return jsonify({'error': 'Transcripts are disabled for this video by the uploader.'}), 404
    except NoTranscriptFound:
        print(f"Error: No transcript could be found for video {video_id}.")
        return jsonify({'error': 'No transcript could be found for this video. It might be a music video, a very new upload, or have subtitles turned off.'}), 404
    except Exception as e:
        # This often catches cases where YouTube blocks the request (e.g., HTTP 429 Too Many Requests)
        # or returns an unexpected page (e.g., CAPTCHA).
        print(f"Critical Transcript fetching error for {video_id}: {type(e).__name__} - {e}")
        return jsonify({'error': '❌ Failed to fetch transcript. This can happen if YouTube blocks the request or the video is unavailable. Trying again later might help. Please ensure the video has public captions.'}), 500

    if not transcript_text:
        return jsonify({'error': 'Transcript was fetched but appears empty. Cannot summarize.'}), 500

    # --- 3. Generate Summary with Gemini ---
    # Define the prompt for the AI model
    prompt = f"""
You are an expert content summarizer. Your goal is to create a, engaging summary of the following YouTube video transcript.
this is the transcript of the video but you need to amek it lieka normal vey engaging nromal texxt into like a video text
Instructions:
1.  **Keep it concise:** The summary must be brief and to the point in paragraphs or short paragraphs with same flow of the transcript and include all info that mentioned without leaving anything.
2.  **Make it engaging:** Use a friendly and exciting tone make the text readbale with very enagnign instresting text and make it very amazing. Add relevant many colorful emojis to make it lively.
3.  **Format with Markdown:**
    - Use Markdown for all formatting.
    - Use `**bold text**` to highlight key terms, ideas, or conclusions use very elss headings.
    - Use headings (`#`, `##`) and bullet points (`*` or `-`) to structure the summary for easy reading.
use vey less headings  and very less **bold text**s.
Here is the transcript:
---
{transcript_text}
---

Now, provide the short, engaging, Markdown-formatted summary.
"""
    final_summary = "AI summarization is unavailable due to an API key configuration issue." # Default error message

    try:
        # Check if genai was configured. This handles the case where API_KEY was missing on startup.
        if not api_key: # api_key variable comes from the global scope, set during app startup
            raise ValueError("Gemini API key not configured. Cannot generate summary.")

        # Create a GenerativeModel instance
        # Using gemini-1.5-flash-latest as it's fast and effective for this task
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        # Generate content and get the response
        print("Sending transcript to Gemini for summarization...")
        response = model.generate_content(prompt)
        
        # Convert the Markdown response to HTML for direct rendering in the browser.
        final_summary = markdown2.markdown(response.text)
        print("Summary generated by Gemini and converted to HTML.")
        
    except Exception as e:
        print(f"Gemini API error: {type(e).__name__} - {e}")
        return jsonify({'error': f'Could not generate summary. Error from AI service: {e}'}), 500

    # --- 4. Return Result ---
    return jsonify({'summary': final_summary})


# --- Main execution point ---
if __name__ == '__main__':
    # Runs the Flask app. debug=True allows for automatic reloading on code changes.
    # In production, set debug=False and use a production-ready WSGI server like Gunicorn.
    app.run(debug=True, port=5000) # Explicitly set a common port
