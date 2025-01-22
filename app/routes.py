
import os

import random
import string
from flask import Blueprint, render_template, request, redirect, flash, send_from_directory, session, url_for, send_file
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from . import mysql
import bcrypt
from werkzeug.utils import secure_filename
from gtts import gTTS
import pytesseract

from flask import current_app


main = Blueprint('main', __name__)

# Generate a CAPTCHA code
def generate_captcha_code():
    # Generate 2 lowercase letters
    lower = ''.join(random.choices(string.ascii_lowercase, k=2))
    # Generate 2 uppercase letters
    upper = ''.join(random.choices(string.ascii_uppercase, k=2))
    # Generate 2 digits
    digits = ''.join(random.choices(string.digits, k=2))
    
    # Combine them and shuffle
    result = list(lower + upper + digits)
    random.shuffle(result)
    
    return ''.join(result)

# Generate a CAPTCHA image
def generate_captcha_image(captcha_code):
    width, height = 200, 60
    image = Image.new('RGB', (width, height), color=(255, 255, 255))
    font = ImageFont.truetype('arial.ttf', 40)  # Use a valid font file
    draw = ImageDraw.Draw(image)
    draw.text((20, 10), captcha_code, fill=(0, 0, 0), font=font)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

@main.route('/captcha_image')
def captcha_image():
    captcha_code = generate_captcha_code()
    session['captcha_code'] = captcha_code
    image_buffer = generate_captcha_image(captcha_code)
    return send_file(image_buffer, mimetype='image/png')


UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static', 'uploads')
DOWNLOAD_FOLDER = os.path.join(os.getcwd(), 'static', 'downloads')

# Create upload and download folders if they do not exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@main.route('/')
def home():
    return render_template('home.html')

@main.route('/index', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        form_action = request.form.get('form_action')
        
        if form_action == 'sign_in':
            # CAPTCHA validation
            user_captcha = request.form.get('captcha')
            if user_captcha != session.get('captcha_code'):
                flash('Invalid CAPTCHA. Please try again.', 'danger')
                return redirect(url_for('main.index'))

            # Sign-in logic
            email = request.form['email']
            password = request.form['password']

            cursor = mysql.connection.cursor()
            try:
                cursor.execute("SELECT id, password FROM users WHERE email = %s", (email,))
                user = cursor.fetchone()
            except Exception as e:
                flash(f"Database Error: {e}", 'danger')
                return redirect(url_for('main.index'))
            finally:
                cursor.close()

            if user and bcrypt.checkpw(password.encode('utf-8'), user[1].encode('utf-8')):
                session['user_id'] = user[0]
                flash('Login successful!', 'success')
                return render_template('index2.html')
            else:
                flash('Invalid email or password.', 'danger')
                return redirect(url_for('main.index'))

        elif form_action == 'sign_up':
            # Sign-up logic
            name = request.form['name']
            email = request.form['email']
            password = request.form['password']
            confirm_password = request.form['c_password']

            if password != confirm_password:
                flash('Passwords do not match.', 'danger')
                return redirect(url_for('main.index'))

            cursor = mysql.connection.cursor()
            try:
                # Check if the email already exists
                cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                existing_user = cursor.fetchone()

                if existing_user:
                    flash('An account with this email already exists. Please log in.', 'warning')
                    return redirect(url_for('main.index'))

                # Hash the password
                hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

                # Insert the new user into the database
                cursor.execute(
                    "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", 
                    (name, email, hashed_password)
                )
                mysql.connection.commit()
                flash('Account created successfully! Please log in.', 'success')
                return redirect(url_for('main.index'))
            except Exception as e:
                flash(f"Database Error: {e}", 'danger')
                return redirect(url_for('main.index'))
            finally:
                cursor.close()

    # Default behavior for GET requests
    return render_template('index.html')


# Configure Tesseract OCR path
pytesseract.pytesseract.tesseract_cmd = r'C:/Program Files/Tesseract-OCR/tesseract.exe'

@main.route('/convert_image_to_audio', methods=['GET', 'POST'])
def convert_image_to_audio():
    if 'file' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('main.home'))
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('main.home'))

    if file and allowed_file(file.filename):
        try:
            # Save the uploaded file
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            current_app.logger.debug(f'Image file saved at: {filepath}')

            # Validate if file is an image
            try:
                image = Image.open(filepath)
            except IOError:
                flash('Uploaded file is not a valid image.', 'danger')
                current_app.logger.error(f'Invalid image file: {filepath}')
                return redirect(url_for('main.home'))

            # Extract text from the image
            extracted_text = pytesseract.image_to_string(image)
            current_app.logger.debug(f'Extracted text: {extracted_text}')

            if not extracted_text.strip():
                flash('No text detected in the image.', 'danger')
                return redirect(url_for('main.home'))

            # Convert text to audio
            tts = gTTS(extracted_text, lang='en')
            audio_filename = os.path.splitext(filename)[0] + '.mp3'
            audio_filepath = os.path.join(DOWNLOAD_FOLDER, audio_filename)
            tts.save(audio_filepath)
            current_app.logger.debug(f'Audio file saved at: {audio_filepath}')

            flash('File successfully converted to audio.', 'success')

            return send_from_directory(DOWNLOAD_FOLDER, audio_filename, as_attachment=True)
        
        except Exception as e:
            current_app.logger.error(f'Error during conversion: {str(e)}')
            flash(f'An error occurred: {e}', 'danger')
            return redirect(url_for('main.home'))
    else:
        flash('Invalid file type. Please upload an image file.', 'danger')
        return redirect(url_for('main.home'))


@main.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully.', 'success')
    return redirect(url_for('main.index'))