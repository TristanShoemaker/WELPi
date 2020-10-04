import streamlit as st
import altair as alt
import matplotlib.pyplot as plt
import numpy as np
import datetime as dt
import sys
import time
sys.path.append('/home/ubuntu/WEL/WELPy/')
# sys.path.append('../WELPy/')
from WELServer import WELData


# @st.cache(hash_funcs={WELData: id})
def makeWEL(date_range):
    return WELData(mongo_local=True,
                   timerange=date_range)


nearestTime = alt.selection(type='single', nearest=True, on='mouseover',
                            fields=['dateandtime'], empty='none')


def getDataSubset(vars):
    source = dat.data.reset_index()
    source = source.melt(id_vars='dateandtime',
                         value_vars=vars,
                         var_name='label')
    return source


def createRules(source):
    selectors = alt.Chart(source).mark_point().encode(
        x='dateandtime:T',
        opacity=alt.value(0),
    ).add_selection(
        nearestTime
    )
    rules = alt.Chart(source).mark_rule(color='gray').encode(
        x='dateandtime:T'
    ).transform_filter(
        nearestTime
    )

    return [selectors, rules]


def plotMainMonitor(vars):
    source = getDataSubset(vars)

    lines = alt.Chart(source).mark_line(interpolate='basis').encode(
        x=alt.X('dateandtime:T',
                axis=alt.Axis(title=None,
                              labels=False,
                              grid=False)),
        y=alt.Y('value:Q',
                scale=alt.Scale(zero=False),
                axis=alt.Axis(title="Temperature / °C",
                              orient='right',
                              grid=True)),
        color='label',
        strokeWidth=alt.condition(alt.datum.label == 'outside_T',
                                  alt.value(2.5),
                                  alt.value(1.5)),
    )
    points = lines.mark_point().encode(
        opacity=alt.condition(nearestTime, alt.value(1), alt.value(0))
    )

    text = lines.mark_text(align='left', dx=5, dy=-5).encode(
        text=alt.condition(nearestTime,
                           'value:Q',
                           alt.value(' '),
                           format='.1f')
    )

    plot = alt.layer(
        lines, points, text, *createRules(source)
    )

    return plot


def plotStatusPlot():
    status_list = ['TAH_fan_b', 'heat_1_b', 'heat_2_b', 'zone_1_b',
                   'zone_2_b', 'humid_b', 'rev_valve_b', 'aux_heat_b']
    source = getDataSubset(status_list)
    source.value = source.value % 2

    chunks = alt.Chart(source).mark_bar(width=1).encode(
        x=alt.X('dateandtime:T',
                axis=alt.Axis(title=None,
                              labels=False,
                              grid=False)),
        y=alt.Y('label',
                title=None,
                axis=alt.Axis(orient='right'),
                sort=status_list),
        opacity=alt.condition(alt.datum.value > 0,
                              alt.value(100),
                              alt.value(0)),
        color=alt.Color('label', legend=None)
    )

    plot = alt.layer(
        chunks, *createRules(source)
    )

    return plot


def plotCOPPlot():
    source = getDataSubset(['COP'])
    lines = alt.Chart(source).transform_window(
        rollmean='mean(value)',
        frame=[-3 * 3600, 0]
    ).mark_line(
        strokeWidth=1.5
    ).encode(
        x=alt.X('dateandtime:T',
                axis=alt.Axis(grid=False),
                title=None),
        y=alt.Y('rollmean:Q',
                scale=alt.Scale(zero=False),
                axis=alt.Axis(orient='right',
                              grid=True),
                title='COP 3Hr Rolling Mean'))

    points = lines.mark_point().encode(
        opacity=alt.condition(nearestTime, alt.value(1), alt.value(0))
    )

    text = lines.mark_text(align='left', dx=5, dy=-5).encode(
        text=alt.condition(nearestTime,
                           'rollmean:Q',
                           alt.value(' '),
                           format='.1f')
    )

    plot = alt.layer(
        lines, points, text, *createRules(source)
    )

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


def date_select():
    date_range = st.sidebar.date_input(label='Date Range',
                                       value=[(dt.datetime.now()
                                               - dt.timedelta(days=1)),
                                              dt.datetime.now()],
                                       min_value=dt.datetime(2020, 7, 1),
                                       max_value=dt.datetime.now())
    date_range = list(date_range)
    if len(date_range) < 2:
        st.warning('Please select a start and end date.')
    selected_today = date_range[1] == dt.datetime.now().date()
    if selected_today:
        date_range[1] = dt.datetime.now()
    else:
        date_range[1] = dt.datetime.combine(date_range[1],
                                            dt.datetime.max.time())
    date_range[0] = dt.datetime.combine(date_range[0], dt.datetime.max.time())
    if date_range[1] - date_range[0] < dt.timedelta(hours=24):
        date_range[0] = date_range[1] - dt.timedelta(hours=12)

    return date_range


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

def_width = 640
def_height = 230

tic = time.time()
with st.spinner('Generating Plots'):
    temp = alt.vconcat(
        plotStatusPlot().properties(
            width=def_width,
            height=def_height * 0.6
        ),
        plotMainMonitor(in_sensors).properties(
            width=def_width,
            height=def_height
        ),
        plotMainMonitor(out_sensors).properties(
            width=def_width,
            height=def_height * 1.2
        ),
        plotCOPPlot().properties(
            width=def_width,
            height=def_height * .6
        ),
        spacing=0
    ).resolve_scale(
        y='independent',
        color='independent'
    )

print(F"{time.strftime('%Y-%m-%d %H:%M')}: "
      F"Altair plot gen: {time.time() - tic:.2f} s")


# tic = time.time()
plot_placeholder.altair_chart(temp)
# print(F"Altair plot display: {time.time() - tic} s")

# tic = time.time()
# temp_pyplot = plotMainMonitor_pyplot([in_sensors,
#                                       out_sensors])
# print(F"Time for pyplot plot generation: {time.time() - tic}")
# tic = time.time()
# st.pyplot(temp_pyplot)
# print(F"Time for pyplot plot display: {time.time() - tic}")

# st.altair_chart(plotMainMonitor(in_sensors), use_container_width=True)
# st.altair_chart(plotMainMonitor(out_sensors), use_container_width=True)
# st.pyplot(temp_pyplot)
