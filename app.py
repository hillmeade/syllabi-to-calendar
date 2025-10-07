from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
import os
import pdfplumber
import ollama
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime

app = Flask(__name__)

# Sets up constants - where files are saved and Allowed File Types
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

# Tells Flask where to save uploads, secret key is needed for flash messages
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'supersecretkey'

# Ensures uploads folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Google Calendar API Scope
SCOPES = ['https://www.googleapis.com/auth/calendar']

"""
# Name: allowed_file - File Type Validator
# Desc: Validates if the uploaded file has an allowed extension
# Precondition: filename is a valid string containing a filename
# Postcondition: Returns True if file extension is allowed, False otherwise
"""
def allowed_file(filename):
    # Checks if there is a '.' in the filename and gets the extension after the last dot
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


"""
# Name: home - Home Page Route Handler
# Desc: Handles GET requests to the root URL (runs is someones visits the homepage)
# Precondition: Flask app is running and home.html template exists
# Postcondition: Renders home page template with optional message parameter
"""
# Registers home function as route handler for root URL ("/"), accepts GET requests by default
@app.route('/')
def home():
    # Extracts 'message' parameter from URL query string (e.g., ?message=success)
    message = request.args.get('message')

    # Renders the home HTML template a makes the message variable available to use in the template to display messages
    return render_template('home.html', message=message)


"""
# Name: upload_file - File Upload Route Handler
# Desc: A comprehensive file upload handler that performs multiple validation checks at each step and provides user feedback through flash messages. 
# Precondition: Flask app is running, UPLOAD_FOLDER is configured, POST request contains file data
# Postcondition: File is saved to upload folder if valid, or error message is flashed. User is always redirected back to home page.
"""
# Registers upload_file function as route handler for "/upload" URL, restricts to POST requests only
@app.route('/upload', methods=['POST'])
def upload_file():
    # Checks whether the HTML form was submitted correctly and contains the 'file' input
    if 'file' not in request.files:
        # Flashes an error message
        flash('No file part in request')
        # Redirects user to the home page
        return redirect(url_for('home'))
    
    # Retrieves the file object from the request (whether its empty or not)
    file = request.files['file']

    # Checks if the user actually selected a file
    if file.filename == '':
        # Flashes an error message
        flash('No selected file')
        # Redirects user to the home page
        return redirect(url_for('home'))
    
    # Checks that the file exists and it is an allowed file (PDF)
    if file and allowed_file(file.filename):
        # Cleans the filename up to remove potentially dangerous characters
        filename = secure_filename(file.filename)
        # Stores the full path to the uploaded file 
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        # Saves the uploaded file to the uploads folder
        file.save(filepath)

        # Extracts text from the uploaded PDF
        text = ""
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                # Append text from each page with the newline operator
                text += page.extract_text() + "\n"

        # Extracts events and dates using Ollama 
        events_and_dates = extract_events_with_ollama(text)

        # Debug: print to terminal
        print("---- Detected Events + Dates (Ollama) ----")
        print(events_and_dates)
        
        # Flashes a success message
        flash('File uploaded successfully!')
        return render_template('results.html', text=text, events_and_dates=events_and_dates)
    else:
        # Flashes an error message
        flash('Invalid file type. Please upload a PDF.')
        # Redirects user to the home page
        return redirect(url_for('home'))


"""
# Name: extract_events_with_ollama - AI-Powered Event Extractor
# Desc: Uses Ollama's llama3.2 model to extract important dates and events from syllabus text
# Precondition: text is a string containing extracted PDF content, Ollama service is running
# Postcondition: Returns a list of dictionaries with 'event' and 'date' keys
"""
def extract_events_with_ollama(text):
    prompt = f"""
    You are analyzing a course syllabus. Extract all important dates and events.
    Return ONLY a JSON array of objects with this format:
    [
        {{"event": "Assignment 1", "date": "September 15"}}
        {{"event": "Midterm Exam", "date": "October 20"}}
    ]
    Important:
    - Include assignments, exams, quizzes, project deadlines, and other academic events
    - Use clear, concise event names
    - Keep dates in a readable format (e.g., "September 15" or "Sept 15")
    - Return ONLY the JSON array, no other text

    Syllabus text:
    {text}
    """

    try:
        # Sends a request to Ollama
        response = ollama.chat(model='llama3.2', messages=[{'role': 'user', 'content': prompt}])

        # Extracts the response text
        response_text = response['message']['content']

        # Parses JSON response
        events = json.loads(response_text)
        return events
    
    except Exception as e:
        print(f"Error extracting eevnts: {e}")
        return []
    

"""
# Name: get_calendar_service - Google Calendar API Authentication
# Desc: Authenticates user with Google Calendar API and returns an authorized service object for making API calls
# Precondition: credentials.json exists in project root, Google Calendar API is enabled in Google Cloud Console
# Postcondition: Returns an authenticated Google Calendar service object, creates/refreshes token.json for future use
"""
def get_calendar_service():
    creds = None

    # Token.json stores the user's access and refresh tokens
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If there are no valid credentials, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Saves the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    service = build('calendar', 'v3', credentials=creds)
    return service

# Only starts the web server if this file is being run directly
if __name__ == '__main__':
    app.run(debug=True)