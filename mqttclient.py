from .utils import is_valid_ip, is_valid_hostname, is_valid_mqtt_topic
from typing import Final
import logging
import os
import asyncio
import paho.mqtt.client as mqtt


"""Constants."""
DEFAULT_MQTT_BROKER: Final[str] = 'localhost'
DEFAULT_MQTT_PORT: Final[int] = 1883
DEFAULT_TOPIC_PREFIX: Final[str] = 'smatrix'
DEFAULT_TOPIC_SUFFIX: Final[str] = 'climate'


class MqttConfig:
    """MQTT configuration."""
    def __init__(self, broker: str, port: int, username: str | None, password: str | None, keep_alive: int | None = None) -> None:
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.keep_alive = keep_alive

    def __str__(self) -> str:
        return f"MQTT broker: {self.broker}, port: {self.port}, username: {self.username}, password: {self.password}, keep alive: {self.keep_alive}"


class MqttPubClient():
    """MQTT publisher client."""
    def __init__(self, config: MqttConfig) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION_2)
        if config.username is not None:
            self._mqttc.username_pw_set(config.username, config.password)
        self.connected = asyncio.Event()
        try: 
            self._mqttc.connect_async(config.broker, config.port, keepalive=config.keep_alive)
            self._mqttc.loop_start()
        except mqtt.MQTTException as e:
            self._logger.error(f"Error connecting to MQTT broker: {str(e)}")
            self._logger.debug(f"Error details: {repr(e)}")
            raise
        except Exception as e:
            self._logger.error(f"Unexpected exception occurred: {str(e)}")
            self._logger.debug(f"Error details: {repr(e)}")
            raise

    @self._mqttc.connect_callback()
    def on_connect(self, client, userdata, flags, rc) -> None:
        try:
            if rc == 0:
                self.connected.set()
                self._logger.info("Connected to MQTT broker")
            elif rc == 3: # Server unavailable.
                self._logger.error(f"Connection refused - server unavailable")
                self._logger.debug(f"Return code details: {repr(rc)}")
            else: # Unrecoverable error
                self._logger.error(f"Connection refused - return code: {str(rc)}")
                self._logger.debug(f"Return code details: {repr(rc)}")
                raise mqtt.MQTTException(f"Connection refused - return code: {str(rc)}")
        except Exception as e:
            self._logger.error(f"Error in on_connect callback: {str(e)}")


    @self._mqttc.disconnect_callback()
    def on_disconnect(self, client, userdata, rc) -> None:
        self.connected.clear()
        if rc != 0:
            self._logger.warning("Unexpected disconnection from MQTT broker. Attempting to reconnect...")
            self._logger.debug(f"Return code details: {repr(rc)}")
        else:
            self._logger.info("Disconnected from MQTT broker")


    def publish(self, topic: str, message: str) -> None:
        if self.connected.is_set():
            try:
                self._mqttc.publish(topic, message)
            except Exception as e:
                self._logger.error(f"Unexpected exception occurred: {str(e)}")
                self._logger.debug(f"Error details: {repr(e)}")


    def disconnect(self):
        self._mqttc.disconnect()
        self._mqttc.loop_stop()
        self._logger.info("MQTT client disconnected")


def get_mqtt_vars() -> MqttConfig | None:
    """Get environment variables for MQTT client."""
    logger = logging.getLogger(__name__)

    mqtt_broker = os.getenv('MQTT_BROKER', DEFAULT_MQTT_BROKER)
    if not (is_valid_ip(mqtt_broker) or is_valid_hostname(mqtt_broker)):
        logger.error("MQTT_BROKER is not a valid IP address or hostname/FQDN.")
        return None

    try:
        mqtt_port = int(os.getenv('MQTT_PORT', DEFAULT_MQTT_PORT))
    except (ValueError, TypeError) as e:
        logger.warning(f"MQTT_PORT error: {e}. Using default ({DEFAULT_MQTT_PORT}).")
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
    if len(mqtt_topic_suffix) == 0:
        mqtt_topic_suffix = None
    elif not is_valid_mqtt_topic(mqtt_topic_suffix):
        logger.warning(f"Invalid MQTT topic prefix or suffix. Using default ({DEFAULT_TOPIC_SUFFIX}).")
        mqtt_topic_suffix = DEFAULT_TOPIC_SUFFIX

    return MqttConfig(mqtt_broker, mqtt_port, mqtt_username, mqtt_password), mqtt_topic_prefix, mqtt_topic_suffix

