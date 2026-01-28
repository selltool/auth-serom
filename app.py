import os
from flask import Flask, jsonify
import logging

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

from sqlalchemy.exc import SQLAlchemyError
from extensions import db
from routes.base_routes import base_bp
from config.database import init_db

app = Flask(__name__)

# Configuration
PORT = int(os.environ.get("PORT", 3618))
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")

# Initialize Database
init_db(app, db)

# Register Blueprints
app.register_blueprint(base_bp)

from services.telegram_bot import start_bot_thread, log_error_to_telegram

with app.app_context():
    # Import models here so SQLAlchemy knows about them before create_all
    from models.device_info import DeviceInfo
    
    # create tables if they don't exist
    try:
        db.create_all()
    except SQLAlchemyError as e:
        log_error_to_telegram(app, f"Database Connection Error: {str(e)}")
        logging.error(f"Database connection error (could not create tables): {e}")

if __name__ == '__main__':
    # Start Telegram Bot
    start_bot_thread(app)
    
    # Run on all interfaces so it's accessible
    app.run(host='0.0.0.0', port=PORT) 
    # use_reloader=False is important when running threads to avoid duplicate threads
