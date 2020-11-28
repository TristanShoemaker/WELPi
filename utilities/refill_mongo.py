import datetime as dt
import WELData
from pprint import pprint
from dateutil.relativedelta import relativedelta
from pymongo.errors import DuplicateKeyError
from pytz import timezone
from astral import sun, LocationInfo


loc = LocationInfo('Home', 'MA', 'America/New_York', 42.485557, -71.433445)
to_tzone = timezone('America/New_York')
db_tzone = timezone('UTC')
db = WELData.mongoConnect().data


def clean_post(frame):
    frame = frame.dropna()
    post = frame.to_dict()
    post['dateandtime'] = (post['dateandtime'].replace(tzinfo=to_tzone)
                                              .astimezone(db_tzone)
                                              .to_pydatetime())

    del post['Date']
    del post['Time']

    sunrise = sun.sunrise(loc.observer, date=post['dateandtime'].date(),
                          tzinfo=to_tzone).astimezone(db_tzone)
    sunset = sun.sunset(loc.observer, date=post['dateandtime'].date(),
                        tzinfo=to_tzone).astimezone(db_tzone)
    post['daylight'] = ((post['dateandtime'] > sunrise)
                        and (post['dateandtime'] < sunset)) * 1

    return post


_now = dt.datetime.now().astimezone(timezone('America/New_York'))
init_date = dt.datetime(2020, 3, 1)
num_months = ((_now.year - init_date.year) * 12
              + _now.month - init_date.month)
timerange_list = [[init_date + relativedelta(months=x),
                   init_date + relativedelta(months=x + 1, days=-1)]
                  for x in range(num_months + 1)]

for timerange in timerange_list:
    dat = WELData.WELData(data_source='WEL',
                          timerange=timerange,
                          calc_cols=False)
    for i in range(len(dat.data)):
        row = dat.data.iloc[i]
        post = clean_post(row)
        utc_time = post['dateandtime'].strftime('%Y-%m-%d %H:%M')
        try:
            post_id = db.insert_one(post).inserted_id
            if i % (60*24) == 0:
                print(F"UTC time: {utc_time} | post_id: {post_id}")
        except DuplicateKeyError:
            print(F"UTC time: {utc_time} already in database")
