from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
import os
import pdfplumber
import ollama
import json
import re
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime
from dateutil import parser as date_parser

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

        # Adds events to Google Calendar
        if events_and_dates:
            added_count = add_events_to_calendar(events_and_dates)
            flash(f'File uploaded successfully! Added {added_count} events to your calendar.')
        else:
            flash('File uploaded but no events were detected.')

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
Extract all important academic dates and events from this syllabus.

Return ONLY valid JSON in this EXACT format (no extra text, no explanations):
[
  {{"event": "Assignment 1", "date": "September 15"}},
  {{"event": "Midterm Exam", "date": "October 20"}}
]

Rules:
- Return ONLY the JSON array
- Each object must have "event" and "date" keys
- Use proper JSON syntax with commas between objects
- Include assignments, exams, quizzes, project deadlines
- Keep event names clear and concise
- Use readable date format (e.g., "September 15" or "Sept 15")

Syllabus text:
{text[:3000]}
"""

    try:
        # Sends a request to Ollama
        response = ollama.chat(model='llama3.2', messages=[{'role': 'user', 'content': prompt}])

        # Extracts the response text
        response_text = response['message']['content'].strip()

        # Tries to find JSON array in the response (in case of extra text)
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group()

        # Parses JSON response
        events = json.loads(response_text)
        return events
    
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        print(f"Response was: {response_text[:500]}")
        return []
    except Exception as e:
        print(f"Error extracting events: {e}")
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
            creds = flow.run_local_server(port=8080)
        
        # Saves the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    service = build('calendar', 'v3', credentials=creds)
    return service

"""
# Name: add_events_to_calendar - Calendar Event Creator
# Desc: Takes a list of event dictionaries and adds them to the user's Google Calendar
# Precondition: events is a list of dicts with 'event' and 'date' keys, user is authenticated with Google Calendar API
# Postcondition: Creates calendar events for each item in the list, returns count of successfully added events
"""
def add_events_to_calendar(events):
    try:
        service = get_calendar_service()
        added_count = 0
        
        for item in events:
            event_name = item.get('event', 'Untitled Event')
            date_str = item.get('date', '')

            try:
                # Parses the date with the current year - dateutil handles format variations
                event_date = date_parser.parse(f"{date_str} {datetime.now().year}")         
            except Exception as e:
                print(f"Error parsing date: {date_str}")
                continue

            # Creates the event
            event_body = {
                'summary': event_name,
                'start': {
                    'date': event_date.strftime('%Y-%m-%d'),
                    'timeZone': 'America/New_York',
                },
                'end': {
                    'date': event_date.strftime('%Y-%m-%d'),
                    'timeZone': 'America/New_York',
                },
                'description': f'Imported from syllabus'
            }

            # Adds event to calendar
            event = service.events().insert(calendarId='primary', body=event_body).execute()
            print(f"Event created: {event.get('htmlLink')}")
            added_count += 1
        
        return added_count
    
    except HttpError as error:
        print(f'An error occurred: {error}')
        return 0
    
    
# Only starts the web server if this file is being run directly
if __name__ == '__main__':
    app.run(debug=True)