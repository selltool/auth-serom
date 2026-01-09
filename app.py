import os
import json
import datetime
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv
from utils import decrypt_ciphertext_b64

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration
PORT = int(os.environ.get("PORT", 3618))
SERVER_PRIVATE_KEY_B64 = os.environ.get("SERVER_PRIVATE_KEY_B64")

# Database Configuration
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "auth_serom")

# Connection Pooling options are handled by SQLAlchemy/Engine default, 
# but we can explicit set them if needed in SQLALCHEMY_ENGINE_OPTIONS.
# Flask-SQLAlchemy defaults are usually good, but here is explicit configuration.
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True
}

db = SQLAlchemy(app)

# Database Model
class DeviceInfo(db.Model):
    __tablename__ = 'device_info'
    sn = db.Column(db.String(255), primary_key=True)
    imei = db.Column(db.String(255))
    st_data = db.Column(db.Text) # Stores the extra ST keys as JSON or raw text
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<DeviceInfo {self.sn}>"

with app.app_context():
    # create tables if they don't exist
    try:
        db.create_all()
    except SQLAlchemyError as e:
        print(f"Database connection error (could not create tables): {e}")

@app.route('/healthy', methods=['POST'])
def healthy():
    # Try to get data from JSON 'data' field, or 'ciphertext_b64', or just raw body
    data = None
    if request.is_json:
        data = request.json.get('data') or request.json.get('ciphertext_b64')
    
    if not data:
        # Fallback to form data
        data = request.form.get('data') or request.form.get('ciphertext_b64')
    
    if not data:
        # Fallback to raw data if it looks like a b64 string
        raw = request.data.decode('utf-8').strip()
        if raw:
            data = raw

    if not data:
        return jsonify({"error": "No data provided"}), 400

    if not SERVER_PRIVATE_KEY_B64:
        return jsonify({"error": "Server configuration error: Missing Private Key"}), 500

    try:
        decrypted_text = decrypt_ciphertext_b64(data, SERVER_PRIVATE_KEY_B64)
        
        # Try to parse properties for DB update
        # Assuming decrypted text is JSON-like or contains the fields. 
        # If the user format is specific (e.g. SN|IMEI|ST...), this parsing logic might need adjustment.
        # For now, I will assume it's valid JSON for data extraction.
        
        sn = None
        imei = None
        st_data = {}
        
        try:
            json_data = json.loads(decrypted_text)
            if isinstance(json_data, dict):
                sn = json_data.get('SN') or json_data.get('sn')
                imei = json_data.get('Imei') or json_data.get('imei') or json_data.get('IMEI')
                
                # Extract keys starting with ST
                for k, v in json_data.items():
                    if k.upper().startswith('ST'):
                        st_data[k] = v
        except json.JSONDecodeError:
            # If not JSON, maybe we can't extract SN easily without more info on format.
            # But the requirement says "nhận về SN, Imei". 
            # I will log warning if extraction fails but still return the string.
            pass

        if sn:
            # Update Database
            device = DeviceInfo.query.get(sn)
            if not device:
                device = DeviceInfo(sn=sn)
                db.session.add(device)
            
            if imei:
                device.imei = imei
            
            if st_data:
                 # Merge or overwrite ST data
                 device.st_data = json.dumps(st_data)
            
            device.updated_at = datetime.datetime.utcnow()
            db.session.commit()

        return decrypted_text, 200

    except ValueError as ve:
        return jsonify({"error": f"Decryption error: {str(ve)}"}), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Internal error: {str(e)}"}), 500

if __name__ == '__main__':
    # Run on all interfaces so it's accessible
    app.run(host='0.0.0.0', port=PORT)
