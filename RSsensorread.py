from pymodbus.client import ModbusSerialClient
import time
from db_logger import log_reading

# Configure RS485 connection
client = ModbusSerialClient(
    port='/dev/ttyUSB0',          # Change to your port (e.g., '/dev/ttyUSB0' on Linux)
    baudrate=9600,
    parity='N',
    stopbits=1,
    bytesize=8,
    timeout=1
)

if not client.connect():
    print("Unable to connect to RS485 device")
    exit()

sensor_addresses = [1, 2, 3, 4]

def read_sensor(address):
    try:
        response = client.read_holding_registers(
            address=0x0000,
            count=2,
            device_id=address
        )

        if response.isError():
            print(f"Error reading sensor {address}")
            return None

        humidity_raw = response.registers[0]
        temperature_raw = response.registers[1]

        # Handle negative temperature if needed
        if temperature_raw > 32767:
            temperature_raw -= 65536

        humidity = humidity_raw / 10.0
        temperature = temperature_raw / 10.0

        return temperature, humidity

    except Exception as e:
        print(f"Exception reading sensor {address}: {e}")
        return None


try:
    while True:
        print("----- Sensor Readings -----")
        temperatures = []
        humidities = []
        for addr in sensor_addresses:
            result = read_sensor(addr)
            if result:
            
                temperature, humidity = result
                temperature = (temperature * 9/5) + 32  # Convert to Fahrenheit
                temperatures.append(temperature)

                humidities.append(humidity)
                print(f"Sensor {addr}: {temperature:.1f} °F | {humidity:.1f} %RH")
                log_reading(f"SEN0438:{addr}", temperature, humidity)

            else:
                print(f"Sensor {addr}: No data")

        # Calculate average temperature
        if temperatures and humidities:
            avg_temp = sum(temperatures) / len(temperatures)
            avg_hum = sum(humidities) / len(humidities)
            print(f"\nAverage Temperature: {avg_temp:.2f} °F : Average Humidity: {avg_hum:.2f} %RH")
            
            log_reading("SEN0438:avg", avg_temp, avg_hum)
        else:
            print("\nAverage Temperature: No valid data")

        print()
        time.sleep(2)

except KeyboardInterrupt:
    print("Stopping...")

finally:
    client.close()