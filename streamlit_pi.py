import streamlit as st
import altair as alt
import numpy as np
import pandas as pd
import sys
sys.path.append('../WELPy/')
from WELServer import WELData


# @st.cache(hash_funcs={WELData: id})
def makeWEL():
    return WELData(mongo_local=False,
                   timerange=['-t', '12'])

# Load data and melt into format for alt
dat = makeWEL()
dat.data = dat.data.reset_index()
# dat.data

nearestTime = alt.selection(type='single', nearest=True, on='mouseover',
                            fields=['dateandtime'], empty='none')

def plotMainMonitor(vars):
    status_list=['aux_heat_b', 'heat_1_b', 'heat_2_b', 'rev_valve_b',
                 'TAH_fan_b', 'zone_1_b', 'zone_2_b', 'humid_b']

    temp_source = dat.data.melt(id_vars='dateandtime',
                           value_vars=vars,
                           var_name='label')
    print(temp_source)
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

    temp_plot = alt.layer(
        lines, selectors, points, text, rules
    )

    stat_source = dat.data.melt(id_vars='dateandtime',
                                   value_vars=status_list,
                                   var_name='label')
    stat_source.value = stat_source.value % 2
    # stat_source
    status_plot = alt.Chart(stat_source).mark_bar(width=7).encode(
        alt.X('dateandtime:T'),
        alt.Y('label'),
        alt.FillOpacity('value:Q', legend=None),
        alt.Opacity('value:Q', legend=None)
    )


    plot = temp_plot & status_plot
    return plot


st.title('Geothermal Monitoring')

sensors = st.multiselect(" ",
                         list(dat.vars()),
                         ['TAH_in_T',
                          'TAH_out_T',
                          'loop_in_T',
                          'loop_out_T',
                          'outside_T',
                          'living_T',
                          'trist_T',
                          'base_T'])
temp = plotMainMonitor(sensors)

st.altair_chart(temp, use_container_width=True)
