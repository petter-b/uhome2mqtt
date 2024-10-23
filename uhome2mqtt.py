 
import os
import time
import sys
import signal
import json
import logging
from datetime import datetime, timezone
import schedule
from mqttclient import MqttPubClient


from uhome import Uhome, UHOME_THERMOSTAT_KEYS

# Configuration from environment variables
UHOME_ADDR: str = os.getenv('UHOME_ADDR')

UPDATE_INTERVAL: int = int(os.getenv('UPDATE_INTERVAL', '60'))  # seconds

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# MQTT parameters
MQTT_BROKER: str = os.getenv('MQTT_BROKER', 'localhost')
MQTT_PORT: int = int(os.getenv('MQTT_PORT', '1883'))
MQTT_USERNAME: str = os.getenv('MQTT_USERNAME', '')
MQTT_PASSWORD: str = os.getenv('MQTT_PASSWORD', '')
MQTT_TOPIC_PREFI: str = os.getenv('MQTT_TOPIC_PREFIX', 'smatrix')


def init_uhome() -> Uhome | None:
    """Establish connection to U@home module."""
    if not UHOME_ADDR:
        logger.error("UHOME_ADDR is not set.")
        return None
    try:
        uhome = Uhome(UHOME_ADDR)
        return uhome
    except Exception as e:  # Catching all exceptions
        logger.error(f"Error connecting to U@home: {e}")
        return None


def connect_mqtt() -> Optional[mqtt.Client]:
    """Establish connection to MQTT broker with authentication."""
    client = mqtt.Client()
 
    if len(MQTT_USERNAME) == 0:
        MQTT_USERNAME = None
    if len(MQTT_PASSWORD) == 0:
        MQTT_PASSWORD = None 
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    try:
        client.connect(MQTT_BROKER, MQTT_PORT)
        client.loop_start()  # Start the network loop
        return client
    except mqtt.MQTTException as e:
        logger.error(f"Error connecting to MQTT broker: {e}")
        return None



def publish_thermostat_data(uhome: Optional[Uhome], mqtt_client: Optional[mqtt.Client]) -> None:
    """Fetch and publish specific thermostat data with renamed keys and timestamp."""
    if not uhome or not mqtt_client:
        logger.warning("U@home or MQTT client not available.")
        return

    key_mapping = {
        'rh_value': 'humidity',
        'room_temperature': 'temperature',
        'room_setpoint': 'tempsetpoint'
    }

    for thermostat in uhome.thermostats:
        try:
            data = {}
            for old_key, new_key in key_mapping.items():
                if hasattr(thermostat, old_key):
                    value = getattr(thermostat, old_key)
                    if value is not None:
                        data[new_key] = value
            
            # Add timestamp in ISO 8601 format
            data['time'] = datetime.now(timezone.utc).isoformat()
            
            # Convert room_name to lower case and replace spaces with underscores
            room_name = getattr(thermostat, 'room_name', '').lower().replace(' ', '_')
            
            topic = f"{MQTT_TOPIC_PREFIX}/{room_name}"
            if len(MQTT_TOPIC_SUFFIX) > 0:
                topic += f"/{MQTT_TOPIC_SUFFIX}"
            mqtt_client.publish(topic, json.dumps(data))
            logger.info(f"Published data for thermostat {room_name}: {data}")
        except AttributeError as e:
            logger.error(f"Error accessing attribute for thermostat {room_name}: {e}")
        except mqtt.MQTTException as e:
            logger.error(f"Error publishing data for thermostat {room_name}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error for thermostat {room_name}: {e}")



def job(uhome: Uhome, mqtt_client: mqtt.Client) -> None:
    """Update U@home data and publish to MQTT."""
    try:
        uhome.update()
    except Exception as e:
        logger.error(f"Error reading thermostat data: {e}")
    try:
        publish_thermostat_data(uhome, mqtt_client)
    except Exception as e:
        logger.error(f"Error publishing thermostat data: {e}")


# Global flag to control the main loop
shutdown: bool = False

def signal_handler(signum, frame) -> None:
    """Signal handler to initiate graceful shutdown of the program."""
    global shutdown
    logger.info(f"Signal {signum} received, initiating graceful shutdown...")
    shutdown = True

# Register the signal handler
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


def main_loop() -> None:
    global shutdown
 
    uhome = init_uhome()
    if not uhome:
        logger.error("Failed to initialize U@home. Exiting.")
        sys.exit(0)
 
    mqtt_client = connect_mqtt()

    if not uhome or not mqtt_client:
        logger.error("Failed to initialize. Exiting.")
        return

    schedule.every(UPDATE_INTERVAL).seconds.do(job, uhome, mqtt_client)

    logger.info(f"Starting data collection. Publishing every {UPDATE_INTERVAL} minutes.")
    while not shutdown:
        schedule.run_pending()
        time.sleep(1)


def clean_up() -> None:
    if mqtt_client:
        mqtt_client.loop_stop()  # Stop the network loop
        mqtt_client.disconnect()


def main() -> None:
    try:
        setup()
    except Exception as e:
        logger.error(f"Error during setup: {e}")
        sys.exit(1)
    try:
        main_loop()
    finally:
        clean_up()
        logger.info("Exiting.")


if __name__ == "__main__":
    main()

"""
import os
import time
import schedule
import paho.mqtt.client as mqtt
from uhome import Uhome

# Define MQTT settings using environment variables
MQTT_BROKER = os.getenv('MQTT_BROKER', 'mqtt.example.com')  # Default to 'mqtt.example.com' if not set
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))               # Default to 1883 if not set
MQTT_TOPIC = os.getenv('MQTT_TOPIC', 'uhome/thermostat')    # Default to 'uhome/thermostat' if not set
MQTT_USERNAME = os.getenv('MQTT_USERNAME')                  # No default value
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')                  # No default value

# Initialize Uhome instance with the IP address of your U@home unit
UHOME_ADDR = os.getenv('UHOME_ADDR', '192.168.1.100')           # Default to '192.168.1.100' if not set
uhome = Uhome(UHOME_ADDR)

# Initialize MQTT client and connect to the broker
mqtt_client = mqtt.Client()
mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)

def read_and_publish():
#    Function to read thermostat values and publish them to the MQTT broker.
    # Update thermostat values
    uhome.update()
    
    # Iterate through each thermostat and send MQTT messages
    for thermostat in uhome.uhome_thermostats:
        # Create a payload dictionary with thermostat key values
        payload = {key: value['value'] for key, value in thermostat.uhome_thermostat_keys.items()}
        # Publish the payload as a JSON string to the MQTT topic
        mqtt_client.publish(MQTT_TOPIC, json.dumps(payload))

# Schedule the task to run every 10 minutes
schedule.every(10).minutes.do(read_and_publish)

# Keep the script running to execute scheduled tasks
while True:
    schedule.run_pending()
    time.sleep(1)

"""
