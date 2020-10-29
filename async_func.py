import requests
import xmltodict
import time
import platform
from pymongo import DESCENDING
from pymongo.errors import DuplicateKeyError
from requests.exceptions import ConnectionError
from datetime import datetime as dt
from pytz import timezone
from astral import sun, LocationInfo
from libmc import Client
from streamlit_pi import streamPlot, message
from WELData import mongoConnect


WEL_ip = '192.168.68.107'
if platform.machine() == 'aarch64':
    mongo_ip = 'localhost'
elif platform.machine() == 'x86_64':
    mongo_ip = '98.118.28.23'
else:
    raise("Unknown platform, can't choose mongoDB ip")
loc = LocationInfo('Home', 'MA', 'America/New_York', 42.485557, -71.433445)
to_tzone = timezone('America/New_York')
db_tzone = timezone('UTC')


def getData(ip):
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
    date = dt.strptime(post['Date'], "%m/%d/%Y")
    timeStamp = dt.strptime(post['Time'], "%H:%M:%S").time()

    post['dateandtime'] = (dt.combine(date, timeStamp)
                           .replace(tzinfo=timezone('EST')))
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


def asyncPlot(mc, timeKey):
    stp = streamPlot()
    stp.makeWEL(['-t', '12'], force_refresh=True)
    plot_options = ['temp', 'pandw']
    for which in plot_options:
        message(F"Async plot {which}")
        plots = stp.plotAssembly(which=which)
        mc_result = mc.set(F"{which}PlotKey", {'plots': plots,
                                               'timeKey': timeKey})
        if not mc_result:
            message(F"❗{which} plot failed to cache❗")
            exit()


def connectMemCache():
    mc = Client(['localhost'])
    message("MemCache Connected")
    return mc


def main():
    message("\n Restarted ...")
    db = mongoConnect().data
    # mc = connectMemCache()
    if "dateandtime_-1" not in list(db.index_information()):
        result = db.create_index([('dateandtime', DESCENDING)], unique=True)
        message(F"Creating Unique Time Index: {result}")
    while True:
        post = getData(WEL_ip)
        post_success = False
        utc_time = post['dateandtime'].strftime('%Y-%m-%d %H:%M')
        try:
            post_id = db.insert_one(post).inserted_id
            message(F"UTC time: {utc_time} | "
                    F"post_id: {post_id}")
            post_success = True
        except DuplicateKeyError:
            message(F"UTC time: {utc_time} post already in database")

        # if post_success:
        #     asyncPlot(mc, post['dateandtime'].astimezone(to_tzone))

        time.sleep(30)


if __name__ == "__main__":
    main()
