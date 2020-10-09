import streamlit as st
import altair as alt
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import datetime as dt
import sys
import time
if sys.platform == 'linux':
    sys.path.append('/home/ubuntu/WEL/WELPy/')
elif sys.platform == 'darwin':
    sys.path.append('../WELPy/')
else:
    raise('Platform not recognized.')
from WELServer import WELData, mongoConnect


@st.cache(hash_funcs={"builtins.dict": id})
def makeWEL(date_range,
            resample_P=350):
    tic = time.time()
    dat = WELData(timerange=date_range,
                  mongo_connection=mongo_connection)
    if resample_P is not None:
        resample_T = (dat.timerange[1] - dat.timerange[0]) / resample_P
        dat.data = dat.data.resample(resample_T).mean()
    print(F"{time.strftime('%Y-%m-%d %H:%M')} : "
          F"MakeWEL:             {time.time() - tic:.2f} s", flush=True)
    return dat


nearestTime = alt.selection(type='single',
                            nearest=True,
                            on='mouseover',
                            fields=['dateandtime'],
                            empty='none')

resize = alt.selection_interval(encodings=['x'])


def getDataSubset(vars):
    source = dat.data
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


def createRules(source):
    selectors = alt.Chart(source).mark_point().encode(
        x='dateandtime:T',
        opacity=alt.value(0),
    ).add_selection(
        nearestTime
    )
    rules = alt.Chart(source).mark_rule().encode(
        x='dateandtime:T',
        color=alt.condition('isValid(datum.value)',
                            alt.ColorValue('gray'),
                            alt.ColorValue('red'))
    ).transform_filter(
        nearestTime
    )

    return [selectors, rules]


def plotNightAlt(height_mod=1):
    source = getDataSubset('daylight')
    area = alt.Chart(source).mark_bar(
        fill='black',
        width=10,
        clip=True,
        height=def_height * height_mod
    ).encode(
        x='dateandtime:T',
        opacity=alt.condition(alt.datum.value < 1,
                              alt.value(0.006),
                              alt.value(0))
    )

    return area


def plotMainMonitor(vars):
    source = getDataSubset(vars)

    lines = alt.Chart(source).mark_line(interpolate='basis').encode(
        x=alt.X('dateandtime:T',
                scale=alt.Scale(domain=resize),
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
        opacity=alt.condition(nearestTime,
                              alt.value(1),
                              alt.value(0))
    )

    text = lines.mark_text(align='left', dx=5, dy=-5).encode(
        text=alt.condition(nearestTime,
                           'value:Q',
                           alt.value(' '),
                           format='.1f')
    )

    plot = alt.layer(
        plotNightAlt(), lines, points, text, *createRules(source)
    )

    return plot


def plotStatusPlot():
    status_list = ['TAH_fan_b', 'heat_1_b', 'heat_2_b', 'zone_1_b',
                   'zone_2_b', 'humid_b', 'rev_valve_b', 'aux_heat_b']
    source = getDataSubset(status_list)
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
        plotNightAlt(), chunks, *createRules(source)
    )

    return plot


def plotCOPPlot():
    source = getDataSubset(['COP'])
    lines = alt.Chart(source).transform_window(
        rollmean='mean(value)',
        frame=[-6 * 40, 0]
    ).mark_line(
        interpolate='basis',
        strokeWidth=1.5
    ).encode(
        x=alt.X('dateandtime:T',
                scale=alt.Scale(domain=resize),
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
        opacity=alt.condition(nearestTime, alt.value(1), alt.value(0))
    )

    text = lines.mark_text(align='left', dx=5, dy=-5).encode(
        text=alt.condition(nearestTime,
                           'rollmean:Q',
                           alt.value(' '),
                           format='.1f')
    )

    selectors, rules = createRules(source)

    time_text_dy = def_height * 0.6 / 2 + 10
    time_text = rules.mark_text(align='center', dx=0, dy=time_text_dy).encode(
        text=alt.condition(nearestTime,
                           'dateandtime:T',
                           alt.value(' '),
                           format='%b %-d, %H:%M'),
        color=alt.ColorValue('black')
    )

    plot = alt.layer(
        plotNightAlt(), lines, points, text, time_text, selectors, rules
    )

    return plot


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
    date_range[0] = dt.datetime.combine(date_range[0], dt.datetime.min.time())
    if selected_today and date_range[1].day - date_range[0].day == 1:
        date_range[0] = date_range[1] - dt.timedelta(hours=12)

    return date_range


@st.cache(hash_funcs={"pymongo.database.Database": id})
def serverStartup():
    print(F"{time.strftime('%Y-%m-%d %H:%M')} : Server Started", flush=True)
    mongo_connection = mongoConnect()
    return mongo_connection

def plotAssembly():
    tic = time.time()
    with st.spinner('Generating Plots'):
        plot = alt.vconcat(
            plotStatusPlot().properties(
                width=def_width,
                height=def_height * 0.5
            ).add_selection(resize),
            plotMainMonitor(in_sensors).properties(
                width=def_width,
                height=def_height
            ),
            plotMainMonitor(out_sensors).properties(
                width=def_width,
                height=def_height
            ),
            plotCOPPlot().properties(
                width=def_width,
                height=def_height * 0.6
            ),
            spacing=0
        ).resolve_scale(
            y='independent',
            color='independent'
        )

    print(F"{time.strftime('%Y-%m-%d %H:%M')} : "
          F"Altair plot gen:     {time.time() - tic:.2f} s", flush=True)

    return plot


def plotMainMonitor_pyplot(vars,
                           timerange=None):
    fig, axes = plt.subplots(4, 1,
                             sharex=True,
                             figsize=(9, 9.5),
                             gridspec_kw={'height_ratios': [0.3, 0.4,
                                                            0.6, 0.2]})

    dat.plotStatus(axes=axes[0])
    dat.plotVar(vars[0],
                statusmask='heat_1_b',
                axes=axes[1])
    dat.plotVar(vars[1],
                statusmask='heat_1_b',
                axes=axes[2])
    dat.plotVar(['outside_T'], axes=axes[2], nighttime=False)
    outside_T_line = [x for x in axes[2].get_lines()
                      if x.get_label() == "outside_T"][0]
    outside_T_line.set(lw=2.5)

    full_range_delta = dat.timerange[1] - dat.timerange[0]
    rolling_interval = int(round(np.clip(((full_range_delta.total_seconds()
                                 / 3600) / 4), 1, 24)))
    dat.plotVar([F"COP.rolling('{rolling_interval}H').mean()"],
                yunits=F'COP {rolling_interval} Hr Mean',
                axes=axes[3])
    axes[3].get_legend().remove()
    plt.subplots_adjust(hspace=0.05)

    return fig


# ---------------------------- Start of Page Code ----------------------------

mongo_connection = serverStartup()

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

date_range = date_select()

dat = makeWEL(date_range)

in_sensors = st.sidebar.multiselect("Inside",
                                    list(dat.vars()),
                                    ['living_T',
                                     'trist_T',
                                     'base_T',
                                     'wood_fire_T'])

out_sensors = st.sidebar.multiselect("Loop",
                                     list(dat.vars()),
                                     ['TAH_in_T',
                                      'TAH_out_T',
                                      'loop_in_T',
                                      'loop_out_T',
                                      'outside_T'])

st.title('Geothermal Monitoring')
plot_placeholder = st.empty()

def_width = 700
def_height = 270
stat_height_mod = 0.5
cop_height_mod = 0.6

plots = plotAssembly()

tic = time.time()
plot_placeholder.altair_chart(plots, use_container_width=True)
print(F"{time.strftime('%Y-%m-%d %H:%M')} : "
      F"Altair plot display: {time.time() - tic:.2f} s", flush=True)
