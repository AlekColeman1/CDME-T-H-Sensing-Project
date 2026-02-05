'''
import time
import board
import adafruit_dht
from db_logger import log_reading

# Initialize sensors
dht1 = adafruit_dht.DHT11(board.D4)
dht2 = adafruit_dht.DHT11(board.D17)

def read_sensor(sensor):
    try:
        return sensor.temperature, sensor.humidity
    except RuntimeError:
        return None, None

while True:
    t1, h1 = read_sensor(dht1)
    t2, h2 = read_sensor(dht2)

    if None not in (t1, h1, t2, h2):
        avg_temp = (t1 + t2) / 2
        avg_hum = (h1 + h2) / 2

        print(f"Sensor 1 -> Temp: {t1:.1f}°C  Humidity: {h1:.1f}%")
        print(f"Sensor 2 -> Temp: {t2:.1f}°C  Humidity: {h2:.1f}%")
        print(f"Average  -> Temp: {avg_temp:.1f}°C  Humidity: {avg_hum:.1f}%")
        print("-" * 50)
        log_reading("dht11_1", t1, h1)
        log_reading("dht11_2", t2, h2)
    else:
        print("Sensor read error, retrying...")

    time.sleep(2)
'''
import time
import board
import adafruit_dht
from db_logger import log_reading


# Initialize sensors
dht1 = adafruit_dht.DHT11(board.D4)
dht2 = adafruit_dht.DHT11(board.D17)


def read_sensor(sensor):
    try:
        return sensor.temperature, sensor.humidity
    except RuntimeError:
        return None, None

while True:
    t1, h1 = read_sensor(dht1)
    t2, h2 = read_sensor(dht2)

    t1 = (t1 * 9/5 + 32) if t1 is not None else None
    t2 = (t2 * 9/5 + 32) if t2 is not None else None

    if t1 is not None and h1 is not None:
        print(f"Sensor 1 -> Temp: {t1:.1f}°F  Humidity: {h1:.1f}%")
        log_reading("dht11_1", t1, h1)

    
    if t2 is not None and h2 is not None:
        print(f"Sensor 2 -> Temp: {t2:.1f}°F  Humidity: {h2:.1f}%")
        log_reading("dht11_2", t2, h2)

    if None not in (t1, h1, t2, h2):
        avg_temp = (t1 + t2) / 2
        avg_hum = (h1 + h2) / 2
        print(f"Average  -> Temp: {avg_temp:.1f}°F  Humidity: {avg_hum:.1f}%")

    print("-" * 50)

    time.sleep(5)