import streamlit as st
import altair as alt
import pandas as pd
import numpy as np
import datetime as dt
import time
import libmc
import subprocess
import json
from sys import platform
from WELData import WELData, mongoConnect


st.beta_set_page_config(page_title="Geo Monitor",
                        page_icon="🌀",
                        initial_sidebar_state='expanded')


def message(message_text,
            tbl=None):
    timestamp = F"{time.strftime('%Y-%m-%d %H:%M')}"
    if tbl is not None:
        message = pd.DataFrame([{"Message": message_text[0],
                                 "Value": message_text[1]}])
        message.set_index("Message", inplace=True)
        tbl.add_rows(message)
    if type(message_text) is list:
        print(F"{timestamp} : {message_text[0]} {message_text[1]}", flush=True)
    else:
        print(F"{timestamp} : {message_text}", flush=True)


@st.cache()
def _serverStartup():
    message("Server Started")


@st.cache(hash_funcs={"pymongo.database.Database": id})
def _cachedMongoConnect():
    message("Mongo Connected")
    return mongoConnect()


@st.cache()
def _cachedMemCache():
    message("MemCache Connected")
    return libmc.Client(['localhost'])


@st.cache(allow_output_mutation=True)
def _cachedWELData(date_range,
                   data_source='Pi'):
    return WELData(timerange=date_range,
                   data_source=data_source,
                   dl_db_path="/home/ubuntu/WEL/log_db/",
                   mongo_connection=_cachedMongoConnect())


def _date_select():
    date_range = st.sidebar.date_input(label='Date Range',
                                       value=[(dt.datetime.now()
                                               - dt.timedelta(days=1)),
                                              dt.datetime.now()],
                                       min_value=dt.datetime(2020, 3, 21),
                                       max_value=dt.datetime.now())
    date_range = list(date_range)
    while len(date_range) < 2:
        st.warning('Please select a start and end date.')
        st.stop()
    selected_today = date_range[1] == dt.datetime.now().date()
    if selected_today:
        date_range[1] = dt.datetime.now()
    else:
        date_range[1] = dt.datetime.combine(date_range[1],
                                            dt.datetime.min.time())
    date_range[0] = dt.datetime.combine(date_range[0],
                                        dt.datetime.min.time())
    date_mode = 'custom'
    if selected_today and date_range[1].day - date_range[0].day == 1:
        date_range[0] = date_range[1] - dt.timedelta(hours=12)
        date_mode = 'default'

    return [date_range, date_mode]


def ping(host):
    if host == 'wel':
        command = ['ping', '-c', '1', '192.168.68.107']
        if subprocess.call(command, stdout=subprocess.DEVNULL) == 0:
            return "✅"
        else:
            return "❎"
    if host == 'pi_temp' and platform == 'linux':
        command = ['sensors', '-j']
        temp = json.loads(subprocess.run(command,
                          stdout=subprocess.PIPE).stdout.decode('utf-8'))
        temp = temp["cpu_thermal-virtual-0"]["temp1"]["temp1_input"]
        return F"{temp:.1f} °C"
    else:
        return "Not Pi 😞"


def _whichFormatFunc(option):
    if option == 'temp':
        return "Temperature"
    if option == 'pandw':
        return "Power and Water"


def _createNearestTime():
    return alt.selection(type='single',
                         nearest=True,
                         on='mouseover',
                         fields=['dateandtime'],
                         empty='none')


def _createResize():
    return alt.selection(type='interval',
                         encodings=['x'])


class streamPlot():
    resample_N = 250
    def_width = 'container'
    def_height = 245
    def_spacing = 2
    stat_height_mod = 0.5
    cop_height_mod = 0.5
    pwr_height_mod = 0.7
    mark_text_font_size = 13
    label_font_size = 12
    title_font_size = 11
    sensor_list = ['TAH_W', 'HP_W',  'TAH_fpm', 'liqu_refrig_T',
                   'gas_refrig_T', 'loop_in_T', 'loop_out_T', 'outside_T',
                   'power_tot', 'living_T', 'desup_T', 'house_hot_T',
                   'TAH_in_T', 'aux_heat_b', 'heat_1_b', 'heat_2_b',
                   'rev_valve_b', 'TAH_fan_b', 'humid_b', 'zone_1_b',
                   'zone_2_b', 'TAH_out_T', 'desup_return_T', 'buderus_h2o_T',
                   'wood_fire_T', 'tank_h2o_T', 'trist_T', 'base_T',
                   'daylight', 'T_diff', 'COP', 'well_W', 'well_COP']
    in_default = ['living_T', 'trist_T', 'base_T', 'wood_fire_T']
    out_default = ['TAH_in_T', 'TAH_out_T', 'loop_in_T', 'loop_out_T',
                   'outside_T']
    water_default = ['desup_T', 'desup_return_T', 'house_hot_T', 'tank_h2o_T',
                     'buderus_h2o_T']
    pwr_default = ['TAH_W', 'HP_W', 'power_tot']
    wind_default = ['TAH_fpm']
    dat = None
    dat_resample = None
    nearestTime = None
    resize = None
    mssg_tbl = None

    def __init__(self):
        self.nearestTime = _createNearestTime()
        self.resize = _createResize()

    def makeTbl(self):
        self.mssg_tbl = st.sidebar.table()

    def makeWEL(self,
                date_range,
                force_refresh=False):
        tic = time.time()
        if not force_refresh:
            if date_range[0] < dt.datetime(2020, 8, 3):
                dat = _cachedWELData(date_range, data_source='WEL')
            else:
                dat = _cachedWELData(date_range)
        else:
            dat = WELData(timerange=date_range,
                          mongo_connection=_cachedMongoConnect())
        resample_T = (dat.timerange[1] - dat.timerange[0]) / self.resample_N
        self.dat_resample = dat.data.resample(resample_T).mean()
        self.dat = dat
        message([F"{'WEL Data init:': <20}", F"{time.time() - tic:.2f} s"],
                tbl=self.mssg_tbl)

    def _getDataSubset(self,
                       vars,
                       resample=True):
        if resample:
            source = self.dat_resample
        else:
            source = self.dat.data
        source = source.reset_index()
        try:
            source = source.melt(id_vars='dateandtime',
                                 value_vars=vars,
                                 var_name='label')
        except KeyError:
            message(["Key(s) not found in db:", F"{vars}"],
                    tbl=self.mssg_tbl)
            source = pd.DataFrame()
        return source

    def _createRules(self,
                     source):
        selectors = alt.Chart(source).mark_point(opacity=0).encode(
            x='dateandtime:T',
        ).add_selection(
            self.nearestTime
        )
        rules = alt.Chart(source).mark_rule().encode(
            x='dateandtime:T',
            color=alt.condition('isValid(datum.value)',
                                alt.ColorValue('gray'),
                                alt.ColorValue('red'))
        ).transform_filter(
            self.nearestTime
        )

        return [selectors, rules]

    def _createTimeText(self,
                        rules,
                        height_mod,
                        top=False):
        if top:
            flip = -1
        else:
            flip = 1
        time_text_dy = flip * (self.def_height * height_mod / 2 + 11)
        time_text = rules.mark_text(align='center',
                                    dx=0,
                                    dy=time_text_dy,
                                    fontSize=self.mark_text_font_size
                                    ).encode(
            text=alt.condition(self.nearestTime,
                               'dateandtime:T',
                               alt.value(' '),
                               format='%b %-d, %H:%M'),
            color=alt.ColorValue('black')
        )

        return time_text

    def _plotNightAlt(self,
                      height_mod=1):
        source = self._getDataSubset('daylight')
        area = alt.Chart(source).mark_bar(
            fill='black',
            width=12,
            clip=True,
            height=self.def_height * height_mod
        ).encode(
            x='dateandtime:T',
            opacity=alt.condition(alt.datum.value < 1,
                                  alt.value(0.01),
                                  alt.value(0))
        )

        return area

    def plotMainMonitor(self,
                        vars,
                        axis_label="Temperature / °C",
                        height_mod=1,
                        bottomPlot=False):
        source = self._getDataSubset(vars)

        lines = alt.Chart(source).mark_line(interpolate='cardinal').encode(
            x=alt.X('dateandtime:T',
                    # scale=alt.Scale(domain=self.resize),
                    axis=alt.Axis(title=None,
                                  labels=False,
                                  grid=False,
                                  ticks=False,
                                  domainWidth=0)),
            y=alt.Y('value:Q',
                    scale=alt.Scale(zero=False),
                    axis=alt.Axis(title=axis_label,
                                  tickMinStep=1,
                                  orient='right',
                                  grid=True)),
            color=alt.Color('new_label:N',
                            legend=alt.Legend(title='Sensors',
                                              orient='top')),
            strokeWidth=alt.condition(alt.datum.label == 'outside_T',
                                      alt.value(2.5),
                                      alt.value(1.5)),
        ).transform_calculate(
            new_label=alt.expr.slice(alt.datum.label, 0, -2)
        )

        points = lines.mark_point(size=40, filled=True).encode(
            opacity=alt.condition(self.nearestTime,
                                  alt.value(0.8),
                                  alt.value(0))
        )

        text = lines.mark_text(
            align='left',
            dx=5, dy=-5,
            fontSize=self.label_font_size
        ).encode(
            text=alt.condition(self.nearestTime,
                               'value:Q',
                               alt.value(' '),
                               format='.1f')
        )

        latest_opacity = 0.7
        latest_text = lines.mark_text(
            align='left',
            dx=25,
            fontSize=self.mark_text_font_size,
            opacity=latest_opacity
        ).transform_window(
            rank='rank()',
            sort=[alt.SortField('dateandtime', order='descending')]
        ).encode(
            text=alt.condition(alt.datum.rank == 1,
                               'value:Q',
                               alt.value(' '),
                               format='.1f')
        )

        # latest_text_tick = lines.mark_tick(
        #     strokeDash=[1, 1],
        #     xOffset=10,
        #     size=20,
        #     thickness=1.5
        # ).transform_window(
        #     rank='rank()',
        #     sort=[alt.SortField('dateandtime', order='descending')]
        # ).encode(
        #     opacity=alt.condition(alt.datum.rank == 1,
        #                           alt.value(latest_opacity),
        #                           alt.value(0))
        # )

        selectors, rules = self._createRules(source)

        plot = alt.layer(
            self._plotNightAlt(), lines, points, text, selectors, rules,
            latest_text
        )

        if bottomPlot:
            time_text = self._createTimeText(rules, height_mod=height_mod)
            plot = alt.layer(plot, time_text)

        return plot

    def plotStatus(self):
        status_list = ['TAH_fan_b', 'heat_1_b', 'heat_2_b', 'zone_1_b',
                       'zone_2_b', 'humid_b', 'rev_valve_b', 'aux_heat_b']
        source = self._getDataSubset(status_list, resample=True)
        source.value = source.value % 2
        # source = source.loc[source.value != 0]

        chunks = alt.Chart(source).mark_bar(
            width=3.5,
            clip=True
        ).encode(
            x=alt.X('dateandtime:T',
                    axis=alt.Axis(title=None,
                                  labels=False,
                                  grid=False,
                                  ticks=False,
                                  orient='top',
                                  offset=16)),
            y=alt.Y('new_label:N',
                    title=None,
                    axis=alt.Axis(orient='right',
                                  grid=False),
                    sort=status_list),
            opacity=alt.condition(alt.datum.value > 0,
                                  alt.value(1),
                                  alt.value(0)),
            color=alt.Color('new_label:N', legend=None)
        ).transform_calculate(
            new_label=alt.expr.slice(alt.datum.label, 0, -2)
        )
        # .add_selection(
        #     self.resize
        # )

        selectors, rules = self._createRules(source)

        time_text = self._createTimeText(rules, self.stat_height_mod, top=True)

        plot = alt.layer(
            self._plotNightAlt(), chunks, selectors, rules, time_text
        )

        return plot

    def plotCOP(self,
                bottomPlot=False):
        source = self._getDataSubset(['COP', 'well_COP'])

        rolling_frame = (3 * self.resample_N / ((self.dat.timerange[1]
                         - self.dat.timerange[0]).total_seconds() / 3600))
        rolling_frame = int(np.clip(rolling_frame, self.resample_N / 15,
                                    self.resample_N / 2))
        lines = alt.Chart(source).transform_window(
            rollmean='mean(value)',
            frame=[-rolling_frame, 0]
        ).mark_line(
            interpolate='cardinal',
            strokeWidth=1.5
        ).encode(
            x=alt.X('dateandtime:T',
                    axis=alt.Axis(grid=False,
                                  labels=False,
                                  ticks=False),
                    title=None),
            y=alt.Y('rollmean:Q',
                    scale=alt.Scale(zero=False),
                    axis=alt.Axis(orient='right',
                                  grid=True),
                    title='COP Rolling Mean'),
            color=alt.Color('label', legend=alt.Legend(title='Efficiencies',
                                                       orient='top'))
        )

        raw_lines = alt.Chart(source).mark_line(
            interpolate='cardinal',
            strokeWidth=1.5,
            strokeDash=[1, 2],
            opacity=0.8
        ).encode(
            x=alt.X('dateandtime:T'),
            y=alt.Y('value:Q'),
            color='label'
        )

        points = lines.mark_point(size=40, filled=True).encode(
            opacity=alt.condition(self.nearestTime,
                                  alt.value(0.8),
                                  alt.value(0))
        )

        text = lines.mark_text(align='left', dx=5, dy=-5).encode(
            text=alt.condition(self.nearestTime,
                               'rollmean:Q',
                               alt.value(' '),
                               format='.1f')
        )

        selectors, rules = self._createRules(source)

        plot = alt.layer(
            self._plotNightAlt(), lines, raw_lines, points, text, selectors,
            rules
        )

        if bottomPlot:
            time_text = self._createTimeText(rules, self.cop_height_mod)
            plot = alt.layer(plot, time_text)

        return plot

    def plotAssembly(self,
                     sensor_groups=None,
                     which='temp'):
        tic = time.time()

        if which == 'temp':
            if sensor_groups is None:
                sensor_groups = [self.in_default, self.out_default]
            with st.spinner('Generating Plots'):
                plot = alt.vconcat(
                    self.plotStatus().properties(
                        width=self.def_width,
                        height=self.def_height * self.stat_height_mod
                    ),
                    self.plotMainMonitor(sensor_groups[0]).properties(
                        width=self.def_width,
                        height=self.def_height
                    ),
                    self.plotMainMonitor(sensor_groups[1]).properties(
                        width=self.def_width,
                        height=self.def_height
                    ),
                    self.plotCOP(bottomPlot=True).properties(
                        width=self.def_width,
                        height=self.def_height * self.cop_height_mod
                    ),
                    spacing=self.def_spacing
                ).resolve_scale(
                    y='independent',
                    color='independent'
                )

        if which == 'pandw':
            if sensor_groups is None:
                sensor_groups = [self.water_default, self.pwr_default,
                                 self.wind_default]
            with st.spinner('Generating Plots'):
                plot = alt.vconcat(
                    self.plotStatus().properties(
                        width=self.def_width,
                        height=self.def_height * self.stat_height_mod
                    ),
                    self.plotMainMonitor(sensor_groups[0]).properties(
                        width=self.def_width,
                        height=self.def_height
                    ),
                    self.plotMainMonitor(sensor_groups[1],
                                         axis_label="Power / W",
                                         height_mod=self.pwr_height_mod
                                         ).properties(
                        width=self.def_width,
                        height=self.def_height * self.pwr_height_mod
                    ),
                    self.plotMainMonitor(sensor_groups[2],
                                         axis_label="Wind Speed / m/s",
                                         height_mod=self.pwr_height_mod,
                                         bottomPlot=True
                                         ).properties(
                        width=self.def_width,
                        height=self.def_height * self.pwr_height_mod
                    ),
                    spacing=self.def_spacing
                ).resolve_scale(
                    y='independent',
                    color='independent'
                )

        plot = plot.configure_axis(
            labelFontSize=self.label_font_size,
            titleFontSize=self.title_font_size,
            titlePadding=35,
            domain=False
        ).configure_legend(
            labelFontSize=self.label_font_size,
            titleFontSize=self.title_font_size
        ).configure_view(
            cornerRadius=2
        )

        message([F"{'Altair plot gen:': <20}", F"{time.time() - tic:.2f} s"],
                tbl=self.mssg_tbl)

        return plot


def _cacheCheck(mc, stp, date_mode, date_range, sensor_groups, which='temp'):
    if which == 'temp':
        if (date_mode == 'default' and sensor_groups[0] == stp.in_default
                and sensor_groups[1] == stp.out_default
                and platform == 'linux'):
            return True
    elif which == 'pandw':
        if (date_mode == 'default' and sensor_groups[0] == stp.water_default
                and sensor_groups[1] == stp.pwr_default
                and sensor_groups[2] == stp.wind_default
                and platform == 'linux'):
            return True
    return False


def _page_select(mc, stp, date_mode, date_range, sensor_container, which):
    sensor_groups = []
    if which == 'temp':
        in_sensors = sensor_container.multiselect("Inside Sensors",
                                                  stp.sensor_list,
                                                  stp.in_default)
        out_sensors = sensor_container.multiselect("Loop Sensors",
                                                   stp.sensor_list,
                                                   stp.out_default)
        sensor_groups = [in_sensors, out_sensors]

    if which == 'pandw':
        water_sensors = sensor_container.multiselect("Water Sensors",
                                                     stp.sensor_list,
                                                     stp.water_default)
        pwr_sensors = sensor_container.multiselect("Power Sensors",
                                                   stp.sensor_list,
                                                   stp.pwr_default)
        wind_sensors = sensor_container.multiselect("Wind Sensors",
                                                    stp.sensor_list,
                                                    stp.wind_default)
        sensor_groups = [water_sensors, pwr_sensors, wind_sensors]

    if _cacheCheck(mc, stp, date_mode, date_range, sensor_groups, which=which):
        tic = time.time()
        memCache = mc.get(F"{which}PlotKey")
        plots = memCache['plots']
        if plots is not None:
            cache_hit_mssg = ("MemCache hit | "
                              F"{memCache['timeKey'].strftime('%H:%M')}:")
            message([F"{cache_hit_mssg: <20}",
                     F"{time.time() - tic:.2f} s"],
                    tbl=stp.mssg_tbl)
            return plots
        else:
            message([F"{'❗MemCache MISS❗:': <20}",
                     F"{time.time() - tic:.2f} s"],
                    tbl=stp.mssg_tbl)

    stp.makeWEL(date_range)
    plots = stp.plotAssembly(sensor_groups, which)

    return plots


# ---------------------------- Start of Page Code ----------------------------

def main():
    _serverStartup()
    mc = _cachedMemCache()

    st.markdown(
        F"""
        <style>
            .stVegaLiteChart{{
                width: {95}%;
            }}
            .reportview-container .main .block-container{{
                max-width: {1300}px;
                padding-top: {10}px;
                padding-right: {40}px;
                padding-left: {10}px;
                padding-bottom: {0}px;
            }}
        </style>
        """, unsafe_allow_html=True)

    # -- sidebar --
    st.sidebar.subheader("Monitor:")
    which = st.sidebar.selectbox("Page",
                                 ['temp', 'pandw'],
                                 format_func=_whichFormatFunc)

    st.sidebar.subheader("Plot Options:")
    date_range, date_mode = _date_select()
    stp = streamPlot()
    sensor_container = st.sidebar.beta_container()

    st.sidebar.subheader("Log:")
    stp.makeTbl()

    # -- main area --
    st.header(F"{_whichFormatFunc(which)} Monitor")
    plot_placeholder = st.empty()
    plots = _page_select(mc, stp, date_mode, date_range, sensor_container,
                         which)

    tic = time.time()
    plot_placeholder.altair_chart(plots)
    message([F"{'Altair plot disp:': <20}", F"{time.time() - tic:.2f} s"],
            tbl=stp.mssg_tbl)

    message([F"{'WEL Status:': <20}", F"{ping('wel')}"], tbl=stp.mssg_tbl)

    message([F"{'Pi Temp:': <20}", F"{ping('pi_temp')}"], tbl=stp.mssg_tbl)


if __name__ == "__main__":
    main()
