from pymodbus.client import ModbusSerialClient
import time
from db_logger import log_reading
from FlaskSite import load_settings
from logger import logger
import os

# List of sensor addresses to read from
SENSOR_ADDRESSES = [1, 2, 3, 4]

PORT = '/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0'        # Serial port for RS485 adapter

# Track connection state to avoid repeated error logging
last_connection_state = True

# Track per-sensor error state to avoid repeated error logging
sensor_error_state = {}

def create_client():
    # Configure RS485 connection
    return ModbusSerialClient(
        port=PORT,
        baudrate=9600,
        parity='N',
        stopbits=1,
        bytesize=8,
        timeout=1
    )

# Track device connection
client = None

def ensure_connection():
    # Ensure device is connected
    global client

    if not os.path.exists(PORT):
        if client:
            try:
                client.close()
            except:
                pass
            client = None
        return False
    if client is None:
        client = create_client()
    try:
        if client.connect():
            return True
        else:
            logger.error("Connection failed")
    except Exception as e:
        print(f"Connection error: {e}")
        try:
            client.close()
        except:
            pass
        client = None
        return False

# Convert Celsius to Fahrenheit
def c_to_f(c):
    return (c * 9/5) + 32


def read_sensor(address):
    """
    Read temperature and humidity data from single sensor
    
    Returns:
        (temperature, humidity) tuple if successful, None if error
    """
    global client
    try:
        if client is None:
            return None
        
        response = client.read_holding_registers(
            address=0x0000,        #Starting register address
            count=2,               #Number of registers to read (temp + humidity)
            device_id=address
        )

        # Handle Modbus errors and log them only on state change
        if response.isError():
            if not sensor_error_state.get(address, False):
                print(f"Error reading sensor {address}: {response}")
                logger.error(f"Error reading sensor {address}: {response}")
                sensor_error_state[address] = True
            return None
        else:
            sensor_error_state[address] = False

        humidity_raw = response.registers[0]
        temperature_raw = response.registers[1]

        # Handle signed 16 bit values for temperature(negative values)
        if temperature_raw > 32767:
            temperature_raw -= 65536

        # Convert raw value to actual value (e.g. 160 = 16.0 °C)
        humidity = humidity_raw / 10.0
        temperature = temperature_raw / 10.0

        return temperature, humidity

    except Exception as e:
        # Log exceptions only on state change to avoid flooding logs
        if not sensor_error_state.get(address, False):
            print(f"Exception reading sensor {address}: {e}")
            logger.error(f"Exception reading sensor {address}: {e}")
            sensor_error_state[address] = True
        try:
            client.close()
        except:
            pass
        client = None
        return None


try:
    while True:
        """
        Manages connection to RS485 device
        Allows for automatic reconnection if connection is lost, with logging of connection status changes
        """
        
        if not ensure_connection():
            print("Waiting for RS485 device...")
            time.sleep(5)
            continue

        
        print("----- Sensor Readings -----")

        # Load settings
        settings = load_settings()
        SENSOR_READING_INTERVAL = settings.get("reading_interval", 3.0)

        # Store readings for each sensor to average out noise later
        sensor_data = {addr: {"temps": [], "hums": []} for addr in SENSOR_ADDRESSES}

        # Take 10 readings from each sensor, 3 seconds apart
        # This makes each sensor reading more accurate
        # This is also why the time between readings is 30 seconds if reading interval is set to 0
        for i in range(1):
            for addr in SENSOR_ADDRESSES:
                result = read_sensor(addr)
                if result is None:
                    print(f"Reading {i+1} for sensor {addr}: No data")
                    continue

                temperature, humidity = result
                # Store readings for averaging
                sensor_data[addr]["temps"].append(temperature)
                sensor_data[addr]["hums"].append(humidity)

                print(f"Reading {i+1} for sensor {addr}: {temperature:.1f} °C | {humidity:.1f} %RH")

            time.sleep(3)

        # Per sensor averaging
        avg_temps = {}
        avg_hums = {}

        for addr in SENSOR_ADDRESSES:
            temps = sensor_data[addr]["temps"]
            hums = sensor_data[addr]["hums"]

            if temps and hums:
                avg_temp = sum(temps) / len(temps)
                avg_hum = sum(hums) / len(hums)

                # Convert from Celsius to Fahrenheit
                avg_temp_f = c_to_f(avg_temp)

                avg_temps[addr] = avg_temp_f
                avg_hums[addr] = avg_hum

                print(f"Sensor {addr} AVG: {avg_temp_f:.1f} °F | {avg_hum:.1f} %RH")
                # Save each reading to the database with sensor identifier
                log_reading(f"SEN0438:{addr}", avg_temp_f, avg_hum)
            else:
                # No valid data collected for sensor
                print(f"Sensor {addr}: No valid data")
                logger.warning(f"Sensor {addr}: No valid data")

        # Compute overall averages
        if avg_temps and avg_hums:
            overall_temp = sum(avg_temps.values()) / len(avg_temps)
            overall_hum = sum(avg_hums.values()) / len(avg_hums)
            print(f"\nAverage Temperature: {overall_temp:.2f} °F | Average Humidity: {overall_hum:.2f} %RH")
            # Save overall average to database with generic identifier
            log_reading("SEN0438:avg", overall_temp, overall_hum)
        else:
            print("\nAverage Temperature: No valid data")
            logger.warning("Average Temperature: No valid data")

        print()
        
        time.sleep(SENSOR_READING_INTERVAL)

except KeyboardInterrupt:
    print("Stopping...")

finally:
    if client is not None:
        try:
            client.close()
        except:
            pass
