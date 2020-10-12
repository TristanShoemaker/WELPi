import streamlit as st
import altair as alt
import pandas as pd
import datetime as dt
import sys
import time
import libmc
import subprocess
if sys.platform == 'linux':
    sys.path.append('/home/ubuntu/WEL/WELPy/')
elif sys.platform == 'darwin':
    sys.path.append('../WELPy/')
else:
    raise('Platform not recognized.')
from WELServer import WELData, mongoConnect


st.beta_set_page_config(page_title="Geo Monitoring",
                        page_icon="🔩")


def message(message_text,
            tbl=None):
    timestamp = F"{time.strftime('%Y-%m-%d %H:%M')}"
    if tbl is not None:
        print(F"{timestamp} : {message_text[0]} {message_text[1]}", flush=True)
        message = pd.DataFrame([{"Message": message_text[0],
                                 "Value": message_text[1]}])
        message.set_index("Message", inplace=True)
        tbl.add_rows(message)
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
    def_width = 700
    def_height = 270
    stat_height_mod = 0.5
    cop_height_mod = 0.6
    sensor_list = ['TAH_W', 'HP_W',  'TAH_fpm', 'liqu_refrig_T',
                   'gas_refrig_T', 'loop_in_T', 'loop_out_T', 'outside_T',
                   'power_tot', 'living_T', 'desup_T', 'house_hot_T',
                   'TAH_in_T', 'aux_heat_b', 'heat_1_b', 'heat_2_b',
                   'rev_valve_b', 'TAH_fan_b', 'humid_b', 'zone_1_b',
                   'zone_2_b', 'TAH_out_T', 'desup_return_T', 'buderus_h2o_T',
                   'wood_fire_T', 'tank_h2o_T', 'trist_T', 'base_T',
                   'daylight', 'T_diff', 'COP', 'well_W', 'well_COP']
    in_default = ['living_T',
                  'trist_T',
                  'base_T',
                  'wood_fire_T']
    out_default = ['TAH_in_T',
                   'TAH_out_T',
                   'loop_in_T',
                   'loop_out_T',
                   'outside_T']
    dat = None
    nearestTime = None
    mssg_tbl = None

    def __init__(self):
        self.nearestTime = nearestTimeGen()

    def makeTbl(self):
        self.mssg_tbl = st.sidebar.table()

    def makeWEL(self,
                date_range,
                resample_P=350):
        tic = time.time()
        dat = WELData(timerange=date_range,
                      mongo_connection=cachedMongoConnect())
        if resample_P is not None:
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
                        vars):
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
                    axis=alt.Axis(title="Temperature / °C",
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

        plot = alt.layer(
            self.plotNightAlt(), lines, points, text, *self.createRules(source)
        )

        return plot

    def plotStatusPlot(self):
        status_list = ['TAH_fan_b', 'heat_1_b', 'heat_2_b', 'zone_1_b',
                       'zone_2_b', 'humid_b', 'rev_valve_b', 'aux_heat_b']
        source = self.getDataSubset(status_list)
        source.value = source.value % 2
        # source = source.loc[source.value != 0]

        chunks = alt.Chart(source).mark_bar(
            width=self.def_width/350,
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

    def plotCOPPlot(self):
        source = self.getDataSubset(['COP'])
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
                                  # format='%H',
                                  # labelAngle=25,
                                  labels=False,
                                  ticks=False),
                    title=None),
            y=alt.Y('rollmean:Q',
                    scale=alt.Scale(zero=True),
                    axis=alt.Axis(orient='right',
                                  grid=True),
                    title='COP Rolling Mean')
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

        time_text_dy = self.def_height * 0.6 / 2 + 10
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

        plot = alt.layer(
            self.plotNightAlt(), lines, points, text, time_text, selectors,
            rules
        )

        return plot

    def plotAssembly(self,
                     in_sensors=None,
                     out_sensors=None):
        if in_sensors is None:
            in_sensors = self.in_default
        if out_sensors is None:
            out_sensors = self.out_default

        tic = time.time()
        with st.spinner('Generating Plots'):
            plot = alt.vconcat(
                self.plotStatusPlot().properties(
                    width=self.def_width,
                    height=self.def_height * self.stat_height_mod
                ),
                self.plotMainMonitor(in_sensors).properties(
                    width=self.def_width,
                    height=self.def_height
                ),
                self.plotMainMonitor(out_sensors).properties(
                    width=self.def_width,
                    height=self.def_height
                ),
                self.plotCOPPlot().properties(
                    width=self.def_width,
                    height=self.def_height * self.cop_height_mod
                ),
                spacing=0
            ).resolve_scale(
                y='independent',
                color='independent'
            )

        message([F"{'Altair plot gen:': <20}", F"{time.time() - tic:.2f} s"],
                tbl=self.mssg_tbl)

        return plot


# ---------------------------- Start of Page Code ----------------------------

def main():
    serverStartup()

    st.markdown(
        f"""
        <style>
            .reportview-container .main .block-container{{
                max-width: {800}px;
                padding-top: {1}rem;
                padding-right: {0}rem;
                padding-left: {0.5}rem;
                padding-bottom: {1}rem;
            }}
        </style>
        """,
        unsafe_allow_html=True)

    st.sidebar.subheader("Plotting Options:")

    date_range, date_mode = date_select()

    stp = streamPlot()

    in_sensors = st.sidebar.multiselect("Inside Sensors",
                                        stp.sensor_list,
                                        stp.in_default)
    out_sensors = st.sidebar.multiselect("Loop Sensors",
                                         stp.sensor_list,
                                         stp.out_default)

    stp.makeTbl()

    st.header('Geothermal Monitoring')

    plot_placeholder = st.empty()

    if (date_mode == 'default' and in_sensors == stp.in_default
            and out_sensors == stp.out_default and sys.platform == 'linux'):
        tic = time.time()
        mc = cachedMemCache()
        plots = mc.get('plotKey')
        message([F"{'MemCache hit:': <20}", F"{time.time() - tic:.2f} s"],
                tbl=stp.mssg_tbl)
    else:
        stp.makeWEL(date_range)
        plots = stp.plotAssembly(in_sensors, out_sensors)

    tic = time.time()
    plot_placeholder.altair_chart(plots)
    message([F"{'Altair plot disp:': <20}", F"{time.time() - tic:.2f} s"],
            tbl=stp.mssg_tbl)

    message([F"{'WEL Status:': <20}", F"{ping('wel')}"], tbl=stp.mssg_tbl)


if __name__ == "__main__":
    main()
