import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import datetime as dt
import os
import platform
import re
import argparse
from dateutil.relativedelta import relativedelta
from wget import download
from urllib.error import HTTPError
from shutil import move
from astral import sun, LocationInfo
from pymongo import MongoClient
from pytz import timezone
from log_message import message


def mongoConnect():
    if platform.system() == 'Linux':
        admin = open("/home/ubuntu/WEL/WELPi/"
                     "mongo_admin_info.txt").read().strip()
        if platform.machine() == 'x86_64':
            ip = "98.118.28.23"
        else:
            ip = "localhost"
    elif platform.system() == 'Darwin':
        admin = open("./mongo_admin_info.txt").read().strip()
        ip = "192.168.68.101"
    else:
        raise("Unrecognized platform")

    uri = F"mongodb://{admin}@{ip}:27017/admin"
    client = MongoClient(uri)
    return client.WEL


class WELData:
    _figsize = (11, 5)        # default matplotlib figure size
    _loc = LocationInfo('Home', 'MA', 'America/New_York',
                        42.485557, -71.433445)
    _dl_db_path = None
    _db_tzone = timezone('UTC')
    _to_tzone = timezone('America/New_York')
    _mongo_db = None
    _data_source = None
    _now = None
    _calc_cols = None
    data = None
    timerange = None

    """
    Initialize the Weldata Object.
    If filepath is given, data will be read from the file, otherwise this
    month's log is downloaded and read.
    """
    def __init__(self,
                 data_source='Pi',
                 timerange=None,
                 WEL_download=False,
                 dl_db_path='../log_db/',
                 mongo_connection=None,
                 calc_cols=True):
        self._calc_cols = calc_cols
        self._data_source = data_source
        self._dl_db_path = dl_db_path
        self._now = dt.datetime.now().astimezone(self._to_tzone)
        if timerange is None:
            self.timerange = self.time_from_args()
        elif type(timerange[0]) is str:
            self.timerange = self.time_from_args(timerange)
        else:
            self.timerange = self.timeCondition(timerange)
        self.timerange = [time.replace(tzinfo=self._to_tzone)
                          if time.tzinfo is None else time
                          for time in self.timerange]

        if self._data_source == 'WEL':
            self.refresh_db()
            if WEL_download:
                dat_url = ("http://www.welserver.com/WEL1060/"
                           + F"WEL_log_{self._now.year}"
                           + F"_{self._now.month:02d}.xls")
                downfilepath = (self._dl_db_path
                                + F"WEL_log_{self._now.year}"
                                + F"_{self._now.month:02d}.xls")
                downfile = download(dat_url, downfilepath)
                if os.path.exists(downfilepath):
                    move(downfile, downfilepath)

            self._stitch()
        elif self._data_source == 'Pi':
            if mongo_connection is None:
                self._mongo_db = mongoConnect()
            else:
                self._mongo_db = mongo_connection
            self._stitch()
        else:
            message("Valid data sources are 'Pi' or 'WEL'", mssgType='WARNING')
            quit()

    def time_from_args(self,
                       arg_string=None):
        parser = argparse.ArgumentParser()
        parser.add_argument('-t', type=int, action='store',
                            help='specify number of hours into past to plot. '
                                 'Example: <-t 12> plots the past 12 hours.')
        parser.add_argument('-r', type=str, action='store', nargs=2,
                            help='specify start and end time to plot as two '
                                 'strings in iso format. Example: '
                                 '<-r \'2020-03-22 12:00\' '
                                 '\'2020-03-22 15:00\'>')
        if arg_string is None:
            args = parser.parse_args()
        else:
            args = parser.parse_args(arg_string)
        timerange = None

        if args.t:
            timerange = [self._now - dt.timedelta(hours=args.t), 'none']
        if args.r:
            timerange = args.r

        return self.timeCondition(timerange)

    """
    From a filepath, load that data.
    Columns with all NaNs are dropped.

    ADDED COLUMNS:
    dateandtime : combined datetime object for each row.
    power_tot : TAH_W + HP_W
    T_diff : living_T - outside_T
    eff_ma : day length rolling average of efficiency

    filepath : filepath for data file.
    keepdata : boolean keep downloaded data file. Default False.
    """
    def read_log(self,
                 filepath):
        try:
            data = pd.read_excel(filepath)
        except Exception:
            data = pd.read_csv(filepath, sep='\t',
                               index_col=False, na_values=['?'])

        for col in data.columns:
            if ('Date' not in col) and ('Time' not in col):
                data[col] = data[col].astype(np.float64)

        data.Date = data.Date.apply(lambda date:
                                    dt.datetime.strptime(date, "%m/%d/%Y"))
        data.Time = data.Time.apply(lambda time:
                                    dt.datetime.strptime(time,
                                                         "%H:%M:%S").time())

        data['dateandtime'] = [dt.datetime.combine(date, time)
                               for date, time in zip(data.Date,
                                                     data.Time)]
        data.index = data['dateandtime']
        data = data.tz_localize(timezone('EST'))
        data = data.tz_convert(self._to_tzone)
        data.drop(columns=['Date', 'Time'])

        if self._calc_cols:
            data = pd.concat((data, self._calced_cols(data)), axis=1)

        return data

    def _calced_cols(self,
                     frame):
        out_frame = pd.DataFrame()

        heat_mask = frame.heat_1_b % 2
        heat_mask[heat_mask == 0] = np.nan

        # Additional calculated columns
        try:
            out_frame['geo_tot_w'] = frame.power_tot
        except AttributeError:
            frame['power_tot'] = frame.TAH_W + frame.HP_W
            out_frame['geo_tot_w'] = frame.power_tot
        try:
            out_frame['base_load_w'] = np.abs(frame.house_w - frame.power_tot
                                              - frame.dehumidifier_w)
        except AttributeError:
            pass
        try:
            out_frame['T_diff'] = np.abs(np.mean([frame.fireplace_T,
                                                  frame.D_room_T,
                                                  frame.V_room_T,
                                                  frame.T_room_T])
                                         - frame.outside_T)
        except AttributeError:
            out_frame['T_diff'] = np.abs(frame.living_T - frame.outside_T)
        out_frame['T_diff_eff'] = (frame.power_tot / out_frame.T_diff)

        # COP calculation
        air_density = 1.15
        surface_area = 0.34
        heat_capacity = 1.01
        COP = (((air_density * surface_area * heat_capacity * frame.TAH_fpm)
                * (np.abs(frame.TAH_out_T - frame.TAH_in_T)))
               / (frame.HP_W / 1000))
        COP[COP > 5] = np.nan
        COP = COP * heat_mask
        out_frame['COP'] = COP
        # WEL COP calculation
        well_gpm = 13.6
        gpm_to_lpm = 0.0630902
        out_frame['well_W'] = ((well_gpm * gpm_to_lpm) * 4.186
                               * (np.abs(frame.loop_out_T - frame.loop_in_T)))
        well_COP = out_frame.well_W / (frame.HP_W / 1000)
        well_COP[well_COP > 5] = np.nan
        well_COP = well_COP * heat_mask
        out_frame['well_COP'] = well_COP

        # Reset rain accumulation every 24 hrs
        try:
            rain_offset = (frame.groupby(frame.index.date)['weather_station_R']
                           .transform(lambda x: x.iloc[-1]))
            out_frame['rain_accum_R'] = (frame['weather_station_R']
                                         - rain_offset)
        except KeyError:
            message("Weather station rain data not present in selection",
                    mssgType='WARNING')

        return out_frame

    """
    Check if the last month's log has been downloaded, and download if not.

    month : specify month to download to db. If no month is specified, download
            the previous month.

    returns a string with the downloaded month.
    """
    def check_dl_db(self,
                    month=None,
                    forcedl=False):
        if not os.path.exists(self._dl_db_path):
            os.mkdir(self._dl_db_path)
        if month is None:
            month = self._now - relativedelta(months=1)
        prev_db_path_xls = (self._dl_db_path + F'WEL_log_{month.year}'
                                               F'_{month.month:02d}.xls')
        this_month = self._now.date().month == month.month
        if (not os.path.exists(prev_db_path_xls)) or forcedl or this_month:
            prev_url = ('http://www.welserver.com/WEL1060/'
                        F'WEL_log_{month.year}_{month.month:02d}')
            prev_db_path_zip = (self._dl_db_path + F'WEL_log_{month.year}'
                                                   F'_{month.month:02d}.zip')
            try:
                message(F"Downloading {month.year}-{month.month}:\n",
                        mssgType='ADMIN')
                download(prev_url + '.zip', prev_db_path_zip)
                os.system(F'unzip {prev_db_path_zip} -d {self._dl_db_path}'
                          F';rm {prev_db_path_zip}')
            except HTTPError:
                try:
                    download(prev_url + '.xls', prev_db_path_xls)
                except Exception:
                    message(F"Error while downloading log: {HTTPError}",
                            mssgType='ERROR')

    """
    Redownload all months since 2020-3-1 to db.
    """
    def refresh_db(self,
                   forcedl=False):
        first = dt.date(2020, 3, 1)
        num_months = ((self._now.year - first.year) * 12
                      + self._now.month - first.month)
        monthlist = [first + relativedelta(months=x)
                     for x in range(num_months + 1)]
        [self.check_dl_db(month=month, forcedl=forcedl) for month in monthlist]

    """
    Load correct months of data based on timerange.
    """
    def _stitch(self):
        if self._data_source == 'WEL':
            load_new = False
            if self.data is not None:
                if ((self.data.dateandtime.iloc[0] > self.timerange[0]) or
                   (self.data.dateandtime.iloc[-1] < self.timerange[1])):
                    load_new = True
            else:
                load_new = True
            if load_new:
                num_months = ((self.timerange[1].year - self.timerange[0].year)
                              * 12 + self.timerange[1].month
                              - self.timerange[0].month)
                monthlist = [self.timerange[0] + relativedelta(months=x)
                             for x in range(num_months + 1)]
                loadedstring = [F'{month.year}-{month.month}'
                                for month in monthlist]
                message(F'Loaded: {loadedstring}', mssgType='ADMIN')
                datalist = [self.read_log(self._dl_db_path
                                          + F'WEL_log_{month.year}'
                                          + F'_{month.month:02d}.xls')
                            for month in monthlist]
                # print(datalist)
                self.data = pd.concat(datalist)

                # Shift power meter data by one sample for better alignment
                self.data.HP_W = self.data.HP_W.shift(-1)
                self.data.TAH_W = self.data.TAH_W.shift(-1)
                tmask = ((self.data.index > self.timerange[0])
                         & (self.data.index < self.timerange[1]))
                self.data = self.data[tmask]

        if self._data_source == 'Pi':
            query = {'dateandtime': {'$gte': self.timerange[0]
                                     .astimezone(self._db_tzone),
                                     '$lte': self.timerange[1]
                                     .astimezone(self._db_tzone)}}
            # print(F"#DEBUG: query: {query}")
            self.data = pd.DataFrame(list(self._mongo_db.data.find(query)))
            if len(self.data) == 0:
                raise Exception("No data came back from mongo server.")
            self.data.index = self.data['dateandtime']
            self.data = self.data.drop(columns=['dateandtime'])
            # print(self.data.columns)
            self.data = self.data.tz_localize(self._db_tzone)
            self.data = self.data.tz_convert(self._to_tzone)
            # print(F"#DEBUG: timerange from: {self.data.index[-1]}"
            #       "to {self.data.index[0]}")

            # Shift power meter data by one sample for better alignment
            self.data.HP_W = self.data.HP_W.shift(-1)
            self.data.TAH_W = self.data.TAH_W.shift(-1)

            self.data = pd.concat((self.data, self._calced_cols(self.data)),
                                  axis=1)

    """
    Returns list of all column names.
    """
    def vars(self):
        return [col for col in self.data.columns]

    """
    Takes a list with a start and end time. If either is 'none', defaults to
    12 hours ago or latest time respectively. Converts iso strings to datetime,
    keeps datetime as datetime.
    """
    def timeCondition(self,
                      timerange):
        if timerange is None:
            timerange = [self._now - dt.timedelta(hours=12), self._now]
            return timerange
        if timerange[0] == 'none':
            timerange[0] = self._now - dt.timedelta(hours=12)
        else:
            if type(timerange[0]) is str:
                timerange[0] = dt.datetime.fromisoformat(timerange[0])
        if timerange[1] == 'none':
            timerange[1] = self._now
        else:
            if type(timerange[1]) is str:
                timerange[1] = dt.datetime.fromisoformat(timerange[1])

        return timerange

    """
    Converts variable name string into object data string, to be evaluated as
    a python expression.

    string : expression string to be modified.
    optional mask : indicates this is for status mask data, including a call to
                    remOffset
    """
    def _varExprParse(self,
                      string,
                      mask=False):
        splitString = re.split('(\\()|(\\))|(\\s)', string)
        splitString = [w for w in splitString if w is not None]

        expr = ""
        for word in splitString:
            possibleVars = [var for var in self.data.columns if var in word]
            if len(possibleVars) > 0:
                foundVar = max(possibleVars, key=len)
                if mask:
                    rst = ("self.remOffset(self.data['"
                           + foundVar + "'])")
                else:
                    rst = "self.data['" + foundVar + "']"
                expr += word.replace(foundVar, rst)
            else:
                expr += word

        return expr

    """
    Adds day/night background shading based on calculated sunrise/sunset times
    to the specified axes.

    axes : axes to plot on.
    timerange : timerange to plot on.
    """
    def _plotNighttime(self,
                       axes=None,
                       plot=True):
        dayList = [(self.timerange[0] + dt.timedelta(days=x - 1)).date()
                   for x in range((self.timerange[1]
                                   - self.timerange[0]).days + 3)]
        for day in dayList:
            day = dt.datetime.combine(day, dt.datetime.min.time())
            sunrise = sun.sunrise(self._loc.observer, date=day,
                                  tzinfo=self._to_tzone)
            sunset = sun.sunset(self._loc.observer, date=day,
                                tzinfo=self._to_tzone)
            # print(F"#DEBUG: sunrise: {sunrise}, sunset: {sunset}")
            timelist = [day, sunrise - dt.timedelta(seconds=1), sunrise,
                        sunset, sunset + dt.timedelta(seconds=1),
                        day + dt.timedelta(days=1)]

            if plot:
                axes.autoscale(enable=False)
                limits = axes.get_ylim()
                axes.fill_between(timelist, np.full(len(timelist), limits[0]),
                                  np.full(len(timelist), limits[1]),
                                  where=[True, True, False, False, True, True],
                                  facecolor='black', alpha=0.05)
        return timelist

    """
    Remove plotting offset from status channel data
    status : data from which to remove offset
    """
    def remOffset(self,
                  status):
        mask = np.array(status) % 2
        mask[mask == 0.] = np.nan
        return mask

    """
    Plot two variables against each other.

    y : Single variable or list of variable names to plot on y axis. Math
       operations can be used in a variable string in the list.
    optional x : Defaults to 'dateandtime'. Variable name to plot on x axis.
    optional xunits : Defaults to 'Time'. Variable string to display on x axis.
    optional yunits : Defaults to 'None'. Varaible string to display on y axis.
    optional timerange : 2 length array with start and end time as iso string,
                         datetime object or if 'none' defaults to start/end
                         time in that position.
    optional statusmask : string describing which binary channels to use as a
                          mask for all plotted variables.
    optional axes : axes to draw plot on instead of default figure.
    optional nighttime : adds day/night shading to plot.
    optional **kwargs : passed on to plot function

    returns plotted data as dictionary of dataframes
    """
    def plotVar(self,
                y,
                x='dateandtime',
                xunits='Time',
                yunits='None',
                statusmask=None,
                maskghost=True,
                axes=None,
                nighttime=True,
                **kwargs):
        if type(y) is not list:
            y = [y]
        p_locals = locals()
        if statusmask is not None:
            smask = eval(self._varExprParse(statusmask, mask=True), p_locals)
        else:
            smask = np.full(np.shape(self.data.index), True)

        # plotx = eval(self._varExprParse(x), p_locals)
        ploty = [eval(self._varExprParse(expr), p_locals) for expr in y]

        if axes is None:
            fig = plt.figure(figsize=self._figsize)
            axes = plt.gca()

        if ('time' or 'date') in x:
            lines = {label: axes.plot_date(plotDatum.index, plotDatum * smask,
                                           '-', label=label, **kwargs)
                     for label, plotDatum in zip(y, ploty)}
            if statusmask is not None and maskghost:
                [axes.plot_date(plotDatum.index, plotDatum, fmt='-', alpha=0.3,
                                color=lines[label][0].get_color(), **kwargs)
                 for label, plotDatum in zip(y, ploty)]
            plt.setp(axes.get_xticklabels(), rotation=20, ha='right')
            axes.set_xlim(self.timerange)
            if nighttime:
                self._plotNighttime(axes=axes)
        # else:
        #     [plt.plot(plotx, plotDatum, '.', label=label, **kwargs)
        #      for label, plotDatum in zip(y, ploty)]
        #     axes.set_xlabel(xunits)
        #     axes.set_xlim((np.nanmin(plotx), np.nanmax(plotx)))

        if yunits == 'None':
            usedVars = [var for var in self.data.columns if var in y[0]]
            if usedVars[0][-1] == 'T':
                yunits = "Temperature / °C"
            if usedVars[0][-1] == 'W':
                yunits = "Power / W"
            if usedVars[0][-3:] == 'fpm':
                yunits = "Windspeed / m/s"
        axes.set_ylabel(yunits)
        axes.yaxis.set_label_position("right")
        axes.yaxis.tick_right()
        # axes.legend(bbox_to_anchor=(0., 1.02, 1., .102), loc='lower left',
        #             ncol=7, mode="expand", borderaxespad=0)
        # axes.legend(bbox_to_anchor=(-0.01, 1,), loc='upper right',
        #             borderaxespad=0)
        axes.legend(borderaxespad=0, loc='center left')
        axes.grid(True)
        plt.tight_layout()

        return {label: datum * smask for label, datum in zip(y, ploty)}

    """
    Plots all hardcoded status variables against time.

    optional timerange : 2 length array with start and end time as iso string,
                         datetime object or if 'none' defaults to start/end
                         time in that position.
    optional axes : axes to draw plot on instead of default figure.
    optional nighttime : adds day/night shading to plot.
    """
    def plotStatus(self,
                   axes=None,
                   nighttime=True,
                   status_list=['aux_heat_b',
                                'heat_1_b',
                                'heat_2_b',
                                'rev_valve_b',
                                'TAH_fan_b',
                                'zone_1_b',
                                'zone_2_b',
                                'humid_b']):
        labels = [stat[:-2] for stat in status_list]

        p_locals = locals()
        # plotx = eval(self._varExprParse('dateandtime'), p_locals)
        ploty = [eval(self._varExprParse(stat), p_locals)
                 for stat in status_list]

        if axes is None:
            fig = plt.figure(figsize=(self._figsize[0],
                                      self._figsize[1] * 0.75))
            axes = plt.gca()

        [axes.plot_date(plotDatum.index, plotDatum, fmt='-', label=label)
            for label, plotDatum in zip(labels, ploty)]

        axes.set_ylim((-0.75, 2 * (len(status_list) - 1) + 1.75))
        if nighttime:
            self._plotNighttime(axes=axes)

        plt.setp(axes.get_xticklabels(), rotation=20, ha='right')
        axes.set_yticks(np.arange(0, 16, 2))
        axes.set_yticklabels(labels)
        axes.yaxis.set_label_position("right")
        axes.yaxis.tick_right()
        axes.grid(True)
        axes.set_xlim(self.timerange)
        plt.tight_layout()
