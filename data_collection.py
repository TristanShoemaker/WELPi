from pymongo import MongoClient, DESCENDING
from pymongo.errors import DuplicateKeyError
import requests
from requests.exceptions import ConnectionError
import xmltodict
import time
from datetime import datetime as dt
from dateutil import tz
from astral import sun, LocationInfo
from libmc import Client
from streamlit_pi import streamPlot, message


WEL_ip = '192.168.68.107'
mongo_ip = 'localhost'
# mongo_ip = '192.168.68.101'
loc = LocationInfo('Home', 'MA', 'America/New_York', 42.485557, -71.433445)
to_tzone = tz.gettz('America/New_York')
db_tzone = tz.gettz('UTC')


def getData(ip):
    url = "http://" + ip + ":5150/data.xml"
    try:
        response = requests.get(url)
    except ConnectionError:
        message("Error in connecting to WEL, waiting 10 sec then trying again")
        time.sleep(10)
        response = requests.get(url)
    # print(response.content)
    response_data = xmltodict.parse(response.content)['Devices']['Device']
    # print(response_data)
    post = {}
    for item in response_data:
        try:
            post[item['@Name']] = float(item['@Value'])
        except ValueError:
            post[item['@Name']] = item['@Value']
    date = dt.strptime(post['Date'], "%m/%d/%Y")
    timeStamp = dt.strptime(post['Time'], "%H:%M:%S").time()
    # print(time)
    post['dateandtime'] = (dt.combine(date, timeStamp)
                           .replace(tzinfo=tz.gettz('EST')))
    # print(post['dateandtime'])
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


def asyncPlot(mc):
    stp = streamPlot()
    stp.makeWEL(['-t', '12'])
    plots = stp.plotAssembly()
    mc_result = mc.set('plotKey', plots)
    if not mc_result:
        message("Plot failed to cache")
        quit()


def connectMongo(ip):
    address = "mongodb://" + ip + ":27017"
    client = MongoClient(address)
    db = client.WEL.data
    message("Mongo Connected")
    return db


def connectMemCache():
    mc = Client(['localhost'])
    message("MemCache Connected")
    return mc


def main():
    print(F"\n Restarted {dt.now()} ...", flush=True)
    db = connectMongo(mongo_ip)
    mc = connectMemCache()
    if "dateandtime_-1" not in list(db.index_information()):
        result = db.create_index([('dateandtime', DESCENDING)], unique=True)
        print(F"Creating Unique Time Index: {result}", flush=True)
    while True:
        post = getData(WEL_ip)
        post_success = False
        try:
            post_id = db.insert_one(post).inserted_id
            message((F"UTC time: {post['dateandtime']} | "
                     F"post_id: {post_id}"))
            post_success = True
        except DuplicateKeyError:
            print(F"time key {post['dateandtime']} already in database",
                  flush=True)

        if post_success:
            asyncPlot(mc)

        time.sleep(30)


if __name__ == "__main__":
    main()
