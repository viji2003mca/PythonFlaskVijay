
from datetime import datetime
import os
import random
import string
import PyPDF2
import speech_recognition as sr
from flask import Blueprint, render_template, request, redirect, flash, send_from_directory, session, url_for, send_file, jsonify
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from . import mysql
import bcrypt
from werkzeug.utils import secure_filename
from gtts import gTTS
import pytesseract
from pydub import AudioSegment
from pydub.playback import play

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
                # Fetch user details (id, name, email, and hashed password)
                cursor.execute("SELECT id, name, email, password FROM users WHERE email = %s", (email,))
                user = cursor.fetchone()
            except Exception as e:
                flash(f"Database Error: {e}", 'danger')
                return redirect(url_for('main.index'))
            finally:
                cursor.close()

            if user and bcrypt.checkpw(password.encode('utf-8'), user[3].encode('utf-8')):  # Match password
                session['user_id'] = user[0]  # Store user ID in session
                flash('Login successful!', 'success')

                # Pass user details to index2.html
                return render_template('index2.html', name=user[1], email=user[2])
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



#Home Page Concept

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'app', 'static', 'uploads')
DOWNLOAD_FOLDER = os.path.join(os.getcwd(), 'app', 'static', 'downloads')

# Create upload and download folders if they do not exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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

            

            return send_from_directory(DOWNLOAD_FOLDER, audio_filename, as_attachment=True)
        
        except Exception as e:
            current_app.logger.error(f'Error during conversion: {str(e)}')
            flash(f'An error occurred: {e}', 'danger')
            return redirect(url_for('main.home'))
    else:
        flash('Invalid file type. Please upload an image file.', 'danger')
        return redirect(url_for('main.home'))


@main.route('/index2', methods=['GET', 'POST'])
def index2():
    if request.method == 'POST':
        # Check if a file was uploaded
        if 'uploadedFile' not in request.files:
            flash('No file part', 'danger')
            return redirect(url_for('main.index2'))

        file = request.files['uploadedFile']

        # Check if file is selected
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(url_for('main.index2'))

        if file and allowed_file(file.filename):
            try:
                # Save uploaded file
                filename = secure_filename(file.filename)
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
                current_app.logger.debug(f'Image file saved at: {filepath}')

                # Extract text from the image if selected conversion is to text
                extracted_text = ""
                if request.form['convertTo'] == 'text':
                    try:
                        # Extract text using Tesseract
                        image = Image.open(filepath)
                        extracted_text = pytesseract.image_to_string(image)
                        current_app.logger.debug(f'Extracted text: {extracted_text}')
                    except IOError:
                        flash('Uploaded file is not a valid image.', 'danger')
                        current_app.logger.error(f'Invalid image file: {filepath}')
                        return redirect(url_for('main.index2'))

                # Process the user's customization choices
                background_music = request.form.get('backgroundMusic')
                voice_gender = request.form.get('voiceGender', 'female')  # Default to female if not provided
                
                language_mapping = {
                        'eng': 'en',  # English
                        'spa': 'es',  # Spanish
                        'fra': 'fr',  # French
                        'deu': 'de',  # German
                        'ita': 'it',  # Italian
                        'jpn': 'ja',  # Japanese
                        'kor': 'ko',  # Korean
                        'hin': 'hi',  # Hindi
                        'tam': 'ta',  # Tamil
                        'tel': 'te',  # Telugu
                        'rus': 'ru',  # Russian
                        'ara': 'ar',  # Arabic
                    }

                    # Get the language from the form (default to 'en' if not provided)
                form_language = request.form.get('language', 'eng')  # Default to 'eng' if not specified

                    # Convert form value to the corresponding gTTS language code
                language = language_mapping.get(form_language, 'en')  # Default to 'en' if not found in the dictionary
                
                
                # MySQL Database logic for storing conversion history
                email = request.form.get('email')

                if request.form['convertTo'] == 'mp3':
                    try:
                        # Extract text using Tesseract
                        image = Image.open(filepath)
                        extracted_text = pytesseract.image_to_string(image, lang=language)
                        current_app.logger.debug(f'Extracted text: {extracted_text}')
                        
                        # Convert extracted text to audio (MP3)
                        if voice_gender == "male":
                            tts = gTTS(extracted_text, lang=language, slow=False, tld="co.in")
                        elif voice_gender == "mal":
                            tts = gTTS(extracted_text, lang=language, slow=False, tld="co.uk")
                        elif voice_gender == "ma":
                            tts = gTTS(extracted_text, lang=language, slow=False, tld="ca")
                        elif voice_gender == "m":
                            tts = gTTS(extracted_text, lang=language, slow=False, tld="com.au")
                        else:
                            tts = gTTS(extracted_text, lang=language, slow=False, tld="com")  # US Female Accent
                        audio_filename = os.path.splitext(filename)[0] + '_voice.mp3'
                        
                        audio_filepath = os.path.join(DOWNLOAD_FOLDER, audio_filename)
                        tts.save(audio_filepath)
                        current_app.logger.debug(f'Audio file saved at: {audio_filepath}')


                        email = request.form.get('email')

                        try:
                            cursor = mysql.connection.cursor()
                            
                            # Insert new conversion history into the database
                            cursor.execute(
                                "INSERT INTO conversion_history (email, file_name, is_favorite, created_at) VALUES (%s, %s, %s, %s)", 
                                (email, audio_filename, False, datetime.utcnow())
                            )
                            mysql.connection.commit()
                            current_app.logger.debug(f'Conversion history saved for {email} with file {audio_filename}.')

                            


                        except Exception as e:
                            flash(f"Database Error: {e}", 'danger')
                            current_app.logger.error(f"Error while saving conversion history: {str(e)}")
                        
                        finally:
                            cursor.close()
                        
                        # Fetch user input values
                        pitch = float(request.form.get('pitch', 1))  # Default pitch to 1 (normal)
                        duration = float(request.form.get('duration', 1))  # Default duration to 1 (normal)
                        volume_percentage = int(request.form.get('volume', 50))  # Default volume to 50%
                        bg_volume = volume_percentage / 100  # Convert to a scale of 0.0 to 1.0

                        # If background music is provided
                        if background_music:
                            music_filepath = os.path.join('app', 'static', 'backgroundmusic', background_music)
                            if os.path.exists(music_filepath):
                                # Load the background music and the generated voice
                                music = AudioSegment.from_file(music_filepath)
                                voice = AudioSegment.from_mp3(audio_filepath)
                                
                                # Adjust pitch and speed
                                if pitch != 1:
                                    voice = voice.set_frame_rate(int(voice.frame_rate * pitch))
                                if duration != 1:
                                    voice = voice.speedup(playback_speed=duration)
                                
                                # Adjust background music volume
                                music = music - (20 * (1 - bg_volume))  # Reduce volume by a scaled dB level

                                # Extend or trim the music to match the voice duration
                                if len(music) < len(voice):
                                    loops = len(voice) // len(music) + 1
                                    music = (music * loops)[:len(voice)]
                                else:
                                    music = music[:len(voice)]
                                
                                    # Combine voice and music
                                    music = music.fade_in(2000)  # Fade in music for smooth transition
                                    combined = voice.overlay(music)

                                    # Save the final combined file
                                    final_audio_filename = os.path.splitext(filename)[0] + '_final.mp3'
                                    final_audio_filepath = os.path.join(DOWNLOAD_FOLDER, final_audio_filename)
                                    combined.export(final_audio_filepath, format='mp3')
                                    current_app.logger.debug(f'Combined audio file saved at: {final_audio_filepath}')

                                    try:
                                        cursor = mysql.connection.cursor()
                                        
                                        # Insert new conversion history into the database
                                        cursor.execute(
                                            "INSERT INTO conversion_history (email, file_name, is_favorite, created_at) VALUES (%s, %s, %s, %s)", 
                                            (email, final_audio_filename, False, datetime.utcnow())
                                        )
                                        mysql.connection.commit()
                                        current_app.logger.debug(f'Conversion history saved for {email} with file {final_audio_filename}.')

                                        


                                    except Exception as e:
                                        flash(f"Database Error: {e}", 'danger')
                                        current_app.logger.error(f"Error while saving conversion history: {str(e)}")
                                    
                                    finally:
                                        cursor.close()

                                    # Send the file as a download
                                    return send_from_directory(DOWNLOAD_FOLDER, final_audio_filename, as_attachment=True)
                                    
                            else:
                                flash('Background music file not found.', 'danger')
                                return redirect(url_for('main.index2'))
                        else:
                            # If no background music, return the original MP3 file
                            return send_from_directory(DOWNLOAD_FOLDER, audio_filename, as_attachment=True)

                    except Exception as e:
                        current_app.logger.error(f"Error processing MP3 conversion: {e}")
                        flash("An error occurred while processing your request.", "danger")
                        return redirect(url_for('main.index2'))


                elif request.form['convertTo'] == 'text':
                    # Save extracted text as a txt file
                    if not extracted_text.strip():
                        flash('No text detected in the image to convert to text.', 'danger')
                        return redirect(url_for('main.index2'))
                    
                    text_filename = os.path.splitext(filename)[0] + '.txt'
                    
                    text_filepath = os.path.join(DOWNLOAD_FOLDER, text_filename)

                    with open(text_filepath, 'w') as f:
                        f.write(extracted_text)
                    
                    current_app.logger.debug(f'Text file saved at: {text_filepath}')
                    
                    try:
                        cursor = mysql.connection.cursor()
                        
                        # Insert new conversion history into the database
                        cursor.execute(
                            "INSERT INTO conversion_history (email, file_name, is_favorite, created_at) VALUES (%s, %s, %s, %s)", 
                            (email, text_filename, False, datetime.utcnow())
                        )
                        mysql.connection.commit()
                        current_app.logger.debug(f'Conversion history saved for {email} with file {text_filename}.')

                        

                    except Exception as e:
                        flash(f"Database Error: {e}", 'danger')
                        current_app.logger.error(f"Error while saving conversion history: {str(e)}")
                    
                    finally:
                        cursor.close()

                    return send_from_directory(DOWNLOAD_FOLDER, text_filename, as_attachment=True)
                

            except Exception as e:
                current_app.logger.error(f'Error during conversion: {str(e)}')
                flash(f'An error occurred: {e}', 'danger')
                return redirect(url_for('main.index2'))
        else:
            flash('Invalid file type. Please upload an image file.', 'danger')
            return redirect(url_for('main.index2'))
    else:
        
        return redirect(url_for('main.index2'))
    

@main.route('/image-to-audio')
def image_to_audio():
    name = request.args.get('name', 'Guest')
    email = request.args.get('email', 'No Email')
    return render_template('index2.html', name=name, email=email)

@main.route('/image-to-text')
def image_to_text():
    name = request.args.get('name', 'Guest')
    email = request.args.get('email', 'No Email')
    return render_template('image_to_text.html', name=name, email=email)

@main.route('/convert_image_to_text1', methods=['GET', 'POST'])
def convert_image_to_text1():

    UPLOAD_FOLDERS = os.path.join(os.getcwd(), 'static', 'uploads')
    DOWNLOAD_FOLDERS = os.path.join(os.getcwd(), 'static', 'downloads')

    # Create upload and download folders if they do not exist
    os.makedirs(UPLOAD_FOLDERS, exist_ok=True)
    os.makedirs(DOWNLOAD_FOLDERS, exist_ok=True)

    ALLOWED_EXTENSION = {'png', 'jpg', 'jpeg', 'gif'}

    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSION


    if 'file' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('main.image_to_text'))
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('main.image_to_text'))

    if file and allowed_file(file.filename):
        try:
            # Save the uploaded file
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDERS, filename)
            file.save(filepath)
            current_app.logger.debug(f'Image file saved at: {filepath}')

            # Validate if file is an image
            try:
                image = Image.open(filepath)
            except IOError:
                flash('Uploaded file is not a valid image.', 'danger')
                current_app.logger.error(f'Invalid image file: {filepath}')
                return redirect(url_for('main.image_to_text'))
            language_mapping = {
                'eng': 'en',  # English
                'spa': 'es',  # Spanish
                'fra': 'fr',  # French
                'deu': 'de',  # German
                'ita': 'it',  # Italian
                'jpn': 'ja',  # Japanese
                'kor': 'ko',  # Korean
                'hin': 'hi',  # Hindi
                'tam': 'ta',  # Tamil
                'tel': 'te',  # Telugu
                'rus': 'ru',  # Russian
                'ara': 'ar',  # Arabic
            }

                # Get the language from the form (default to 'en' if not provided)
            form_language = request.form.get('language', 'eng')  # Default to 'eng' if not specified

                # Convert form value to the corresponding gTTS language code
            language = language_mapping.get(form_language, 'en')  # Default to 'en' if not found in the dictionary
            # Extract text from the image
            extracted_text = pytesseract.image_to_string(image, lang=language)
            current_app.logger.debug(f'Extracted text: {extracted_text}')

            if not extracted_text.strip():
                flash('No text detected in the image.', 'danger')
                return redirect(url_for('main.image_to_text'))

            # Save extracted text to a file
            text_filename = os.path.splitext(filename)[0] + '.txt'
            text_filepath = os.path.join(DOWNLOAD_FOLDERS, text_filename)
            with open(text_filepath, 'w', encoding='utf-8') as text_file:
                text_file.write(extracted_text)
            current_app.logger.debug(f'Text file saved at: {text_filepath}')

            return send_from_directory(DOWNLOAD_FOLDERS, text_filename, as_attachment=True)
        
        except Exception as e:
            current_app.logger.error(f'Error during conversion: {str(e)}')
            flash(f'An error occurred: {e}', 'danger')
            return redirect(url_for('main.image_to_text'))
    else:
        flash('Invalid file type. Please upload an image file.', 'danger')
        return redirect(url_for('main.image_to_text'))

@main.route('/pdf-to-audio')
def pdf_to_audio():
    name = request.args.get('name', 'Guest')
    email = request.args.get('email', 'No Email')
    return render_template('pdf_to_audio.html', name=name, email=email)

@main.route('/convert_pdf_to_audio', methods=['POST'])
def convert_pdf_to_audio():
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static', 'uploads')
    DOWNLOAD_FOLDER = os.path.join(os.getcwd(), 'static', 'downloads')

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

    if 'file' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('main.pdf_to_audio'))

    file = request.files['file']

    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('main.pdf_to_audio'))

    if file and file.filename.endswith('.pdf'):
        try:
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            current_app.logger.debug(f'PDF file saved at: {filepath}')

            # Extract text from PDF
            text = extract_text_from_pdf(filepath)
            if not text.strip():
                flash('No text detected in the PDF.', 'danger')
                return redirect(url_for('main.pdf_to_audio'))

            # Convert text to audio
            audio_filename = os.path.splitext(filename)[0] + '.mp3'
            audio_filepath = os.path.join(DOWNLOAD_FOLDER, audio_filename)

            language = request.form.get('language', 'en')
            voice_gender = request.form.get('voiceGender', 'female')  # Default to female if not provided
            
            # Convert extracted text to audio (MP3)
            if voice_gender == "male":
                tts = gTTS(text=text, lang=language, slow=False, tld="co.in")
            elif voice_gender == "mal":
                tts = gTTS(text=text, lang=language, slow=False, tld="co.uk")
            elif voice_gender == "ma":
                tts = gTTS(text=text, lang=language, slow=False, tld="ca")
            elif voice_gender == "m":
                tts = gTTS(text=text, lang=language, slow=False, tld="com.au")
            else:
                tts = gTTS(text=text, lang=language, slow=False, tld="com")  # US Female Accent
            tts.save(audio_filepath)
            current_app.logger.debug(f'Audio file saved at: {audio_filepath}')

            return send_from_directory(DOWNLOAD_FOLDER, audio_filename, as_attachment=True)

        except Exception as e:
            current_app.logger.error(f'Error during conversion: {str(e)}')
            flash(f'An error occurred: {e}', 'danger')
            return redirect(url_for('main.pdf_to_audio'))
    else:
        flash('Invalid file type. Please upload a PDF file.', 'danger')
        return redirect(url_for('main.pdf_to_audio'))

def extract_text_from_pdf(filepath):
    text = ""
    with open(filepath, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text


@main.route('/audio-to-text')
def audio_to_text():
    name = request.args.get('name', 'Guest')
    email = request.args.get('email', 'No Email')
    return render_template('audio_to_text.html', name=name, email=email)


@main.route('/audio-to-text1', methods=['GET', 'POST'])
def audio_to_text1():
    """Handles audio file upload, transcribes text, and allows downloading."""
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static', 'uploads')
    DOWNLOAD_FOLDER = os.path.join(os.getcwd(), 'static', 'downloads')

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)


    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(url_for('main.audio_to_text'))

        file = request.files['file']

        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(url_for('main.audio_to_text'))

        if file and file.filename.endswith(('.mp3', '.wav', '.flac', '.m4a')):
            try:
                filename = secure_filename(file.filename)
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
                current_app.logger.debug(f'Audio file saved at: {filepath}')

                # Convert non-WAV files to WAV
                wav_filepath = convert_to_wav(filepath)

                # Convert audio to text
                text = extract_text_from_audio(wav_filepath)
                if not text.strip():
                    flash('No speech detected in the audio file.', 'danger')
                    return redirect(url_for('main.audio_to_text'))

                # Save transcribed text as a .txt file
                text_filename = os.path.splitext(filename)[0] + '.txt'
                text_filepath = os.path.join(DOWNLOAD_FOLDER, text_filename)

                with open(text_filepath, 'w', encoding='utf-8') as txt_file:
                    txt_file.write(text)

                current_app.logger.debug(f'Text file saved at: {text_filepath}')
                flash('Audio successfully converted to text.', 'success')

                return send_from_directory(DOWNLOAD_FOLDER, text_filename, as_attachment=True)

            except Exception as e:
                current_app.logger.error(f'Error during conversion: {str(e)}')
                flash(f'An error occurred: {e}', 'danger')
                return redirect(url_for('main.audio_to_text'))

        else:
            flash('Invalid file type. Please upload an audio file.', 'danger')
            return redirect(url_for('main.audio_to_text'))

    return render_template('audio_to_text.html')

def convert_to_wav(filepath):
    """Converts an audio file to WAV format if necessary."""
    if filepath.endswith('.wav'):
        return filepath  # Already WAV, no conversion needed

    wav_filepath = os.path.splitext(filepath)[0] + '.wav'
    audio = AudioSegment.from_file(filepath)
    audio.export(wav_filepath, format="wav")
    
    return wav_filepath

def extract_text_from_audio(filepath):
    """Extracts text from an audio file using SpeechRecognition."""
    recognizer = sr.Recognizer()
    with sr.AudioFile(filepath) as source:
        audio_data = recognizer.record(source)
        try:
            text = recognizer.recognize_google(audio_data)
            return text
        except sr.UnknownValueError:
            return "Could not understand the audio."
        except sr.RequestError:
            return "Error connecting to speech recognition service."


def get_user_audio_files(email):
    try:
        cursor = mysql.connection.cursor()

        # Query the database for filenames where the email matches
        query = "SELECT file_name FROM conversion_history WHERE email = %s"
        cursor.execute(query, (email,))
        files = cursor.fetchall()  # Returns a list of tuples
        
        cursor.close()
        
        # Debugging: Print fetched data to check if it works
        print("Fetched Files:", files)  

        return [file[0] for file in files]  # Extract filenames from tuples
    except Exception as e:
        print("Database error:", e)
        return []


@main.route('/playlists')
def playlists():
    name = request.args.get('name', 'Guest')
    email = request.args.get('email', 'No Email')
    # Fetch audio files for the given email
    audio_files = get_user_audio_files(email)

    return render_template('playlists.html', name=name, email=email, audio_files=audio_files)

@main.route('/get_audio_files', methods=['GET'])
def get_audio_files():
    email = request.args.get('email')
    
    if not email:
        return jsonify({"error": "Email is required"}), 400
    
    files = get_user_audio_files(email)
    
    # Debugging: Print to check response
    print("Returning files:", files)
    
    return jsonify(files)

    

@main.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('main.index'))