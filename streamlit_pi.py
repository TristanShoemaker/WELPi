import streamlit as st
import numpy as np
import datetime as dt
import time
import subprocess
import json
import platform
import pytz
import sys
from log_message import message
from pages.PandW import PandW
from pages.Monit import Monit
from pages.Wthr import Wthr
from pages.Testing import Testing
if len(sys.argv) > 1:
    if sys.argv[1] == 'memcheck':
        MEMCHECK = True
else:
    MEMCHECK = False
if MEMCHECK:
    from pympler.tracker import SummaryTracker


to_tz = pytz.timezone('America/New_York')
st.set_page_config(page_title="Geo Monitor",
                   page_icon="🌀",
                   initial_sidebar_state='auto')


@st.cache()
def _serverStartup():
    message("Server Started", mssgType='ADMIN')


def _date_select():
    local_now = dt.datetime.now(to_tz)
    date_range = st.sidebar.date_input(label='Date Range',
                                       value=[local_now, local_now],
                                       min_value=dt.datetime(2020, 3, 21),
                                       max_value=local_now)
    date_range = list(date_range)
    while len(date_range) < 2:
        st.warning('Please select both a start and end date')
        st.stop()
    selected_today = date_range[1] == local_now.date()
    if selected_today:
        date_range[1] = local_now
    else:
        date_range[1] = dt.datetime.combine(date_range[1],
                                            dt.datetime.min.time())
    date_range[0] = dt.datetime.combine(date_range[0],
                                        dt.datetime.min.time())

    def min_round(time):
        time = time.replace(microsecond=0)
        if time.second > 29:
            time = time + dt.timedelta(minutes=1)
        time = time.replace(second=0)
        return time

    date_range = [min_round(date.astimezone(to_tz)) for date in date_range]
    
    return date_range


def ping(host):
    if host == 'wel' and platform.machine() == 'aarch64':
        command = ['ping', '-c', '1', '192.168.68.107']
        if subprocess.call(command, stdout=subprocess.DEVNULL) == 0:
            return "✅"
        else:
            return "❎"
    if host == 'pi_temp' and platform.machine() == 'aarch64':
        command = ['sensors', '-j']
        temp = json.loads(subprocess.run(command,
                          stdout=subprocess.PIPE).stdout.decode('utf-8'))
        temp = temp["cpu_thermal-virtual-0"]["temp1"]["temp1_input"]
        return F"{temp:.1f} °C"
    else:
        return "Not Pi 😞"


def calc_stats(stp):
    N = len(stp.dat.data)
    heat_2_count = (stp.dat.data['heat_2_b'] % 2).sum()
    heat_1_count = (stp.dat.data['heat_1_b'] % 2).sum() - heat_2_count
    # Heat 1 is ~80% of full power
    duty = 100 * ((0.8 * heat_1_count + heat_2_count) / N)

    house_w_avg = stp.dat.data['house_w'].mean() / 1000
    geo_w_avg = stp.dat.data['geo_tot_w'].mean() / 1000
    return [duty, house_w_avg, geo_w_avg]


def _page_select(resample_N, date_range, sensor_container, which):
    if which == 'monit':
        stp = Monit(resample_N, date_range, sensor_container=sensor_container)
    if which == 'pandw':
        stp = PandW(resample_N, date_range, sensor_container=sensor_container)
    if which == 'wthr':
        stp = Wthr(resample_N, date_range, sensor_container=sensor_container)
    if which == 'test':
        stp = Testing(resample_N, date_range,
                      sensor_container=sensor_container)

    return stp


def _whichFormatFunc(option):
    which = {'monit': "Main",
             'pandw': "Power and Water",
             'wthr': "Weather Station",
             'test': "Testing"}
    return which[option]


# ---------------------------- Start of Page Code ----------------------------

def main():
    _serverStartup()

    st.markdown(
        F"""
        <style>
            .stVegaLiteChart{{
                width: {90}%;
            }}
            .reportview-container .main .block-container{{
                max-width: {1300}px;
                padding-top: {5}px;
                padding-right: {90}px;
                padding-left: {10}px;
                padding-bottom: {5}px;
            }}
        </style>
        <style type='text/css'>
            details {{
                display: none;
            }}
        </style>
        """, unsafe_allow_html=True)

    # -- sidebar --
    st.sidebar.subheader("Monitor:")
    stats_containers = [st.sidebar.beta_container() for x in range(3)]
    which = st.sidebar.selectbox("Page",
                                 ['monit', 'pandw', 'wthr', 'test'],
                                 index=0,
                                 format_func=_whichFormatFunc)
    st.sidebar.subheader("Plot Options:")
    date_range = _date_select()
    sensor_container = st.sidebar.beta_container()
    max_samples = int(np.clip((date_range[1] - date_range[0])
                              .total_seconds() / 60, 720, 1440))
    resample_N = st.sidebar.slider("Number of Data Samples",
                                   min_value=10, max_value=max_samples,
                                   value=250, step=10)

    # -- main area --
    st.header(F"{_whichFormatFunc(which)} Monitor")

    stp = _page_select(resample_N, date_range, sensor_container, which)
    stats = calc_stats(stp)
    stats_containers[0].text(F"System Duty: {stats[0]:.1f}%")
    stats_containers[1].text(F"House Mean Power Use: {stats[1]:.2f} kW")
    stats_containers[1].text(F"Geo Mean Power Use: {stats[2]:.2f} kW")
    tic = time.time()
    for plot in stp.plots:
        st.altair_chart(plot)
    message([F"{'Altair plot disp:': <20}", F"{time.time() - tic:.2f} s"],
            tbl=stp.mssg_tbl, mssgType='TIMING')
    del stp


if __name__ == "__main__":
    if MEMCHECK:
        tracker = SummaryTracker()
    main()
    if MEMCHECK:
        tracker.print_diff()
