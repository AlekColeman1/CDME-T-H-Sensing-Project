from dotenv import load_dotenv
import os
import mysql.connector
"""
This file is to show contents of database only
"""
load_dotenv()

HOST = os.environ["MYSQL_HOST"]
PORT = int(os.environ.get("MYSQL_PORT", 3306))
USER = os.environ["MYSQL_USER"]
PASSWORD = os.environ["MYSQL_PASSWORD"]
DB_NAME = os.environ["MYSQL_DB"]

def get_conn():
    return mysql.connector.connect(
        host=HOST,
        port=PORT,
        user=USER,
        password=PASSWORD,
        database=DB_NAME,
    )  

def show_readings():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM readings ORDER BY ts DESC")
    rows = cur.fetchall()
    headers = [desc[0] for desc in cur.description]
    print("\t".join(headers))
    for row in rows:
        print("\t".join(str(x) for x in row))

    cur.close()
    conn.close()

if __name__ == "__main__":
    show_readings() 
