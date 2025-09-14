from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
import os
import pdfplumber
import re

app = Flask(__name__)

# Sets up constants - where files are saved and Allowed File Types
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}


# Tells Flask where to save uploads, secret key is needed for flash messages
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'supersecretkey'


# Ensures uploads folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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
        
        # Extract dates from the extracted text
        dates = extract_dates(text)
        # Prints detected dates to the terminal for debugging
        print("---- Detected Dates ----")
        print(dates)

        # Flashes a success message
        flash('File uploaded successfully!')
        return render_template('results.html', text=text)
    else:
        # Flashes an error message
        flash('Invalid file type. Please upload a PDF.')
        # Redirects user to the home page
        return redirect(url_for('home'))


"""
# Name: extract_dates - PDF Date Extractor
# Desc: Extracts date strings from a block of text using regular expressions. Supports common formats like "Sept 10", "10/05/25", and "10-05-2025".
# Precondition: text is a string containing extracted text from a PDF or other source
# Postcondition: Returns a list of date strings found in the text
"""
def extract_dates(text):
    # Normalize whitespace: replaces multiple spaces/newlines with a single space
    cleaned = re.sub(r'\s+', ' ', text)

    # List of regex patterns for several common date formats
    date_patterns = [
        # Pattern 1: Month Names and day e.g (October 15, Sept 5, Aug 10)
        r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2}\b',   
        # Pattern 2: Slash-separated dates e.g. (10/15/25, 9/10/2025)
        r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',   
        # Pattern 3: Dash-seperated dates e.g. (10-05-25, 9-10-2025)                                                
        r'\b\d{1,2}-\d{1,2}-\d{2,4}\b'                                                    
    ]

    # List to store all matched date strings
    dates = []
    for pattern in date_patterns:
        # Finds all matches for the current pattern (case-insensitive)
        matches = re.findall(pattern, cleaned, flags=re.IGNORECASE)
        # Adds matches to the overall list
        dates.extend(matches)
    
    return dates


# Only starts the web server if this file is being run directly
if __name__ == '__main__':
    app.run(debug=True)