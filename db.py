import sqlite3
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


def initiate_db():
    logger.info("Initiating DB")
    conn = sqlite3.connect("enviro.db")

    create_str = """
        CREATE TABLE IF NOT EXISTS enviro(
            timestamp datetime not null unique,
            temperature double not null, 
            pressure double not null, 
            humidity double not null, 
            oxidised double not null, 
            reduced double not null, 
            nh3 double not null, 
            lux double not null 
        )
    """

    conn.execute(create_str)
    logger.info("DB initiation complete")



def check_last_insert_ts():
    logger.debug("Checking if system time > last logged DB time")
    conn = sqlite3.connect("enviro.db")
    ts = datetime.now(ZoneInfo("Europe/Oslo"))
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT timestamp
            FROM enviro
            ORDER BY timestamp DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        last_db_ts = datetime.fromisoformat(row[0])
        if ts > last_db_ts:
            logger.debug("Time seems fine.")
            return True
        else:
            return False
    except Exception as e:
        logger.error(f"Error getting ts from db:\n{e}")
        return False
        


def insert_local_db(data):
    conn = sqlite3.connect("enviro.db")
    ts = datetime.now(ZoneInfo("Europe/Oslo"))

    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO
                enviro (
                    timestamp,
                    temperature,
                    pressure,
                    humidity,
                    oxidised,
                    reduced,
                    nh3,
                    lux
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING""",
            (
                ts,
                data["temperature"],
                data["pressure"],
                data["humidity"],
                data["oxidised"],
                data["reduced"],
                data["nh3"],
                data["lux"],
            )
        )
        conn.commit()
        logger.debug(f"Inserted into local db with timestamp {ts}")
        conn.close()
    except Exception as e:
        logger.error(f"Error logging to db:\n{e}")



def test_insert():
    data = {
        "temperature": -1.1,
        "pressure": -1.2,
        "humidity": -1.3,
        "oxidised": -1.4,
        "reduced": -1.5,
        "nh3": -1.6,
        "lux": -1.7
    }

    insert_local_db(data)

    conn = sqlite3.connect("enviro.db")
    cur = conn.cursor()

    r = cur.execute("""
        SELECT * FROM enviro WHERE 
            temperature = -1.1;
    """)

    data = r.fetchall()
    logger.info(f"Got {data}")

    cur.execute("""
        DELETE FROM enviro WHERE
            temperature = -1.1;
    """)
    conn.commit()
    conn.close()

    return "success"