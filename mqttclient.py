from utils import is_valid_ip, is_valid_fqdn, is_valid_mqtt_topic
import logging
import os
import paho.mqtt.client as mqtt


"""Constants."""
DEFAULT_MQTT_BROKER: str = 'localhost'
DEFAULT_MQTT_PORT: int = 1883
DEFAULT_TOPIC_PREFIX: str = 'smatrix'
DEFAULT_TOPIC_SUFFIX: str = 'climate'


class MqttConfig:
    """MQTT configuration."""
    def __init__(self, broker: str, port: int, username: str | None, password: str | None, topic_prefix: str, topic_suffix: str) -> None:
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.topic_prefix = topic_prefix
        self.topic_suffix = topic_suffix

    def __str__(self) -> str:
        return f"MQTT broker: {self.broker}, port: {self.port}, username: {self.username}, password: {self.password}, topic prefix: {self.topic_prefix}, topic suffix: {self.topic_suffix}"


class MqttPubClient:
    """MQTT publisher client."""
    def __init__(self, broker_address: str, broker_port: int = 1883, username: str | None = None, password: str | None = None) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._client = mqtt.Client()
        if username is not None:
            self._client.username_pw_set(username, password)

    
    def on_connect(self, client, userdata, flags, rc) -> None:
        if rc == 0:
            self._logger.info("Connected to MQTT broker")
        else:
            self._logger.error(f"Failed to connect, return code: {rc}")


    def on_disconnect(self, client, userdata, rc):
        self.connected = False
        if rc != 0:
            logging.warning("Unexpected disconnection. Attempting to reconnect...")
        else:
            logging.info("Disconnected from MQTT broker")


    def connect_with_retry(self):
        retry_delay = RECONNECT_DELAY_MIN
        while not self.connected:
            try:
                self.client.connect(BROKER_ADDRESS, PORT)
                self.client.loop_start()
                return
            except Exception as e:
                logging.error(f"Connection failed: {e}")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, RECONNECT_DELAY_MAX)
                retry_delay += uniform(0, 1)  # Add jitter


    def publish_message(self, message):
        try:
            if not self.connected:
                self._logger.warning("Not connected. Attempting to reconnect...")
                self.connect_with_retry()

            result = self.client.publish(TOPIC, message, qos=1)  # Set QoS level
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                self._logger.error(f"Failed to publish message: {mqtt.error_string(result.rc)}")
            else:
                self._logger.info(f"Message published: {message}")
        except Exception as e:
            self._logger.error(f"Error publishing message: {e}")

    def disconnect(self):
        self.client.disconnect()
        self.client.loop_stop()
        self._logger.info("MQTT client disconnected")


def get_mqtt_vars() -> MqttConfig | None:
    """Get environment variables for MQTT client."""
    logger = logging.getLogger(__name__)

    mqtt_broker = os.getenv('MQTT_BROKER', DEFAULT_MQTT_BROKER)
    if not (is_valid_ip(mqtt_broker) or is_valid_fqdn(mqtt_broker)):
        logger.error("MQTT_BROKER is not a valid IP address or FQDN. Exiting.")
        return None

    try:
        mqtt_port = int(os.getenv('MQTT_PORT', DEFAULT_MQTT_PORT))
    except ValueError:
        logger.warning(f"MQTT_PORT is not a valid integer. Using default ({DEFAULT_MQTT_PORT}).")
        mqtt_port = DEFAULT_MQTT_PORT

    mqtt_username = os.getenv('MQTT_USERNAME', '')  
    mqtt_password = os.getenv('MQTT_PASSWORD', '')
    if len(mqtt_username) == 0:
        mqtt_username = None
    if mqtt_password is None or len(mqtt_password) == 0:
        mqtt_password = None

    mqtt_topic_prefix = os.getenv('MQTT_TOPIC_PREFIX', DEFAULT_TOPIC_PREFIX)    
    if not is_valid_mqtt_topic(mqtt_topic_prefix):
        logger.warning(f"Invalid MQTT topic prefix. Using default ({DEFAULT_TOPIC_PREFIX}).")
        mqtt_topic_prefix = DEFAULT_TOPIC_PREFIX
    
    mqtt_topic_suffix = os.getenv('MQTT_TOPIC_SUFFIX', DEFAULT_TOPIC_SUFFIX)
    if not is_valid_mqtt_topic(mqtt_topic_suffix):
        logger.warning(f"Invalid MQTT topic prefix or suffix. Using default ({DEFAULT_TOPIC_SUFFIX}).")
        mqtt_topic_suffix = DEFAULT_TOPIC_SUFFIX

    return MqttConfig(mqtt_broker, mqtt_port, mqtt_username, mqtt_password, mqtt_topic_prefix, mqtt_topic_suffix)

