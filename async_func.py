import requests
import xmltodict
import time
import platform
import asyncio
import datetime as dt
import socket
import json
from pyemvue import PyEmVue
from pyemvue.enums import Scale, Unit
from pymongo.errors import DuplicateKeyError
from requests.exceptions import ConnectionError
from pytz import timezone
from astral import sun, LocationInfo
from libmc import Client
from sense_energy import Senseable
from sense_energy.sense_exceptions import SenseAPITimeoutException
from log_message import message
from WELData import mongoConnect


WEL_IP = '192.168.68.107'

LOC = LocationInfo('Home', 'MA', 'America/New_York', 42.485557, -71.433445)
TO_TZONE = timezone('America/New_York')
DB_TZONE = timezone('UTC')
WEL_tzone = timezone('EST')


class SourceConnects():
    db = None
    mc = None
    sn = None
    em = None

    def __init__(self):
        self.db = mongoConnect().data
        self.connectMemCache()
        self.connectSense()
        self.connectEmporia()

    def connectMemCache(self):
        if platform.system() == 'Linux':
            if platform.machine() == 'aarch64':
                MONGO_IP = 'localhost'
            elif platform.machine() == 'x86_64':
                MONGO_IP = '173.76.156.115'
        elif platform.system() == 'Darwin':
            MONGO_IP = '192.168.68.101'
        else:
            raise("Unknown platform, can't choose mongoDB ip.")

        ip = MONGO_IP + ":11211"
        self.mc = Client([ip])
        message("MemCache Connected", mssgType='ADMIN')

    def connectEmporia(self):
        em = PyEmVue()
        if platform.system() == 'Linux':
            path = "/home/ubuntu/WEL/WELPi/emp_keys.json"
        elif platform.system() == 'Darwin':
            path = "./emp_keys.json"
        with open(path) as f:
            data = json.load(f)
        try:
            em.login(id_token=data['id_token'],
                     access_token=data['access_token'],
                     refresh_token=data['refresh_token'],
                     token_storage_file='keys.json')
        except Exception as e:
            message("Error logging into Emporia, "
                    F"excluding Emporia data from post. \n Error: {e}",
                    mssgType='ERROR')
        devices = em.get_devices()
        device_gids = []
        device_info = {}
        for device in devices:
            if device.device_gid not in device_gids:
                device_gids.append(device.device_gid)
                device_info[device.device_gid] = device
            else:
                device_info[device.device_gid].channels += device.channels
        message("Emporia Connected", mssgType='ADMIN')
        self.em = [em, device_info]

    def connectSense(self):
        sn = Senseable()
        if platform.system() == 'Linux':
            path = "/home/ubuntu/WEL/WELPi/sense_info.txt"
        elif platform.system() == 'Darwin':
            path = "./sense_info.txt"

        sense_info = open(path).read().strip().split()
        try:
            sn.authenticate(*sense_info)
        except Exception as e:
            message("Error in authenticating with Sense, "
                    F"excluding Sense from post. \n Error: {e}",
                    mssgType='ERROR')
        sn.rate_limit = 10
        message("Sense Connected", mssgType='ADMIN')
        self.sn = sn


async def getEmporiaData():
    tic = time.time()
    device_gids = list(connects.em[1].keys())
    device_usage = connects.em[0].get_device_list_usage(deviceGids=device_gids,
                                                        instant=None,
                                                        scale=Scale.MINUTE.value,
                                                        unit=Unit.KWH.value)
    kwh2kw = 60  # over one minute
    kw2w = 1000  # convert from w to kw for consistency with other data sources
    post = {}
    for gid, device in device_usage.items():
        for channelnum, channel in device.channels.items():
            name = channel.name
            if name == 'Main':
                name = connects.em[1][gid].device_name
            elif name == 'TotalUsage':
                post['Emp_Total_w'] = channel.usage * kwh2kw * kw2w
            elif name == 'Balance':
                post['Emp_balance_w'] = channel.usage * kwh2kw * kw2w
            elif name == 'Emporia':
                pass
            else:
                post[channel.name[:-2] + "w"] = channel.usage * kwh2kw * kw2w
    message([F"{'Getting Emporia:': <20}", F"{time.time() - tic:.1f} s"],
            mssgType='TIMING')
    message(post, mssgType='WARNING')
    return post


async def getWELData():
    tic = time.time()
    url = "http://" + WEL_IP + ":5150/data.xml"

    post = {}
    local_now = (dt.datetime.now()
                 .replace(microsecond=0)
                 .replace(tzinfo=TO_TZONE))
    sunrise = sun.sunrise(LOC.observer, date=local_now.date(),
                          tzinfo=TO_TZONE).astimezone(DB_TZONE)
    sunset = sun.sunset(LOC.observer, date=local_now.date(),
                        tzinfo=TO_TZONE).astimezone(DB_TZONE)
    post['daylight'] = ((local_now > sunrise)
                        and (local_now < sunset)) * 1

    try:
        response = requests.get(url)
    except ConnectionError:
        message("Error in connecting to WEL, waiting 10 sec then trying again",
                mssgType='WARNING')
        time.sleep(10)
        try:
            response = requests.get(url)
        except ConnectionError:
            message("Second error in connecting to WEL, "
                    "excluding WEL from post.",
                    mssgType='ERROR')
            return post

    response_data = xmltodict.parse(response.content)['Devices']['Device']

    for item in response_data:
        try:
            post[item['@Name']] = float(item['@Value'])
        except ValueError:
            post[item['@Name']] = item['@Value']

    del post['Date']
    del post['Time']

    message([F"{'Getting WEL:': <20}", F"{time.time() - tic:.1f} s"],
            mssgType='TIMING')
    return post


async def getRtlData():
    tic = time.time()
    post = connects.mc.get('rtl')
    if post is None:
        message("RTL data not found in memCache, "
                "excluding RTL from post.",
                mssgType='WARNING')
        return {}
    else:
        message([F"{'Getting RTL:': <20}", F"{time.time() - tic:.3f} s"],
                mssgType='TIMING')
        return post


async def getSenseData():
    tic = time.time()
    try:
        connects.sn.update_realtime()
    except SenseAPITimeoutException:
        message("Sense API timeout, trying reconnect...", mssgType='WARNING')
        connects.sn = connectSense()
        try:
            connects.sn.update_realtime()
        except SenseAPITimeoutException:
            message("Second Sense API timeout, "
                    "excluding Sense from post.", mssgType='ERROR')
            return {}
        except socket.timeout as e:
            message("Sense offline, excluding Sense from post."
                    F"\n Error: {e}", mssgType='ERROR')
            return {}
    except socket.timeout as e:
        message("Sense offline, excluding Sense from post."
                F"\n Error: {e}", mssgType='ERROR')
        return {}

    sense_post = connects.sn.get_realtime()
    post = {}
    post['solar_w'] = sense_post['solar_w']
    post['house_w'] = sense_post['w']

    try:
        post['dehumidifier_w'] = [device for device in sense_post['devices']
                                  if device['name'] ==
                                  'Dehumidifucker'][0]['w']
    except IndexError:
        post['dehumidifier_w'] = 0
        message("Dehumidifier not found in sense.", mssgType='WARNING')

    try:
        post['furnace_w'] = [device for device in sense_post['devices']
                             if device['name'] == 'Furnace'][0]['w']
    except IndexError:
        post['furnace_w'] = 0
        message("Furnace not found in sense.", mssgType='WARNING')

    try:
        post['barn_pump_w'] = [device for device in sense_post['devices']
                               if device['name'] == 'Barn pump'][0]['w']
    except IndexError:
        post['barn_pump_w'] = 0
        message("Barn pump not found in sense.", mssgType='WARNING')

    try:
        post['TES_sense_w'] = [device for device in sense_post['devices']
                               if device['name'] == 'Geo'][0]['w']
    except IndexError:
        post['TES_sense_w'] = 0
        message("Geo not found in sense.", mssgType='WARNING')

    try:
        post['TAH_sense_w'] = [device for device in sense_post['devices']
                               if device['name'] == 'Geo 1.4kW'][0]['w']
    except IndexError:
        post['TAH_sense_w'] = 0
        message("Geo 1.4kW not found in sense.", mssgType='WARNING')

    message([F"{'Getting Sense:': <20}", F"{time.time() - tic:.1f} s"],
            mssgType='TIMING')
    return post


async def send_post(post):
    utc_time = post['dateandtime'].strftime('%Y-%m-%d %H:%M:%S')
    try:
        post_id = connects.db.insert_one(post).inserted_id
        message(F"Successful post @ UTC time: {utc_time}"
                F" | post_id: {post_id}", mssgType='SUCCESS')
    except DuplicateKeyError:
        message("Tried to insert duplicate key "
                F"{post['dateandtime'].strftime('%Y-%m-%d %H:%M:%S')}",
                mssgType='WARNING')


async def main(interval):
    while True:
        then = time.time()
        post = await getWELData()
        post.update(await getRtlData())
        post.update(await getSenseData())
        post.update(await getEmporiaData())
        elapsed = time.time() - then
        await asyncio.sleep(interval - elapsed)
        post['dateandtime'] = (dt.datetime.utcnow()
                               .replace(microsecond=0)
                               .replace(tzinfo=DB_TZONE))

        await send_post(post)


if __name__ == "__main__":
    message("\n    Restarted ...", mssgType='ADMIN')
    message("Mongo Connected", mssgType='ADMIN')
    connects = SourceConnects()

    asyncio.run(main(30))
