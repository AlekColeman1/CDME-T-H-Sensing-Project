from dotenv import load_dotenv
import os
import mysql.connector

load_dotenv()

HOST = os.environ["MYSQL_HOST"]
PORT = int(os.environ.get("MYSQL_PORT", 3306))
USER = os.environ["MYSQL_USER"]
PASSWORD = os.environ["MYSQL_PASSWORD"]
DB_NAME = os.environ["MYSQL_DB"]

TABLES = {}

TABLES["readings"] = """
CREATE TABLE IF NOT EXISTS readings (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    sensor_id VARCHAR(64) NOT NULL,
    ts TIMESTAMP(3) NOT NULL,
    temperature_c DECIMAL(6,3) NOT NULL,
    humidity_pct DECIMAL(5,2) NOT NULL,
    INDEX idx_device_sensor_ts (device_id, sensor_id, ts)
) ENGINE=InnoDB;
"""

def main():
    # First ensure database
    conn0 = mysql.connector.connect(
        host=HOST,
        port=PORT,
        user=USER,
        password=PASSWORD,
    )
    cur0 = conn0.cursor()
    cur0.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} DEFAULT CHARSET utf8mb4")
    cur0.close()
    conn0.close()

    # Now create tables
    conn = mysql.connector.connect(
        host=HOST,
        port=PORT,
        user=USER,
        password=PASSWORD,
        database=DB_NAME,
    )
    cur = conn.cursor()
    for name, ddl in TABLES.items():
        cur.execute(ddl)
        print(f"Ensured: {name}")
    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()

