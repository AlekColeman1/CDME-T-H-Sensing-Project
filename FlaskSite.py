from flask import Flask, render_template, request, send_file, jsonify
from datetime import datetime
from pathlib import Path
import csv
import io
import json
import os
from collections import deque
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error
import smtplib
from email.mime.text import MIMEText
from logger import logger

load_dotenv()

# Specify path to settings file and log file 
SETTINGS_FILE = Path("settings.json")
LOG_FILE = "/home/cdme/Desktop/SystemLogger.log"

# Cache settings in memory to avoid file I/O on every read
SETTINGS_CACHE = None


def load_settings():
    
    # Loads settings from disk once and cahces them to memory   
    global SETTINGS_CACHE
    if SETTINGS_CACHE is not None:
        return SETTINGS_CACHE
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, "r") as f:
            SETTINGS_CACHE = json.load(f)
    else:
        # Default settings if no settings file exists
        SETTINGS_CACHE = {
            # Default thresholds for each sensor and average reading
            "SEN0438:1": {"temp_min": 65, "temp_max": 80, "hum_min": 0, "hum_max": 60},
            "SEN0438:2": {"temp_min": 65, "temp_max": 80, "hum_min": 0, "hum_max": 60},
            "SEN0438:3": {"temp_min": 65, "temp_max": 80, "hum_min": 0, "hum_max": 60},
            "SEN0438:4": {"temp_min": 65, "temp_max": 80, "hum_min": 0, "hum_max": 60},
            "SEN0438:avg": {"temp_min": 65, "temp_max": 80, "hum_min": 0, "hum_max": 60},
            # Defines how far from threshold the user is warned
            "warning_buffer": 2.0,
            # Defines how often the sensors read data, if 0 then sensors will run every 30 seconds
            "reading_interval": 4.0,
            # Sensor names for UI display
            "SENSOR_NAMES" : {
                "SEN0438:1": "Sensor 1",
                "SEN0438:2": "Sensor 2",
                "SEN0438:3": "Sensor 3",
                "SEN0438:4": "Sensor 4",
                "SEN0438:avg": "Room Average"
            },
            # Enables/Disables all email alerts 
            "email_alerts": True
        }
    return SETTINGS_CACHE

def save_settings(settings):
    # Writes settings to memory and updates cache
    global SETTINGS_CACHE
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)
    SETTINGS_CACHE = settings

# Email Alert Configuration
EMAIL_HOST = os.environ.get("EMAIL_HOST")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")
# List of recipients from environmental variable
ALERT_TO = os.environ.get("ALERT_TO", "")
ALERT_LIST = [email.strip() for email in ALERT_TO.split(",") if email.strip()]

# Track alert state so emails do not get spammed
LAST_ALERT_STATE = {}
# Track log state so logs do not get spammed
LAST_LOG_STATE = {}


def get_latest_reading(sensor_id):
    # Returns most recent database reading for a sensor
    rows = load_data_from_db(sensor_id)
    return rows[-1] if rows else None

def send_email_alert(sensor, alarms, temp, hum, timestamp):
    
    # Sends email notification when sensor enters alarm state
    subject = f"🚨 Sensor Alarm: {sensor}"
    body = f"""Sensor: {sensor}
    Time: {timestamp}
    Temperature: {temp:.1f} F
    Humidity: {hum:.1f} %
    Alarms: {', '.join(alarms)}
    """
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_USER
    msg['To'] = ", ".join(ALERT_LIST)

    try:
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.connect(EMAIL_HOST, EMAIL_PORT)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(
            EMAIL_USER,
            ALERT_LIST,
            msg.as_string()
        )
        server.quit()
        print(f"Email sent: {sensor} {alarms}")
    except Exception as e:
        print("Failed to send email:", e)
        logger.error(f"Failed to send email alert: {e}, Sensor: {sensor}, Alarms: {alarms}")


# Flask Application Setup
app = Flask(__name__)

# MySQL configuration from environmental varibles
DB_HOST = os.environ.get("MYSQL_HOST", "localhost")
DB_PORT = int(os.environ.get("MYSQL_PORT", 3306))
DB_USER = os.environ.get("MYSQL_USER", "env_user")
DB_PASS = os.environ.get("MYSQL_PASS", "env_pass")
DB_NAME = os.environ.get("MYSQL_DB", "envmon")
DEVICE_ID = os.environ.get("DEVICE_ID")

def get_last_backup_time():
    # Get timestamp from last database backup
    try:
        with open("last_backup.txt") as f:
            ts = f.read().strip()
            return datetime.fromisoformat(ts)
    except Exception:
        return None
    

def check_sensor_alarm(sensor, temp, hum):
    """
    Compares sensor values against threshold setting

    Returns:
        alarms: >= Max
        warnings: < Max and >= Max - Warning Buffer
    """
    settings = load_settings()

    # Gets per-sensor limit from settings
    sensor_limits = settings.get("SENSOR-LIMITS", {})

    # Use average configuration if missing
    limits = sensor_limits.get(
        sensor,
        sensor_limits.get("SEN0438:avg", {})
    )

    WARNING_BUFFER = settings.get("warning_buffer", 2.0)
   
    alarms = []
    warnings = []

    # Temperature Checks
    if temp >= limits["temp_max"]:
        alarms.append("TEMP HIGH")
        
    elif temp <= limits["temp_min"]:
        alarms.append("TEMP LOW")
        
    elif temp >= limits["temp_max"] - WARNING_BUFFER:
        warnings.append("Temp approaching HIGH")
        
    elif temp <= limits["temp_min"] + WARNING_BUFFER:
        warnings.append("Temp approaching LOW")
        
    # Humidity Checks
    if hum >= limits["hum_max"]:
        alarms.append("HUM HIGH")
        
    elif hum <= limits["hum_min"]:
        alarms.append("HUM LOW")
        
    elif hum >= limits["hum_max"] - WARNING_BUFFER:
        warnings.append("Humidity approaching HIGH")
       
    elif hum <= limits["hum_min"] + WARNING_BUFFER:
        warnings.append("Humidity approaching LOW")
        

    return alarms, warnings


def parse_dates(start, end):
    # Helper function to format database dates to objects
    return (
        datetime.fromisoformat(start) if start else None,
        datetime.fromisoformat(end) if end else None
    )

def format_row(r):
    # Helper function to normalize DB row format
    return{ 
        "Time": r["Time"].isoformat(),
        "Temperature": r["Temperature"],
        "Humidity": r["Humidity"]
    }

def get_conn():
    # Create new MySQL connection
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
    )

def load_data_from_db(sensor_id, start_dt=None, end_dt=None):
    """
    Query sensor readings from database 
    Returns ordered time series data
    """
    
    rows = []
    try:
        conn = get_conn()
        cur = conn.cursor(dictionary=True)

        # Base query
        query = """
        SELECT ts, temperature_c, humidity_pct
        FROM readings
        WHERE sensor_id = %s
        """

        params = [sensor_id]

        # Optional filter by device/sensor
        if DEVICE_ID:
            query += " AND device_id = %s"
            params.append(DEVICE_ID)

        # Optional time filters
        if start_dt is not None:
            query += " AND ts >= %s"
            params.append(start_dt)

        if end_dt is not None:
            query += " AND ts <= %s"
            params.append(end_dt)

        query += " ORDER BY ts"

        cur.execute(query, params)

        for row in cur:
            rows.append({
                "Time": row["ts"],
                "Temperature": float(row["temperature_c"]),
                "Humidity": float(row["humidity_pct"]),
            })

        cur.close()
        conn.close()
    except Error as e:
        print("DB error while loading data:", e)
        logger.error(f"Database error while loading data: {e}")

    return rows

@app.route("/", methods=["GET"])
def home():

    # Load cached settings
    settings = load_settings()

    # Get selected sensor from URL query  
    sensor = request.args.get("sensor", "SEN0438:avg")

    # Load all data from DB for that sensor
    data = load_data_from_db(sensor)
    if not data:
        return "Database is empty or not accessible."

    # Most recent reading
    latest = data[-1]

    # Get time range to filter data
    start_date = request.args.get("start")
    end_date = request.args.get("end")

    start_dt, end_dt = parse_dates(start_date, end_date)

    if start_date and end_date:
        filtered = [
            r for r in data if start_dt <= r["Time"] <= end_dt
        ]
    else:
        filtered = data
    
    # Get timestamp for last backup
    last_backup = get_last_backup_time()

    #Convert data into jason arrays
    labels = json.dumps([r["Time"].isoformat() for r in filtered])
    tempData = json.dumps([r["Temperature"] for r in filtered])
    humData = json.dumps([r["Humidity"] for r in filtered])

    # Render all variables for dashboard
    return render_template(
        "index.html",
        latest=latest,
        filtered=filtered,
        rows= data,
        labels=labels,
        tempData=tempData,
        humData=humData,
        sensor=sensor,
        settings = settings,
        last_backup=last_backup,
        has_filter=bool(start_date and end_date)
    )

@app.route("/download")
def download():
    # Get all sensor data
    data = load_data_from_db(request.args.get("sensor", "SEN0438:avg"))

    start = request.args.get("start")
    end = request.args.get("end")
    start_dt, end_dt = parse_dates(start, end)

    if start and end:
        data = [r for r in data if start_dt <= r["Time"] <= end_dt]

    output=io.StringIO()
    writer = csv.writer(output)
    # CSV header row
    writer.writerow(["Time", "Temperature", "humidity"])

    # Write each row into CSV
    for r in data:
        writer.writerow([r["Time"].isoformat(), r["Temperature"], r["Humidity"]])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name="FilteredData.csv"
    )
    
@app.route("/data")
def data():
  
    sensor = request.args.get("sensor", "SEN0438:avg")
    start = request.args.get("start")
    end = request.args.get("end")

    start_dt, end_dt = parse_dates(start, end)

    rows = load_data_from_db(sensor, start_dt, end_dt)
    
    # Returns clean JSON format for charts
    return jsonify([
        format_row(r) for r in rows
    ])

@app.route("/api/live")
def api_live():

    sensor = request.args.get("sensor", "SEN0438:avg")
    latest = get_latest_reading(sensor)
    if not latest:
        return jsonify({})
    settings = load_settings()
    SENSORS = ["SEN0438:1", "SEN0438:2", "SEN0438:3", "SEN0438:4"]

    # Track state changes for logging and email
    for sensor_id in SENSORS:
        latest_sensor = get_latest_reading(sensor_id)
        if not latest_sensor:
            continue
        alarms,warnings = check_sensor_alarm(
            sensor_id,
            latest_sensor["Temperature"],
            latest_sensor["Humidity"]
        )
        if alarms:
            current_state = "ALARM"
        elif warnings:
            current_state = "WARNING"
        else:
            current_state = "NORMAL"
        previous_state = LAST_LOG_STATE.get(sensor_id, "NORMAL")
        if current_state != previous_state:
            if current_state == "ALARM":
                logger.error(f"{sensor_id} entered ALARM state: {alarms}")
            elif current_state == "WARNING":
                logger.warning(f"{sensor_id} entered WARNING state: {warnings}")
            elif current_state == "NORMAL":
                logger.info(f"{sensor_id} returned to NORMAL state")
        LAST_LOG_STATE[sensor_id] = current_state
        print(f"{sensor_id} -> Alarms: {alarms}, Warnings: {warnings}")
        
        if settings.get("email_alerts", True):
            if alarms:
                if not LAST_ALERT_STATE.get(sensor_id, False):
                    send_email_alert(
                        sensor_id,
                        alarms,
                        latest_sensor["Temperature"],
                        latest_sensor["Humidity"],
                        latest_sensor["Time"]
                    )
                    LAST_ALERT_STATE[sensor_id] = True
            else:
                LAST_ALERT_STATE[sensor_id] = False
        else:
            LAST_ALERT_STATE[sensor_id] = False
    return jsonify({
        "Time": latest["Time"].isoformat(),
        "Temperature": latest["Temperature"],
        "Humidity": latest["Humidity"],
        "alarms": alarms,
        "warnings": warnings
    })

@app.route("/api/get_thresholds")
def get_thresholds_api():
    sensor = request.args.get("sensor", "SEN0438:avg")
    settings = load_settings()

    sensor_limits = settings.get("SENSOR-LIMITS", {})

    limits = sensor_limits.get(
        sensor,
        sensor_limits.get("SEN0438:avg", {})
    )

    return jsonify(limits)

@app.route("/api/update_settings", methods=["POST"])
def update_settings():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400
        settings = load_settings()

        # Updates settings values
        settings["warning_buffer"] = float(data.get("warning_buffer") or 2.0)
        settings["reading_interval"] = float(data.get("reading_interval") or 4.0)
        settings["SENSOR_NAMES"] = data.get("sensor_name", {})
        settings["email_alerts"] = bool(data.get("email_alerts", True))

        if "SENSOR-LIMITS" not in settings:
            settings["SENSOR-LIMITS"] = {}
        for sensor, limits in data.get("sensor_limits", {}).items():
            settings["SENSOR-LIMITS"][sensor] = limits
        save_settings(settings)
        return jsonify({"Success": True}), 200
    except Exception as e:
        return jsonify({"Success": False}), 500


@app.route("/api/recent")
def api_recent(): 
    # Gets 50 most recent readings
    sensor = request.args.get("sensor", "SEN0438:avg")
    
    limit = int(request.args.get("limit", 50))

    rows = load_data_from_db(sensor)
    rows = rows[-limit:]

    return jsonify([
        format_row(r) for r in rows
    ])


@app.route("/api/settings", methods=["GET"])
def get_Settings():
    # Returns full settings to frontend
    settings = load_settings()
    return jsonify(settings)

@app.route("/api/last_backup")
def api_last_backup():
    # Return timestamp of most recent Database backup
    last_backup = get_last_backup_time()
    return {"last_backup": last_backup if last_backup else "Never"}
@app.route("/api/logs")
def api_logs():
    # Reds 30 most recent logs and returns any with error tag
    try:
        with open(LOG_FILE, "r") as f:
            lines = deque(f, maxlen=30)
            important = [line.strip() for line in lines if "ERROR" in line]
            return jsonify(important)
    except Exception as e:
        return jsonify({"error": str(e)})
    
# Start Flask Server
if __name__ == "__main__":app.run(host="0.0.0.0", port=5000)
