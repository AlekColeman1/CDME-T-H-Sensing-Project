from dotenv import load_dotenv
import os
import mysql.connector
from datetime import datetime, timezone

load_dotenv()

HOST = os.environ["MYSQL_HOST"]
PORT = int(os.environ.get("MYSQL_PORT", 3306))
USER = os.environ["MYSQL_USER"]
PASSWORD = os.environ["MYSQL_PASSWORD"]
DB_NAME = os.environ["MYSQL_DB"]
DEVICE_ID = os.environ.get("DEVICE_ID", "unknown-device")

def get_conn():
    return mysql.connector.connect(
        host=HOST,
        port=PORT,
        user=USER,
        password=PASSWORD,
        database=DB_NAME,
    )

def log_reading(temp_c: float, humidity_pct: float):
    conn = get_conn()
    cur = conn.cursor()

    ts = datetime.now(timezone.utc)

    sql = """
        INSERT INTO readings (device_id, ts, temperature_c, humidity_pct)
        VALUES (%s, %s, %s, %s)
    """

    cur.execute(sql, (DEVICE_ID, ts, float(temp_c), float(humidity_pct)))

    conn.commit()
    cur.close()
    conn.close()


