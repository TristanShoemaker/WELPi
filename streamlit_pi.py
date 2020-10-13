import streamlit as st
import altair as alt
import pandas as pd
import datetime as dt
import sys
import time
import libmc
import subprocess
import json
if sys.platform == 'linux':
    sys.path.append('/home/ubuntu/WEL/WELPy/')
elif sys.platform == 'darwin':
    sys.path.append('../WELPy/')
else:
    raise('Platform not recognized.')
from WELServer import WELData, mongoConnect


st.beta_set_page_config(page_title="Geo Monitor",
                        page_icon="🌀")


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
def serverStartup():
    message("Server Started")


@st.cache(hash_funcs={"pymongo.database.Database": id})
def cachedMongoConnect():
    message("Mongo Connected")
    return mongoConnect()


@st.cache()
def cachedMemCache():
    message("MemCache Connected")
    return libmc.Client(['localhost'])


@st.cache(allow_output_mutation=True)
def cachedWELData(date_range):
    return WELData(timerange=date_range,
                   mongo_connection=cachedMongoConnect())


def date_select():
    date_range = st.sidebar.date_input(label='Date Range',
                                       value=[(dt.datetime.now()
                                               - dt.timedelta(days=1)),
                                              dt.datetime.now()],
                                       min_value=dt.datetime(2020, 8, 3),
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
    if host == 'pi_temp':
        command = ['sensors', '-j']
        temp = json.loads(subprocess.run(command,
                          stdout=subprocess.PIPE).stdout.decode('utf-8'))
        temp = temp["cpu_thermal-virtual-0"]["temp1"]["temp1_input"]
        return F"{temp:.1f} °C"


def whichFormatFunc(option):
    if option == 'temp':
        return "Temperature"
    if option == 'pandw':
        return "Power and Water"


def nearestTimeGen():
    return alt.selection(type='single',
                         nearest=True,
                         on='mouseover',
                         fields=['dateandtime'],
                         empty='none')


def resize():
    return alt.selection(type='interval',
                         encodings=['x'])


class streamPlot():
    resample_P = 350
    def_width = 700
    def_height = 280
    def_spacing = 2
    stat_height_mod = 0.5
    cop_height_mod = 0.6
    pwr_height_mod = 0.7
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
    nearestTime = None
    mssg_tbl = None

    def __init__(self):
        self.nearestTime = nearestTimeGen()

    def makeTbl(self):
        self.mssg_tbl = st.sidebar.table()

    def makeWEL(self,
                date_range,
                resample_P=None):
        if resample_P is None:
            resample_P = self.resample_P
        tic = time.time()
        dat = cachedWELData(date_range)
        resample_T = (dat.timerange[1] - dat.timerange[0]) / resample_P
        dat.data = dat.data.resample(resample_T).mean()
        message([F"{'WEL Data init:': <20}", F"{time.time() - tic:.2f} s"],
                tbl=self.mssg_tbl)
        self.dat = dat

    def getDataSubset(self,
                      vars):
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

    def createRules(self,
                    source):
        selectors = alt.Chart(source).mark_point().encode(
            x='dateandtime:T',
            opacity=alt.value(0),
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

    def createTimeText(self,
                       rules):
        time_text_dy = self.def_height * self.cop_height_mod / 2 + 10
        time_text = rules.mark_text(align='center',
                                    dx=0,
                                    dy=time_text_dy
                                    ).encode(
            text=alt.condition(self.nearestTime,
                               'dateandtime:T',
                               alt.value(' '),
                               format='%b %-d, %H:%M'),
            color=alt.ColorValue('black')
        )

        return time_text

    def plotNightAlt(self,
                     height_mod=1):
        source = self.getDataSubset('daylight')
        area = alt.Chart(source).mark_bar(
            fill='black',
            width=10,
            clip=True,
            height=self.def_height * height_mod
        ).encode(
            x='dateandtime:T',
            opacity=alt.condition(alt.datum.value < 1,
                                  alt.value(0.006),
                                  alt.value(0))
        )

        return area

    def plotMainMonitor(self,
                        vars,
                        axis_label="Temperature / °C",
                        bottomPlot=False):
        source = self.getDataSubset(vars)

        lines = alt.Chart(source).mark_line(interpolate='basis').encode(
            x=alt.X('dateandtime:T',
                    # scale=alt.Scale(domain=self.resize()),
                    axis=alt.Axis(title=None,
                                  labels=False,
                                  grid=False,
                                  ticks=False,
                                  domainWidth=0)),
            y=alt.Y('value:Q',
                    scale=alt.Scale(zero=False),
                    axis=alt.Axis(title=axis_label,
                                  orient='right',
                                  grid=True)),
            color=alt.Color('label',
                            legend=alt.Legend(title='Sensors')),
            strokeWidth=alt.condition(alt.datum.label == 'outside_T',
                                      alt.value(2.5),
                                      alt.value(1.5)),
        )

        points = lines.mark_point().encode(
            opacity=alt.condition(self.nearestTime,
                                  alt.value(1),
                                  alt.value(0))
        )

        text = lines.mark_text(align='left', dx=5, dy=-5).encode(
            text=alt.condition(self.nearestTime,
                               'value:Q',
                               alt.value(' '),
                               format='.1f')
        )

        selectors, rules = self.createRules(source)

        plot = alt.layer(
            self.plotNightAlt(), lines, points, text, selectors, rules
        )

        if bottomPlot:
            time_text = self.createTimeText(rules)
            plot = alt.layer(plot, time_text)

        return plot

    def plotStatusPlot(self):
        status_list = ['TAH_fan_b', 'heat_1_b', 'heat_2_b', 'zone_1_b',
                       'zone_2_b', 'humid_b', 'rev_valve_b', 'aux_heat_b']
        source = self.getDataSubset(status_list)
        source.value = source.value % 2
        # source = source.loc[source.value != 0]

        chunks = alt.Chart(source).mark_bar(
            width=self.def_width / self.resample_P,
            clip=True
        ).encode(
            x=alt.X('dateandtime:T',
                    axis=alt.Axis(title=None,
                                  labels=False,
                                  grid=False,
                                  ticks=False,
                                  domainWidth=0)),
            y=alt.Y('label',
                    title=None,
                    axis=alt.Axis(orient='right',
                                  grid=False),
                    sort=status_list),
            opacity=alt.condition(alt.datum.value > 0,
                                  alt.value(100),
                                  alt.value(0)),
            color=alt.Color('label', legend=None)
        )

        plot = alt.layer(
            self.plotNightAlt(), chunks, *self.createRules(source)
        )

        return plot

    def plotCOPPlot(self,
                    bottomPlot=False):
        source = self.getDataSubset(['COP', 'well_COP'])
        lines = alt.Chart(source).transform_window(
            rollmean='mean(value)',
            frame=[-6 * 40, 0]
        ).mark_line(
            interpolate='basis',
            strokeWidth=1.5
        ).encode(
            x=alt.X('dateandtime:T',
                    # scale=alt.Scale(domain=self.resize()),
                    axis=alt.Axis(grid=False,
                                  labels=False,
                                  ticks=False),
                    title=None),
            y=alt.Y('rollmean:Q',
                    scale=alt.Scale(zero=True),
                    axis=alt.Axis(orient='right',
                                  grid=True),
                    title='COP Rolling Mean'),
            color='label'
        )

        points = lines.mark_point().encode(
            opacity=alt.condition(self.nearestTime,
                                  alt.value(1),
                                  alt.value(0))
        )

        text = lines.mark_text(align='left', dx=5, dy=-5).encode(
            text=alt.condition(self.nearestTime,
                               'rollmean:Q',
                               alt.value(' '),
                               format='.1f')
        )

        selectors, rules = self.createRules(source)

        plot = alt.layer(
            self.plotNightAlt(), lines, points, text, selectors,
            rules
        )

        if bottomPlot:
            time_text = self.createTimeText(rules)
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
                    self.plotStatusPlot().properties(
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
                    self.plotCOPPlot(bottomPlot=True).properties(
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
                    self.plotStatusPlot().properties(
                        width=self.def_width,
                        height=self.def_height * self.stat_height_mod
                    ),
                    self.plotMainMonitor(sensor_groups[0]).properties(
                        width=self.def_width,
                        height=self.def_height
                    ),
                    self.plotMainMonitor(sensor_groups[1],
                                         axis_label="Power / W").properties(
                        width=self.def_width,
                        height=self.def_height * self.pwr_height_mod
                    ),
                    self.plotMainMonitor(sensor_groups[2],
                                         axis_label="Wind Speed / m/s",
                                         bottomPlot=True).properties(
                        width=self.def_width,
                        height=self.def_height * self.pwr_height_mod
                    ),
                    spacing=self.def_spacing
                ).resolve_scale(
                    y='independent',
                    color='independent'
                )

        message([F"{'Altair plot gen:': <20}", F"{time.time() - tic:.2f} s"],
                tbl=self.mssg_tbl)

        return plot


def cacheCheck(mc, stp, date_mode, date_range, sensor_groups, which='temp'):
    if which == 'temp':
        if (date_mode == 'default' and sensor_groups[0] == stp.in_default
                and sensor_groups[1] == stp.out_default
                and sys.platform == 'linux'):
            return True
    elif which == 'pandw':
        if (date_mode == 'default' and sensor_groups[0] == stp.water_default
                and sensor_groups[1] == stp.pwr_default
                and sensor_groups[2] == stp.wind_default
                and sys.platform == 'linux'):
            return True
    return False


def page_select(mc, stp, date_mode, date_range, sensor_container, which):
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

    if cacheCheck(mc, stp, date_mode, date_range, sensor_groups, which=which):
        tic = time.time()
        plots = mc.get(F"{which}PlotKey")
        if plots is not None:
            message([F"{'MemCache hit:': <20}",
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
    serverStartup()
    mc = cachedMemCache()

    st.markdown(
        f"""
        <style>
            .reportview-container .main .block-container{{
                max-width: {800}px;
                padding-top: {1}rem;
                padding-right: {0.5}rem;
                padding-left: {0}rem;
                padding-bottom: {1}rem;
            }}
        </style>
        """,
        unsafe_allow_html=True)

    # -- sidebar --
    which = st.sidebar.selectbox("Page",
                                 ['temp', 'pandw'],
                                 format_func=whichFormatFunc)

    st.sidebar.subheader("Plot Options:")
    date_range, date_mode = date_select()
    stp = streamPlot()
    sensor_container = st.sidebar.beta_container()

    st.sidebar.subheader("Log:")
    stp.makeTbl()

    # -- main area --
    st.header(F"{whichFormatFunc(which)} Monitor")
    plot_placeholder = st.empty()
    plots = page_select(mc, stp, date_mode, date_range, sensor_container,
                        which)

    tic = time.time()
    plot_placeholder.altair_chart(plots, use_container_width=True)
    message([F"{'Altair plot disp:': <20}", F"{time.time() - tic:.2f} s"],
            tbl=stp.mssg_tbl)

    message([F"{'WEL Status:': <20}", F"{ping('wel')}"], tbl=stp.mssg_tbl)

    message([F"{'Pi Temp:': <20}", F"{ping('pi_temp')}"], tbl=stp.mssg_tbl)


if __name__ == "__main__":
    main()
