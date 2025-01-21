from flask import Flask
from flask_mysqldb import MySQL

mysql = MySQL()

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

    # Register routes
    with app.app_context():
        from .routes import main
        app.register_blueprint(main)

    return app