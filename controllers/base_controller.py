from flask import request, jsonify, render_template, current_app, session, redirect, url_for
from extensions import db
from models.device_info import DeviceInfo
from services.telegram_bot import log_error_to_telegram, send_telegram_notification
import json
import datetime
import os

WEB_PASSWORD = os.environ.get("WEB_PASSWORD", "Son1234@") # Default password if not set

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
    try:
        # Check both args (GET) and form/json (POST)
        sn = request.values.get('sn')
        imei = request.values.get('imei')
        stid = request.values.get('stid')

        if not sn and request.is_json:
            data = request.get_json()
            if data:
                sn = data.get('sn')
                imei = data.get('imei')
                stid = data.get('stid')

        if sn:
            # Update Database
            device = DeviceInfo.query.get(sn)
            if not device:
                device = DeviceInfo(sn=sn)
                db.session.add(device)
            
            if imei:
                device.imei = imei
            
            if stid:
                 # Update st_data
                 st_data_dict = {}
                 try:
                     if device.st_data:
                        st_data_dict = json.loads(device.st_data)
                 except:
                     pass
                 
                 st_data_dict['stid'] = stid
                 device.st_data = json.dumps(st_data_dict)
            
            device.updated_at = datetime.datetime.utcnow()
            db.session.commit()
            debug_key = os.environ.get('DEBUG_KEY')
            print(f"Debug Key: {debug_key}")
            if debug_key:
                msg = f"Device Request:\nSN: {sn}"
                if imei:
                    msg += f"\nIMEI: {imei}"
                if stid:
                    msg += f"\nSTID: {stid}"
                send_telegram_notification(current_app._get_current_object(), msg)

            # Return status
            return device.status, 200

        # If no SN provided, but might be a check
        return "Service is running", 200

    except Exception as e: 
        db.session.rollback()
        log_error_to_telegram(current_app._get_current_object(), f"Internal Processing Error: {str(e)}")
        return "Internal Processing Error", 500
