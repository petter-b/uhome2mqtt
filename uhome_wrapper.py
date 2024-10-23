from custom_components.uhomeuponor.uponor_api import UponorClient, UponorThermostat, UponorAPIException
import json
import httpx
import logging

class UponorClient(UponorClient):
    """Wrapper for the UponorClient class to allow for direct calls without Home Assistant"""
    def __init__(self, server):
        super().__init__(None, server)  # Pass None to the parent class for hass
        self.server = server
        self._logger = logging.getLogger(self.__class__.__name__)

    async def do_rest_call(self, requestObject):
        data = json.dumps(requestObject)

        response = None
        try:
            async with httpx.AsyncClient() as client:
                self._logger.debug(f"POST {self.server_uri} with data: {data}")
                response = await client.post(self.server_uri, data=data)
        except httpx.RequestError as ex:
            raise UponorAPIException("API call error", ex)

        if response.status_code != 200:
            raise UponorAPIException("Unsuccessful API call")

        response_data = json.loads(response.text)
        return response_data
