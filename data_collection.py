from pymongo import MongoClient, DESCENDING
from pymongo.errors import DuplicateKeyError
import requests
from requests.exceptions import NewConnectionError
import xmltodict
import time
from datetime import datetime as dt
from dateutil import tz

WEL_ip = '192.168.68.134'
mongo_ip = 'localhost'
# mongo_ip = '192.168.68.101'

def getData(ip):
    url = "http://" + ip + ":5150/data.xml"
    try:
        response = requests.get(url)
    except NewConnectionError:
        print("error in connecting to WEL, waiting 5 sec then trying again",
              flush=True)
        time.sleep(5)
        response = requests.get(url)
    # print(response.content)
    response_data = xmltodict.parse(response.content)['Devices']['Device']
    # print(response_data)
    post = {}
    for item in response_data:
        try:
            post[item['@Name']] = float(item['@Value'])
        except ValueError: post[item['@Name']] = item['@Value']
    date = dt.strptime(post['Date'], "%m/%d/%Y")
    time = dt.strptime(post['Time'], "%H:%M:%S").time()
    post['dateandtime'] = dt.combine(date, time).astimezone(tz.gettz('EST'))
    post['dateandtime'] = post['dateandtime'].astimezone(tz.gettz('UTC'))
    del post['Date']; del post['Time']
    return post

def connect(ip):
    address = "mongodb://" + ip + ":27017"
    client = MongoClient(address)
    db = client.WEL.data
    return db

def run():
    print(F"\n Restarted {datetime.datetime.now()} ...")
    db = connect(mongo_ip)
    if "dateandtime_-1" not in list(db.index_information()):
        result = db.create_index([('dateandtime', DESCENDING)], unique=True)
        print(F"Creating Unique Time Index: {result}", flush=True)
    while(True):
        post = getData(WEL_ip)
        try:
            post_id = db.insert_one(post).inserted_id
            print(F"time: {post['dateandtime']} - post_id: {post_id}",
                  flush=True)
        except DuplicateKeyError:
            print(F"time key {post['dateandtime']} already in database.",
                  flush=True)

        time.sleep(30)

run()
