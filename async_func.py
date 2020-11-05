import requests
import xmltodict
import time
import platform
import datetime as dt
from pymongo import DESCENDING
from pymongo.errors import DuplicateKeyError
from requests.exceptions import ConnectionError
from pytz import timezone
from astral import sun, LocationInfo
from libmc import Client
from sense_energy import Senseable
from StreamPlot import message
from WELData import mongoConnect


WEL_ip = '192.168.68.107'
if platform.machine() == 'aarch64':
    mongo_ip = 'localhost'
elif platform.machine() == 'x86_64':
    mongo_ip = '98.118.28.23'
elif platform.system() == 'Darwin':
    mongo_ip = '192.168.68.101'
else:
    raise("Unknown platform, can't choose mongoDB ip")
loc = LocationInfo('Home', 'MA', 'America/New_York', 42.485557, -71.433445)
to_tzone = timezone('America/New_York')
db_tzone = timezone('UTC')
WEL_tzone = timezone('EST')


def getWELData(ip):
    url = "http://" + ip + ":5150/data.xml"
    try:
        response = requests.get(url)
    except ConnectionError:
        message("Error in connecting to WEL, waiting 10 sec then trying again")
        time.sleep(10)
        response = requests.get(url)

    response_data = xmltodict.parse(response.content)['Devices']['Device']

    post = {}
    for item in response_data:
        try:
            post[item['@Name']] = float(item['@Value'])
        except ValueError:
            post[item['@Name']] = item['@Value']
    date = dt.datetime.strptime(post['Date'], "%m/%d/%Y")
    timeStamp = dt.datetime.strptime(post['Time'], "%H:%M:%S").time()

    post['WELdateandtime'] = (dt.datetime.combine(date, timeStamp)
                              .replace(tzinfo=WEL_tzone)
                              .astimezone(db_tzone))
    post['dateandtime'] = (dt.datetime.now()
                           .replace(microsecond=0)
                           .replace(tzinfo=to_tzone))
    post['dateandtime'] = post['dateandtime'].astimezone(db_tzone)
    del post['Date']
    del post['Time']

    sunrise = sun.sunrise(loc.observer, date=post['dateandtime'].date(),
                          tzinfo=to_tzone).astimezone(db_tzone)
    sunset = sun.sunset(loc.observer, date=post['dateandtime'].date(),
                        tzinfo=to_tzone).astimezone(db_tzone)
    post['daylight'] = ((post['dateandtime'] > sunrise)
                        and (post['dateandtime'] < sunset)) * 1

    return post


def getRtlData(mc):
    post = mc.get('rtl')
    if post is None:
        message("rtl data not found in memCache")
    else:
        return post


def getSenseData(sn):
    sn.update_realtime()
    sense_post = sn.get_realtime()
    post = {}
    post['solar_w'] = sense_post['solar_w']
    post['house_w'] = sense_post['w']
    post['dehumidifier_w'] = [device for device in sense_post['devices']
                              if device['name'] == 'Dehumidifier '][0]['w']
    return post


# def asyncPlot(mc, timeKey):
#     stp = StreamPlot()
#     stp.makeWEL(['-t', '12'], force_refresh=True)
#     plot_options = ['temp', 'pandw']
#     for which in plot_options:
#         message(F"Async plot {which}")
#         plots = stp.plotAssembly(which=which)
#         mc_result = mc.set(F"{which}PlotKey", {'plots': plots,
#                                                'timeKey': timeKey})
#         if not mc_result:
#             message(F"❗{which} plot failed to cache❗")
#             exit()


def connectMemCache():
    mc = Client(['localhost'])
    message("MemCache Connected")
    return mc


def connectSense():
    sn = Senseable()
    if platform.system() == 'Linux':
        path = "/home/ubuntu/WEL/WELPi/sense_info.txt"
    elif platform.system() == 'Darwin':
        path = "./sense_info.txt"

    sense_info = open(path).read().strip().split()
    sn.authenticate(*sense_info)
    sn.rate_limit = 20
    message("Sense Connected")
    return sn


def main():
    message("\n    Restarted ...")
    db = mongoConnect().data
    message("Mongo Connected")
    mc = connectMemCache()
    sn = connectSense()
    if "dateandtime_-1" not in list(db.index_information()):
        result = db.create_index([('dateandtime', DESCENDING)], unique=True)
        message(F"Creating Unique Time Index: {result}")
    while True:
        post = getWELData(WEL_ip)
        last_post = db.find_one(sort=[('_id', DESCENDING)])
        last_post = last_post['WELdateandtime'].replace(tzinfo=db_tzone)
        if post['WELdateandtime'] != last_post:
            try:
                rtl_post = getRtlData(mc)
                post.update(rtl_post)
            except TypeError:
                message("Empty rtl memCache.")
            try:
                sense_post = getSenseData(sn)
                post.update(sense_post)
            except TypeError:
                message("Empty sense data.")

            utc_time = post['dateandtime'].strftime('%Y-%m-%d %H:%M')
            try:
                post_id = db.insert_one(post).inserted_id
                message(F"UTC time: {utc_time} | post_id: {post_id}")
            except DuplicateKeyError:
                message(F"UTC time: {utc_time} post already in database")

        time.sleep(30)


if __name__ == "__main__":
    main()
