from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)

# Sets up constants - where files are saved and Allowed File Types
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}


# Tells Flask where to save uploads, secret key is needed for flash messages
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'supersecretkey'


# Ensures uploads folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# Name: allowed_file - File Type Validator
# Desc: Validates if the uploaded file has an allowed extension
# Precondition: filename is a valid string containing a filename
# Postcondition: Returns True if file extension is allowed, False otherwise
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Registers home function as route handler for root URL ("/"), accepts GET requests by default
@app.route('/')
# Name: home - Home Page Route Handler
# Desc: Handles GET requests to the root URL (runs is someones visits the homepage)
# Precondition: Flask app is running and home.html template exists
# Postcondition: Renders home page template with optional message parameter
def home():
    message = request.args.get('message')
    return render_template('home.html', message=message)


# Registers upload_file function as route handler for "/upload" URL, restricts to POST requests only
@app.route('/upload', methods=['POST'])
# Name: upload_file - File Upload Route Handler
# Desc: A comprehensive file upload handler that performs multiple validation checks at each step and provides user feedback through flash messages. 
# Precondition: Flask app is running, UPLOAD_FOLDER is configured, POST request contains file data
# Postcondition: File is saved to upload folder if valid, or error message is flashed. User is always redirected back to home page.
def upload_file():
    if 'file' not in request.files:
        flash('No file part in request')
        return redirect(url_for('home'))
    
    file = request.files['file']

    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('home'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        flash('File uploaded successfully!')
        return redirect(url_for('home'))
    else:
        flash('Invalid file type. Please upload a PDF.')
        return redirect(url_for('home'))


# Only starts the web server if this file is being run directly
if __name__ == '__main__':
    app.run(debug=True)