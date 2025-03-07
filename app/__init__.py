import os
from flask import Flask
from flask_mysqldb import MySQL
from flask_mail import Mail
from dotenv import load_dotenv

mysql = MySQL()
mail = Mail()  # Declare mail globally

load_dotenv()

def create_app():
    app = Flask(__name__)

    # Configurations
    app.config['SECRET_KEY'] = 'b1a72ffdfb6d12345eabcdef12345678'  # Example 24-byte key
    app.config['MYSQL_HOST'] = 'localhost'
    app.config['MYSQL_USER'] = 'root'  # XAMPP default username
    app.config['MYSQL_PASSWORD'] = ''  # XAMPP default password
    app.config['MYSQL_DB'] = 'image_to_sound'

    # Initialize MySQL
    mysql.init_app(app)
    

    # Configure Flask-Mail
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')  # Use your email provider's SMTP server
    app.config['MAIL_PORT'] = os.getenv('MAIL_PORT') 
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USE_SSL'] = False
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')   # Replace with your email
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')   # Replace with your email password
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER') 

    mail.init_app(app)
        
        
    # Register routes
    with app.app_context():
        from .routes import main
        app.register_blueprint(main)

    return app