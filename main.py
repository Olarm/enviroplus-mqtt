#!/usr/bin/env python3
"""
Run mqtt broker on localhost: sudo apt-get install mosquitto mosquitto-clients

Example run: python3 mqtt-all.py --broker 192.168.1.164 --topic enviro --username xxx --password xxxx
"""

from datetime import datetime
import time
import toml
import psycopg2
from bme280 import BME280
from pms5003 import PMS5003, ReadTimeoutError, SerialTimeoutError
from enviroplus import gas

try:
    # Transitional fix for breaking change in LTR559
    from ltr559 import LTR559

    ltr559 = LTR559()
except ImportError:
    import ltr559

from subprocess import PIPE, Popen, check_output
from PIL import Image, ImageDraw, ImageFont
from fonts.ttf import RobotoMedium as UserFont
import json

import paho.mqtt.client as mqtt

try:
    from smbus2 import SMBus
except ImportError:
    from smbus import SMBus


# mqtt callbacks
def on_connect(client, userdata, flags, rc, properties):
    if rc == 0:
        print("connected OK")
    else:
        print("Bad connection Returned code=", rc)


def on_publish(client, userdata, mid, rc, properties):
    return


# Read values from BME280 and return as dict
def read_bme280(bme280):
    # Compensation factor for temperature
    comp_factor = 2.3
    values = {}
    cpu_temp = get_cpu_temperature()
    raw_temp = bme280.get_temperature()  # float
    comp_temp = raw_temp - ((cpu_temp - raw_temp) / comp_factor)
    values["temperature"] = round(comp_temp, 1)
    values["pressure"] = round(bme280.get_pressure(), 1)
    values["humidity"] = round(bme280.get_humidity(), 1)
    data = gas.read_all()
    values["oxidised"] = round(data.oxidising / 1000, 1)
    values["reduced"] = round(data.reducing / 1000, 1)
    values["nh3"] = round(data.nh3 / 1000, 1)
    values["lux"] = round(ltr559.get_lux(), 1)
    return values


# Read values PMS5003 and return as dict
def read_pms5003(pms5003):
    values = {}
    try:
        pm_values = pms5003.read()  # int
        values["pm1"] = pm_values.pm_ug_per_m3(1)
        values["pm25"] = pm_values.pm_ug_per_m3(2.5)
        values["pm10"] = pm_values.pm_ug_per_m3(10)
    except ReadTimeoutError:
        pms5003.reset()
        pm_values = pms5003.read()
        values["pm1"] = pm_values.pm_ug_per_m3(1)
        values["pm25"] = pm_values.pm_ug_per_m3(2.5)
        values["pm10"] = pm_values.pm_ug_per_m3(10)
    return values


# Get CPU temperature to use for compensation
def get_cpu_temperature():
    process = Popen(
        ["vcgencmd", "measure_temp"], stdout=PIPE, universal_newlines=True
    )
    output, _error = process.communicate()
    return float(output[output.index("=") + 1:output.rindex("'")])


# Get Raspberry Pi serial number to use as ID
def get_serial_number():
    with open("/proc/cpuinfo", "r") as f:
        for line in f:
            if line[0:6] == "Serial":
                return line.split(":")[1].strip()


# Check for Wi-Fi connection
def check_wifi():
    if check_output(["hostname", "-I"]):
        return True
    else:
        return False


def read_config():
    path = "config.toml"
    with open(path, "rb") as f:
        config = toml.load(f)

    return config


def get_db_conn_string(config):
    return(f"""
        dbname={config["db"]["db"]}
        user={config["db"]["user"]}
        password={config["db"]["password"]}
        host={config["db"]["host"]}
    """)


def insert_data(data):
    ts = datetime.now()
    conn_str = get_db_conn_string()
    with psycopg2.connect(conn_str) as conn:
        with conn.cursor() as cur:
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
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING""",
                (
                    ts,
                    data["temperature"],
                    data["pressure"],
                    data["humidity"],
                    data["oxidised"],
                    data["reduced"],
                    data["nh3"],
                    data["lux"]
                )
            )


def main():
    config = read_config()

    mqtt_config = config.get("mqtt")
    device_serial_number = get_serial_number()
    device_id = "raspi-" + device_serial_number

    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=device_id)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_publish = on_publish

    mqtt_client.connect(mqtt_config["host"], mqtt_config["port"])

    bus = SMBus(1)

    # Create BME280 instance
    bme280 = BME280(i2c_dev=bus)

    # Set an initial update time
    mqtt_update_time = time.time()
    db_update_time = time.time()

    # Set start time
    start_time = time.time()

    # Main loop to read data, display, and send over mqtt
    mqtt_client.loop_start()

    k = 0
    while True:
        try:
            values = read_bme280(bme280)
            k += 1
            if k == 20:
                print(values)
                k = 0

            now = time.time()
            time_since_mqtt_update = now - mqtt_update_time
            time_since_db_update = now - db_update_time
            start_delay = now - start_time
            if start_delay > 60*20:
                if time_since_mqtt_update >= mqtt_config["period"]:
                    try:
                        mqtt_update_time = time.time()
                        mqtt_client.publish(mqtt_config["topic"]+"/slow", json.dumps(values), retain=False)
                    except Exception as e:
                        print("Error publishing to mqtt: ", e)
                if time_since_db_update >= config["db"]["period"]:
                    try:
                        insert_data(values)
                    except Exception as e:
                        print("Error inserting into db: ", e)
                
        except Exception as e:
            print(e)
        


if __name__ == "__main__":
    main()
