import requests
import xmltodict
import time
import platform
import asyncio
import datetime as dt
from pymongo.errors import DuplicateKeyError
from requests.exceptions import ConnectionError
from pytz import timezone
from astral import sun, LocationInfo
from libmc import Client
from sense_energy import Senseable
from log_message import message
from WELData import mongoConnect


WEL_IP = '192.168.68.107'

if platform.system() == 'Linux':
    if platform.machine() == 'aarch64':
        MONGO_IP = 'localhost'
    elif platform.machine() == 'x86_64':
        MONGO_IP = '98.118.28.23'
elif platform.system() == 'Darwin':
    MONGO_IP = '192.168.68.101'
else:
    raise("Unknown platform, can't choose mongoDB ip")

LOC = LocationInfo('Home', 'MA', 'America/New_York', 42.485557, -71.433445)
TO_TZONE = timezone('America/New_York')
DB_TZONE = timezone('UTC')
WEL_tzone = timezone('EST')


def connectMemCache():
    ip = MONGO_IP + ":11211"
    mc = Client([ip])
    message("MemCache Connected", mssgType='ADMIN')
    return mc


def connectSense():
    sn = Senseable()
    if platform.system() == 'Linux':
        path = "/home/ubuntu/WEL/WELPi/sense_info.txt"
    elif platform.system() == 'Darwin':
        path = "./sense_info.txt"

    sense_info = open(path).read().strip().split()
    sn.authenticate(*sense_info)
    sn.rate_limit = 10
    message("Sense Connected", mssgType='ADMIN')
    return sn


async def getWELData(ip):
    tic = time.time()
    url = "http://" + ip + ":5150/data.xml"
    try:
        response = requests.get(url)
    except ConnectionError:
        message("Error in connecting to WEL, waiting 10 sec then trying again",
                mssgType='WARNING')
        time.sleep(10)
        response = requests.get(url)

    response_data = xmltodict.parse(response.content)['Devices']['Device']

    post = {}
    for item in response_data:
        try:
            post[item['@Name']] = float(item['@Value'])
        except ValueError:
            post[item['@Name']] = item['@Value']

    post['dateandtime'] = (dt.datetime.now()
                           .replace(microsecond=0)
                           .replace(tzinfo=TO_TZONE))

    del post['Date']
    del post['Time']

    sunrise = sun.sunrise(LOC.observer, date=post['dateandtime'].date(),
                          tzinfo=TO_TZONE).astimezone(DB_TZONE)
    sunset = sun.sunset(LOC.observer, date=post['dateandtime'].date(),
                        tzinfo=TO_TZONE).astimezone(DB_TZONE)
    post['daylight'] = ((post['dateandtime'] > sunrise)
                        and (post['dateandtime'] < sunset)) * 1

    message([F"{'Getting WEL:': <20}", F"{time.time() - tic:.1f} s"],
            mssgType='TIMING')
    return post


async def getRtlData(mc):
    tic = time.time()
    post = mc.get('rtl')
    if post is None:
        message("RTL data not found in memCache", mssgType='WARNING')
        return {}
    else:
        message([F"{'Getting RTL:': <20}", F"{time.time() - tic:.3f} s"],
                mssgType='TIMING')
        return post


async def getSenseData(sn):
    tic = time.time()
    sn.update_realtime()
    sense_post = sn.get_realtime()
    post = {}
    post['solar_w'] = sense_post['solar_w']
    post['house_w'] = sense_post['w']
    post['dehumidifier_w'] = [device for device in sense_post['devices']
                              if device['name'] == 'Dehumidifier '][0]['w']
    post['furnace_w'] = [device for device in sense_post['devices']
                         if device['name'] == 'Furnace'][0]['w']
    post['barn_pump_w'] = [device for device in sense_post['devices']
                           if device['name'] == 'Barn pump'][0]['w']
    message([F"{'Getting Sense:': <20}", F"{time.time() - tic:.1f} s"],
            mssgType='TIMING')
    return post


async def send_post(db, post):
    utc_time = post['dateandtime'].strftime('%Y-%m-%d %H:%M:%S')
    try:
        post_id = db.insert_one(post).inserted_id
        message(F"Successful post @ UTC time: {utc_time}"
                F" | post_id: {post_id}", mssgType='SUCCESS')
    except DuplicateKeyError:
        message("Tried to insert duplicate key "
                F"{post['dateandtime'].strftime('%Y-%m-%d %H:%M:%S')}",
                mssgType='WARNING')


async def main(interval, db, mc, sn):
    while True:
        then = time.time()
        post = await getWELData(WEL_IP)
        post.update(await getRtlData(mc))
        post.update(await getSenseData(sn))
        elapsed = time.time() - then
        await asyncio.sleep(interval - elapsed)
        post['dateandtime'] = (dt.datetime.utcnow()
                               .replace(microsecond=0)
                               .replace(tzinfo=DB_TZONE))
        await send_post(db, post)


if __name__ == "__main__":
    message("\n    Restarted ...", mssgType='ADMIN')
    db = mongoConnect().data
    message("Mongo Connected", mssgType='ADMIN')
    mc = connectMemCache()
    sn = connectSense()

    asyncio.run(main(30, db, mc, sn))
