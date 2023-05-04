import asyncio
import logging
import os
import time
from datetime import datetime, timedelta

import aioesphomeapi
import requests
from esphome.espota2 import run_ota

ACCESS_ID = os.getenv('CF_ACCESS_ID')
ACCESS_SECRET = os.getenv('CF_ACCESS_SECRET')
LOG_LEVEL = os.getenv('LOGLEVEL', 'INFO').upper()
HOST = "https://espcloud.ovh/api"
RATE_LIMIT_SECS = 10

logging.basicConfig(format='[%(asctime)s] %(levelname)s: %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("espcloud")
logger.setLevel(LOG_LEVEL)

if ACCESS_ID is None or ACCESS_SECRET is None:
    logger.error('CF Access ID or Secret not defined!')


def current_timestamp():
    return int(time.time())


class EspCloudAPI:
    last_upload_per_host = {}

    def list_devices(self):
        r = requests.get(HOST + "/devices", headers={
            "CF-Access-Client-Id": ACCESS_ID,
            "CF-Access-Client-Secret": ACCESS_SECRET,
        })
        return r.json()['result']

    def upload_states(self, device_id, entity_id, state):
        self.last_upload_per_host.setdefault(entity_id, None)
        if self.last_upload_per_host[entity_id] == None or \
                self.last_upload_per_host[entity_id] <= current_timestamp():
            logger.debug(f"Uploading state for {device_id}:{entity_id}:{state}")
            r = requests.post(HOST + "/devices/states", json={
                "entity_id": entity_id,
                "state": state
            }, headers={
                "CF-Access-Client-Id": ACCESS_ID,
                "CF-Access-Client-Secret": ACCESS_SECRET,
            })

            self.last_upload_per_host[entity_id] = current_timestamp() + RATE_LIMIT_SECS
            return r.json()

        return

    def update_devices_and_entities(self, device, entities):
        processed_entities = []

        for entity in entities:
            for thing in entity:
                processed_entities.append({
                    "entity_id": thing.name
                })

        logger.info(f"Uploading Entities of {device.name}")
        requests.post(HOST + "/entities/sync", json={
            "device_id": device.name,
            "entities": processed_entities
        }, headers={
            "CF-Access-Client-Id": ACCESS_ID,
            "CF-Access-Client-Secret": ACCESS_SECRET,
        })

    def get_build_file(self, build_id):
        r = requests.get(HOST + f"/builds/{build_id}", headers={
            "CF-Access-Client-Id": ACCESS_ID,
            "CF-Access-Client-Secret": ACCESS_SECRET,
        })

        # Just to make sure its not getting blocked in cf access
        assert len(r.content) > 40000

        path = f'/tmp/{build_id}.bin'

        with open(path, 'wb') as f:
            f.write(r.content)

        return path


class EspProxyManager():
    def __init__(self):
        self._espcloud_api = EspCloudAPI()
        self._registered_devices = {}
        self._entity_key_to_uuid = {}

    def subscribe_callback(self, device_id, state):
        entity_id = self._entity_key_to_uuid[state.key]

        self._espcloud_api.upload_states(device_id, entity_id, state.state)

    async def listen_to_device(self, device):
        device_id = device['device_id']
        device_host = device['hostname']

        logger.info(f"Connecting to {device_id}")
        api = aioesphomeapi.APIClient(device_host, device['port'], device['password'])

        await api.connect(login=True)

        device_info = await api.device_info()

        entities = await api.list_entities_services()

        self._espcloud_api.update_devices_and_entities(device_info, entities)

        self._registered_devices[device_id] = {
            "device_info": device_info,
            "entities": entities
        }
        compilation_time = datetime.strptime(device_info.compilation_time, "%b %d %Y, %H:%M:%S")
        last_build_time = (datetime.strptime(device['lastBuild']['created_at'], '%Y-%m-%dT%H:%M:%S.%fZ') - timedelta(
            minutes=2))

        if (last_build_time > compilation_time):
            self.update_firmware(device)
            return

        for entity in entities:
            for thing in entity:
                self._entity_key_to_uuid[thing.key] = thing.name

        logger.info(f"Connected to {device_id}")

        await api.subscribe_states(lambda state: self.subscribe_callback(device_id, state))

    async def run(self):
        logger.info("Retrieving devices...")
        devices = self._espcloud_api.list_devices()

        for device in devices:
            asyncio.create_task(self.listen_to_device(device))

    def update_firmware(self, device):
        logger.info('Starting OTA')
        file_path = self._espcloud_api.get_build_file(device['lastBuild']['build_id'])
        run_ota(device['hostname'], 8266, device['password'], file_path)
        logger.info('Finished OTA')


manager = EspProxyManager()

loop = asyncio.get_event_loop()
try:
    asyncio.ensure_future(manager.run())
    loop.run_forever()
except KeyboardInterrupt:
    pass
finally:
    loop.close()
