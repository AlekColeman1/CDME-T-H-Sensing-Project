import subprocess
import os
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
from logger import logger

load_dotenv()

# Configure MySQL connection
HOST = os.environ["MYSQL_HOST"]
PORT = int(os.environ.get("MYSQL_PORT", 3306))
USER = os.environ["MYSQL_USER"]
PASSWORD = os.environ["MYSQL_PASSWORD"]
DB_NAME = os.environ["MYSQL_DB"]

# Configure table name and where to save backups
TABLE = "readings"
BACKUP_DIR = "/home/alekcoleman/Desktop/Backups"

# Number of days between each backuo
RETENTION_DAYS = 60

# Max number of retires if backup fails
MAX_RETRIES = 5

# Delay (s) between each retry if backup fails
RETRY_DELAY = 30

os.makedirs(BACKUP_DIR, exist_ok=True)

# Configures name of backup file
timestamp = datetime.now().strftime("%Y-%m-%d_%I:%M")
backup_file = f"{BACKUP_DIR}/readings_{timestamp}.sql"
compressed_file = backup_file + ".gz"

WHERE_CLAUSE = f"ts < NOW() - INTERVAL {RETENTION_DAYS} DAY"

def run_backup() :
    # Outputs data to be backed up into the backup file
    with open(backup_file, "w") as f:
        result = subprocess.run([
            "mysqldump",
            f"-h{HOST}",
            f"-P{PORT}",
            f"-u{USER}",
            f"-p{PASSWORD}",
            DB_NAME,
            TABLE,
            "--where", WHERE_CLAUSE,
        ], stdout=f)
    print(result.returncode)
    print(os.path.getsize(backup_file))
    if result.returncode != 0:
        print("mysqldump failed")
        print(result.stderr)
    return result.returncode == 0

def verify():
    # Verifies backup was successful
    return os.path.exists(backup_file) and os.path.getsize(backup_file) > 200

def compress_backup():
    # Compresses backup file
    subprocess.run(["gzip", backup_file])
    return os.path.exists(compressed_file)

def delete_old_data():
    # Delete data that was backedup
    delete_query = f"DELETE FROM {TABLE} WHERE {WHERE_CLAUSE}"
    result = subprocess.run([
        "mysql",
        f"-h{HOST}",
        f"-P{PORT}",
        f"-u{USER}",
        f"-p{PASSWORD}",
        DB_NAME,
        "-e", delete_query
    ])
    return result.returncode == 0

def backup_retry():
    # Backup retry logic, if no retries needed this only runs once
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"Backup attempt {attempt}...")
        if run_backup() and verify():
            print("Backup verified")
            with open("last_backup.txt", "w") as f:
                f.write(datetime.now(timezone.utc).isoformat())
            logger.info("Database backup successful and verified.")
            if(compress_backup()):
                print("Backup compressed")
                logger.info("Backup file compressed successfully.")
                return True
        print("Backup failed, retrying...")
        time.sleep(RETRY_DELAY)
    return False

if backup_retry():
    if delete_old_data():
        print("Old data deleted")
        logger.info(f"Data older than {RETENTION_DAYS} days deleted successfully.")
    else:
        print("Backup succeeded but delete failed")
        logger.warning("Backup successful but failed to delete old data.")
else:
    print("Backup failed, aborting delete")
    logger.error(f"Database backup failed after {MAX_RETRIES} attempts. No data was deleted.")
