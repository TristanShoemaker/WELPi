from pymongo import MongoClient
import requests
import xmltodict
import time
from datetime import datetime as dt

WEL_ip = '192.168.68.137'
# mongo_ip = 'localhost'
mongo_ip = '192.168.68.114'

def getData(ip):
    url = "http://" + ip + ":5150/data.xml"
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
    post['dateandtime'] = dt.combine(date, time)
    del post['Date']; del post['Time']
    return post

def connect(ip):
    address = "mongodb://" + ip + ":27017"
    client = MongoClient(address)
    db = client.WEL.data
    return db

def run():
    db = connect(mongo_ip)
    while(True):
        post = getData(WEL_ip)
        post_id = db.insert_one(post).inserted_id
        print(F"post_id: {post_id}")
        time.sleep(60)

run()
