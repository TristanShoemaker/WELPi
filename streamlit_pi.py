import streamlit as st
import altair as alt
import pandas as pd
import datetime as dt
import sys
import time
import libmc
if sys.platform == 'linux':
    sys.path.append('/home/ubuntu/WEL/WELPy/')
elif sys.platform == 'darwin':
    sys.path.append('../WELPy/')
else:
    raise('Platform not recognized.')
from WELServer import WELData, mongoConnect


def nearestTimeGen():
    return alt.selection(type='single',
                         nearest=True,
                         on='mouseover',
                         fields=['dateandtime'],
                         empty='none')


def resize():
    return alt.selection(type='interval',
                         encodings=['x'])


@st.cache()
def serverStartup():
    print(F"{time.strftime('%Y-%m-%d %H:%M')} : Server Started", flush=True)


@st.cache(hash_funcs={"pymongo.database.Database": id})
def cachedMongoConnect():
    print(F"{time.strftime('%Y-%m-%d %H:%M')} : Mongo Connected", flush=True)
    return mongoConnect()


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

    def __init__(self):
        self.nearestTime = nearestTimeGen()

    def makeWEL(self,
                date_range,
                resample_P=350):
        tic = time.time()
        dat = WELData(timerange=date_range,
                      mongo_connection=cachedMongoConnect())
        if resample_P is not None:
            resample_T = (dat.timerange[1] - dat.timerange[0]) / resample_P
            dat.data = dat.data.resample(resample_T).mean()
        print(F"{time.strftime('%Y-%m-%d %H:%M')} : "
              F"WELData init:        {time.time() - tic:.2f} s", flush=True)
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
            print(F"{time.strftime('%Y-%m-%d %H:%M')} : "
                  F"Key(s) \"{vars}\" not found in database.")
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
            width=2,
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

        print(F"{time.strftime('%Y-%m-%d %H:%M')} : "
              F"Altair plot gen:     {time.time() - tic:.2f} s", flush=True)

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

    date_range, date_mode = date_select()

    stp = streamPlot()

    in_sensors = st.sidebar.multiselect("Inside Sensors",
                                        stp.sensor_list,
                                        stp.in_default)
    dir(in_sensors)
    out_sensors = st.sidebar.multiselect("Loop Sensors",
                                         stp.sensor_list,
                                         stp.out_default)

    st.title('Geothermal Monitoring')
    plot_placeholder = st.empty()

    if (date_mode == 'default' and in_sensors == stp.in_default
            and out_sensors == stp.out_default):
        tic = time.time()
        mc = libmc.Client(['localhost'])
        plots = mc.get('plotKey')
        print(F"{time.strftime('%Y-%m-%d %H:%M')} : "
              F"MemCache hit:        {time.time() - tic:.2f} s", flush=True)
    else:
        stp.makeWEL(date_range)
        plots = stp.plotAssembly(in_sensors, out_sensors)

    tic = time.time()
    plot_placeholder.altair_chart(plots, use_container_width=True)
    print(F"{time.strftime('%Y-%m-%d %H:%M')} : "
          F"Altair plot display: {time.time() - tic:.2f} s", flush=True)


if __name__ == "__main__":
    main()
