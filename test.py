from utils import is_valid_ip, is_valid_fqdn
from uhome_wrapper import UponorClient, UponorThermostat
from mqttclient import MqttConfig, MqttPubClient, get_mqtt_vars
import logging
import asyncio
import signal
import os
import sys
from typing import Tuple
from requests import RequestException

"""Constants."""
MIN_UPDATE_INTERVAL: int = 15  # seconds
DEFAULT_UPDATE_INTERVAL: int = 60  # seconds


def get_env_vars() -> Tuple[str, int]:
    """Get environment variables."""
    logger = logging.getLogger(__name__)

    #uhome_addr = os.getenv('UHOME_ADDR')
    uhome_addr  = '172.17.4.6'
    if not uhome_addr:
        logger.error("UHOME_ADDR is not set. Exiting.")
        sys.exit(1)

    if not (is_valid_ip(uhome_addr) or is_valid_fqdn(uhome_addr)):
        logger.error("UHOME_ADDR is not a valid IP address or FQDN. Exiting.")
        sys.exit(1)

    try:
        update_interval = int(os.getenv('UPDATE_INTERVAL', DEFAULT_UPDATE_INTERVAL))  # seconds
    except ValueError:
        logger.warning(f"UPDATE_INTERVAL is not a valid integer. Using default {DEFAULT_UPDATE_INTERVAL} [seconds].")
        update_interval = DEFAULT_UPDATE_INTERVAL
    if update_interval< MIN_UPDATE_INTERVAL:
        logger.warning(f"UPDATE_INTERVAL is less than the minimum allowed value of {MIN_UPDATE_INTERVAL} [seconds]. Using {MIN_UPDATE_INTERVAL} [seconds].")
        update_interval = MIN_UPDATE_INTERVAL

    return uhome_addr, update_interval


class ThermostatController():
    """
    Thermostat controller that utilizes Uponor U@Home API to interact with U@Home.
    """
    def __init__(self, thermostat: UponorThermostat) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._available = False
        self.uponor_client = thermostat.uponor_client
        self.thermostat = thermostat
        self.name = f"{thermostat.by_name('room_name').value}"
        self.identity = f"c{thermostat.controller_index}_t{thermostat.thermostat_index}"
        self._trigger = asyncio.Event()


    def trigger(self) -> None: 
        """Trigger the update and publish loop."""
        self._trigger.set()


    def check_completion(self) -> None:
        """Check if the update and publish loop has completed."""
        if self._trigger.is_set():
            self._logger.error(f"Thermostat {self.identity} in {self.name} did not complete the update and publish loop.")



    async def update_publish_loop(self) -> None:
        """Update thermostat data and publish to MQTT."""
        try:
            while True:
                await self._trigger.wait()
                # Update thermostat
                try:
                    await self.thermostat.async_update()
                    valid = self.thermostat.is_valid()
                    self._available = valid
                    if not valid:
                        self._logger.info(f"Invalid data for thermostat {self.identity} in {self.name}")
                except Exception as e:
                    self._available = False
                    self._logger.error(f"Thermostat {self.identity} in {self.name} was unable to update: {e}")
                
                # Publish to MQTT
                print(f"{self.thermostat.by_name('room_name').value} - temp: {self.thermostat.by_name('room_temperature').value}°C - humidity: {self.thermostat.by_name('rh_value').value}%")

                self._trigger.clear() # Reset the event for the next trigger     
        except asyncio.CancelledError:
            self._logger.debug(f"Control loop for thermostat {self.identity} in {self.name} was cancelled.")
            raise


async def main() -> None:
    """Main function."""
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

    # Signal handler and event to initiate graceful shutdown
    shutdown = asyncio.Event() 

    def signal_handler(signum) -> None:
        """Signal handler to initiate graceful shutdown of the program."""
        logger.info(f"Signal {signal.Signals(signum).name} received, initiating graceful shutdown...")
        shutdown.set()

    # Register the signal handler
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, lambda: signal_handler(signal.SIGTERM))
    loop.add_signal_handler(signal.SIGINT, lambda: signal_handler(signal.SIGINT))

    uhome_addr, update_interval = get_env_vars()
    mqtt_config = get_mqtt_vars()

    try: 
        uhome = UponorClient(uhome_addr)
        thermostats = [ThermostatController(thermostat) for thermostat in uhome.thermostats]
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(thermostat.update_publish_loop()) for thermostat in thermostats]

            logger.info(f"Starting data collection. Publishing every {update_interval} seconds.")
            while not shutdown.is_set():
                for thermostat in thermostats:
                    thermostat.trigger() 
                try: 
                    # Wait for either the sleep to complete or the event to be set
                    await asyncio.wait_for(asyncio.create_task(shutdown.wait()), timeout=update_interval)
                except asyncio.TimeoutError:
                    # Check if each thermostant has completed the update and publish loop
                    for thermostat in thermostats:
                        thermostat.check_completion()
                except asyncio.CancelledError:
                    pass
            for task in tasks:
                task.cancel()
    except asyncio.CancelledError:
        pass
    # Clean up    
    logger.info("Exiting.")


if __name__ == "__main__":
    asyncio.run(main())

