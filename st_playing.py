import streamlit as st
import altair as alt
import numpy as np
import sys
sys.path.append('../WELPy/')
import WELServer

def makeWEL():
    return WELServer.WELData(download=True)

dat = makeWEL()

timerange = dat.time_from_args(arg_string=[])

st.title('Geothermal Monitoring')

sensors = st.multiselect(
             "Choose Sensors", list(dat.vars()),
             ['gas_refrig_T',
             'liqu_refrig_T',
             'loop_in_T',
             'loop_out_T',
             'outside_T',
             'living_T',
             'trist_T',
             'base_T'])

temp = dat.plotVarAlt(sensors, timerange=timerange).properties(width=600)
status = dat.plotStatusAlt(timerange=timerange).properties(width=600)
plot = temp & status

st.altair_chart(plot, use_container_width=True)

# power = dat.plotVarAlt(["COP.rolling('2H').mean()"], timerange=timerange)
# power_roll = power.transform_window(
#                 rolling_mean='mean(COP)',
#                 frame=[-120,120]
#                 ).mark_line(size=2).encode(
#                 x='dateandtime:T',
#                 y='rolling_mean:Q')
# st.altair_chart(power, use_container_width=True)
