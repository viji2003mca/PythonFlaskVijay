from flask import Flask
from flask_mysqldb import MySQL
from flask_mail import Mail

mysql = MySQL()
mail = Mail()  # Declare mail globally


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
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Use your email provider's SMTP server
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USE_SSL'] = False
    app.config['MAIL_USERNAME'] = 'bu200512@gmail.com'  # Replace with your email
    app.config['MAIL_PASSWORD'] = 'zliktabovuxbdafy'  # Replace with your email password
    app.config['MAIL_DEFAULT_SENDER'] = 'bu200512@gmail.com'

    mail.init_app(app)
        
        
    # Register routes
    with app.app_context():
        from .routes import main
        app.register_blueprint(main)

    return app