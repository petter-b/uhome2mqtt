from custom_components.uhomeuponor.uponor_api import UponorClient as BaseUponorClient, UponorThermostat, UponorAPIException
import json
import httpx
import logging
import asyncio
from requests import RequestException

class UponorClient(BaseUponorClient):
    """Wrapper for the UponorClient class to allow for direct calls without Home Assistant"""
    
    def __init__(self, server_address: str) -> None:
        super().__init__(None, server_address)  # Pass None to the parent class for hass
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info(f"UponorClient created with server_address: {server_address}")
        try:
            asyncio.create_task(self.rescan())
        except (ValueError, RequestException) as e:
            self._logger.error(f"Error from U@home at initial scan: {e}", exc_info=True)
            raise UponorAPIException("Error from U@home at initial scan", e)
        except asyncio.CancelledError:
            self._logger.info("Setup U@home was cancelled.")
            raise

    async def do_rest_call(self, requestObject):
        data = json.dumps(requestObject)
        self._logger.debug(f"Request payload: {json.dumps(requestObject, indent=2)}")

        response = None
        try:
            async with httpx.AsyncClient() as client:
                self._logger.debug(f"POST {self.server_uri}")
                response = await client.post(self.server_uri, data=data, timeout=10.0)
        except httpx.RequestError as ex:
            self._logger.error(f"API call error: {ex}", exc_info=True)
            raise UponorAPIException("API call error", ex)

        if response.status_code != 200:
            self._logger.warning(f"Unsuccessful API call to {self.server_uri}. Status code {response.status_code} received.")
            raise UponorAPIException("Unsuccessful API call")

        response_data = json.loads(response.text)
        self._logger.debug(f"Response payload: {json.dumps(response_data, indent=2)}")
        return response_data
