import streamlit as st
import altair as alt
import matplotlib.pyplot as plt
import datetime as dt
import numpy as np
import pandas as pd
import sys
sys.path.append('/home/ubuntu/WEL/WELPy/')
from WELServer import WELData


# @st.cache(hash_funcs={WELData: id})
def makeWEL():
    return WELData(mongo_local=True)

# Load data and melt into format for alt
dat = makeWEL()
# dat.data = dat.data.reset_index()
# dat.data

nearestTime = alt.selection(type='single', nearest=True, on='mouseover',
                            fields=['dateandtime'], empty='none')

def plotMainMonitor(vars,
                    status_plot=False):
    status_list=['aux_heat_b', 'heat_1_b', 'heat_2_b', 'rev_valve_b',
                 'TAH_fan_b', 'zone_1_b', 'zone_2_b', 'humid_b']
    temp_source = dat.data.reset_index()
    temp_source = temp_source.melt(id_vars='dateandtime',
                           value_vars=vars,
                           var_name='label')
    lines = alt.Chart(temp_source).mark_line(interpolate='basis').encode(
        x=alt.X('dateandtime:T', axis=alt.Axis(title=None, labels=True)),
        y=alt.Y('value:Q', axis=alt.Axis(format='Q',
                                       title="Temperature / °C")),
        color='label'
    )

    selectors = alt.Chart(temp_source).mark_point().encode(
        x='dateandtime:T',
        opacity=alt.value(0),
    ).add_selection(
        nearestTime
    )

    points = lines.mark_point().encode(
        opacity=alt.condition(nearestTime, alt.value(1), alt.value(0))
    )

    text = lines.mark_text(align='left', dx=5, dy=-5).encode(
        text=alt.condition(nearestTime, 'value:Q', alt.value(' '),
                           format='.1f')
    )

    rules = alt.Chart(temp_source).mark_rule(color='gray').encode(
        x='dateandtime:T'
    ).transform_filter(
        nearestTime
    )

    plot = alt.layer(
        lines, selectors, points, text, rules
    )

    if status_plot:
        stat_source = dat.data.melt(id_vars='dateandtime',
                                       value_vars=status_list,
                                       var_name='label')
        stat_source.value = stat_source.value % 2
        status_plot = alt.Chart(stat_source).mark_bar(width=7).encode(
            alt.X('dateandtime:T'),
            alt.Y('label'),
            alt.FillOpacity('value:Q', legend=None),
            alt.Opacity('value:Q', legend=None)
        )
        plot = plot & status_plot

    return plot


def plotMainMonitor_pyplot(vars,
                           timerange=None):
    fig, axes = plt.subplots(4, 1,
                             sharex=True,
                             figsize=(9,10),
                             gridspec_kw={'height_ratios': [0.4, 0.4, 0.8, 0.4]})

    dat.plotStatus(axes=axes[0])
    dat.plotVar(vars[0],
                statusmask='heat_1_b',
                axes=axes[1])
    dat.plotVar(vars[1],
                statusmask='heat_1_b',
                axes=axes[2])

    full_range_delta = dat.timerange[1] - dat.timerange[0]
    rolling_interval = round(np.clip(((full_range_delta.total_seconds() / 3600) / 4), 1, 24))
    dat.plotVar([F"COP.rolling('{rolling_interval}H').mean()"],
            yunits=F'COP {rolling_interval} Hr Mean',
            axes=axes[3])
    axes[2].get_legend().remove()
    plt.subplots_adjust(hspace=0.05)

    return fig


st.title('Geothermal Monitoring')

# slider_time = st.select_slider("Time Range",
#                         min_value=dat.time_from_args(['-t', '72'])[0],
#                         max_value=dat.time_from_args()[1],
#                         value=dat.time_from_args(),
#                         step=dt.timedelta(minutes=30))


in_sensors = st.multiselect("Inside",
                            list(dat.vars()),
                            ['living_T',
                             'trist_T',
                             'base_T',
                             'outside_T'])

out_sensors = st.multiselect("Loop",
                             list(dat.vars()),
                             ['TAH_in_T',
                              'TAH_out_T',
                              'loop_in_T',
                              'loop_out_T',
                              'liqu_refrig_T',
                              'gas_refrig_T',
                              'outside_T',
                              ])

# water_sensors = st.multiselect("Water",
#                                list(dat.vars()),
#                                ['TAH_in_T',
#                                 'TAH_out_T',
#                                 'loop_in_T',
#                                 'loop_out_T',
#                                 'outside_T',
#                                 'living_T',
#                                 'trist_T',
#                                 'base_T'])

# temp = plotMainMonitor(sensors)
temp_pyplot = plotMainMonitor_pyplot([in_sensors,
                                      out_sensors])


# st.altair_chart(temp, use_container_width=True)
st.pyplot(temp_pyplot)
