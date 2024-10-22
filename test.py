from custom_components.uhomeuponor.uponor_api import UponorClient, UponorAPIException
import json
import requests
import asyncio

smatrix_ip: str = '172.17.4.6'

class UponorClient(UponorClient):
    """Wrapper for the UponorClient class to allow for direct calls without 'hass' / Home Assistant"""
    def __init__(self, server):
        super().__init__(None, server)  # Pass None to the parent class for hass
        self.server = server

    async def do_rest_call(self, requestObject):
        data = json.dumps(requestObject)

        response = None
        try:
            response = requests.post(self.server_uri, data=data)  # Direct call without hass
        except requests.exceptions.RequestException as ex:
            raise UponorAPIException("API call error", ex)

        if response.status_code != 200:
            raise UponorAPIException("Unsuccessful API call")

        response_data = json.loads(response.text)
        return response_data

uhome = UponorClient(smatrix_ip)

async def test():
#    await uhome.init_controllers()
#    await uhome.init_thermostats()
    await uhome.rescan()

#    print(json.dumps(uhome, indent=2))

    for t in uhome.thermostats:
       print(f"{t.by_name('room_name').value} - temp: {t.by_name('room_temperature').value}°C - humidity: {t.by_name('rh_value').value}%")
       print(t.attributes().replace('#', '\n'))

asyncio.run(test())
