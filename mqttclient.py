import logging
import paho.mqtt.client as mqtt

class MqttPubClient:
    """MQTT publisher client."""
    def __init__(self, broker_address: str, broker_port: int = 1883, username: str | None = None, password: str | None = None) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._client = mqtt.Client()
        self._username: str | None = None
        if username is not None and len(username) > 0:
            self._username = username
        self._password: str | None = None  
        if self._username is not None and password is not None and len(password) > 0:
            self._password = password
        self._client.username_pw_set(self._username, self._password)

    
    
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
