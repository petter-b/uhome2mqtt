from requests import RequestException
from uhome_wrapper import UponorClient, UponorThermostat
import logging
import asyncio
import signal
import os
import sys


# Configuration from environment variables
#UHOME_ADDR: str = os.getenv('UHOME_ADDR')
UHOME_ADDR: str = '172.17.4.6'
UPDATE_INTERVAL: int = int(os.getenv('UPDATE_INTERVAL', '60'))  # seconds

# MQTT parameters
MQTT_BROKER: str = os.getenv('MQTT_BROKER', 'localhost')
MQTT_PORT: int = int(os.getenv('MQTT_PORT', '1883'))
MQTT_USERNAME: str = os.getenv('MQTT_USERNAME', '')
MQTT_PASSWORD: str = os.getenv('MQTT_PASSWORD', '')
MQTT_TOPIC_PREFIX: str = os.getenv('MQTT_TOPIC_PREFIX', 'smatrix')
MQTT_TOPIC_SUFFIX: str = os.getenv('MQTT_TOPIC_SUFFIX', 'climate')   


# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Signal handler and global event to initiate graceful shutdown
shutdown = asyncio.Event() 
def signal_handler(signum) -> None:
    """Signal handler to initiate graceful shutdown of the program."""
    logger.info(f"Signal {signal.Signals(signum).name} received, initiating graceful shutdown...")
    shutdown.set()


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
                print(f"{self.thermostat.by_name('room_name').value} - temp: {self.thermostat.by_name('room_temperature').value}°C - humidity: {self.thermostat.by_name('rh_value').value}%")

                self._trigger.clear() # Reset the event for the next trigger     
        except asyncio.CancelledError:
            self._logger.debug(f"Control loop for thermostat {self.identity} in {self.name} was cancelled.")
            raise

async def setup_uhome(uhome_addr: str) -> UponorClient | None:
    """Establish connection to U@home module, and scan for thermostats."""
    try:
        uhome = UponorClient(uhome_addr)
    except Exception as e:  # Catching all exceptions
        logger.error(f"Error connecting to U@home: {e}")
        return None
    try:
        await uhome.rescan()
    except (ValueError, RequestException) as e:
        logger.error(f"Error from U@home at intial scan: {e}")
        return None
    except asyncio.CancelledError:
        logger.info("Setup U@home was cancelled.")
        raise
    return uhome


async def main() -> None:
    """Main function."""
    global shutdown
    # Register the signal handler
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, lambda: signal_handler(signal.SIGTERM))
    loop.add_signal_handler(signal.SIGINT, lambda: signal_handler(signal.SIGINT))

    if not UHOME_ADDR:
        logger.error("UHOME_ADDR is not set. Exiting.")
        sys.exit(1)
    try: 
        uhome = await setup_uhome(UHOME_ADDR)
        if not uhome:
            logger.error("Failed to initialize U@home. Exiting.")   
            sys.exit(1)
        thermostats = [ThermostatController(thermostat) for thermostat in uhome.thermostats]
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(thermostat.update_publish_loop()) for thermostat in thermostats]

            logger.info(f"Starting data collection. Publishing every {UPDATE_INTERVAL} seconds.")
            while not shutdown.is_set():
                for thermostat in thermostats:
                    thermostat.trigger() 
                try: 
                    # Wait for either the sleep to complete or the event to be set
                    await asyncio.wait_for(asyncio.create_task(shutdown.wait()), timeout=UPDATE_INTERVAL)
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

