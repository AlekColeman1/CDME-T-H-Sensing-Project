from flask import Flask, render_template, request, send_file
from datetime import datetime
from pathlib import Path
import csv
import io
import json
import os

import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
from flask import jsonify, request



app = Flask(__name__)
TIME_FORMAT = "%m/%d/%Y %H:%M"

"""CSV_PATH = Path("Data.csv")

def load_csv():
    rows=[]
    if not CSV_PATH.exists():
        return rows
    
    with CSV_PATH.open("r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                timestamp = datetime.fromisoformat(row["Time"])
                temp = float(row["Temperature"])
                hum = float(row["Humidity"])
                rows.append({
                    "Time": timestamp,
                    "Temperature": temp,
                    "Humidity": hum
                })
            except:
                continue
    return rows"""
load_dotenv()

DB_HOST = os.environ.get("MYSQL_HOST", "localhost")
DB_PORT = int(os.environ.get("MYSQL_PORT", 3306))
DB_USER = os.environ.get("MYSQL_USER", "env_user")
DB_PASS = os.environ.get("MYSQL_PASS", "env_pass")
DB_NAME = os.environ.get("MYSQL_DB", "envmon")
DEVICE_ID = os.environ.get("DEVICE_ID")  # optional filter by device/sensor

def get_conn():
    """Create and return a new MySQL connection."""
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
    )

def load_data_from_db(start_dt=None, end_dt=None):
    """
    Query readings from the database between start_dt and end_dt.

    Returns a list of dicts with keys: Time (datetime), Temperature, Humidity.
    """
    rows = []
    try:
        conn = get_conn()
        cur = conn.cursor(dictionary=True)

        # Base query
        query = """
            SELECT ts, temperature_c, humidity_pct
            FROM readings
            WHERE 1=1
        """
        params = []

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
            # row['ts'] is a datetime object from MySQL
            rows.append({
                "Time": row["ts"],
                "Temperature": float(row["temperature_c"]),
                "Humidity": float(row["humidity_pct"]),
            })

        cur.close()
        conn.close()
    except Error as e:
        print("DB error while loading data:", e)

    return rows

@app.route("/", methods=["GET"])
def home():
    data = load_data_from_db()
    if not data:
        return "CSV file not found or empty"
    
    data.sort(key=lambda r: r["Time"])

    latest = data[-1]

    start_date = request.args.get("start")
    end_date = request.args.get("end")

    if start_date and end_date:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        filtered = [
            r for r in data if start_dt <= r["Time"] <= end_dt
        ]
    else:
        filtered = data

    labels = json.dumps([r["Time"].isoformat() for r in filtered])
    tempData = json.dumps([r["Temperature"] for r in filtered])
    humData = json.dumps([r["Humidity"] for r in filtered])
    return render_template(
        "index.html",
        latest=latest,
        filtered=filtered,
        rows= data,
        labels=labels,
        tempData=tempData,
        humData=humData,
        has_filter=bool(start_date and end_date)
    )

@app.route("/download")
def download():
    data = load_data_from_db()

    start = request.args.get("start")
    end = request.args.get("end")

    if start and end:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        data = [r for r in data if start_dt <= r["Time"] <= end_dt]

    output=io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Time", "Temperature", "humidity"])

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
    start = request.args.get("start")
    end = request.args.get("end")

    start_dt = None
    end_dt = None

    # datetime-local → Python datetime
    if start:
        start_dt = datetime.fromisoformat(start)
    if end:
        end_dt = datetime.fromisoformat(end)

    rows = load_data_from_db(start_dt, end_dt)

    return jsonify([
        {
            "Time": r["Time"].isoformat(),  # IMPORTANT
            "Temperature": r["Temperature"],
            "Humidity": r["Humidity"]
        }
        for r in rows
    ])

if __name__ == "__main__":app.run(host="0.0.0.0", port=5000)
