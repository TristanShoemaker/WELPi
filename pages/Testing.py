import streamlit as st
import altair as alt
import time
from StreamPlot import StreamPlot
from log_message import message


class Testing(StreamPlot):
    _sensor_groups = None
    plots = None

    def __init__(self,
                 resample_N,
                 date_range,
                 onlyPlots=False,
                 sensor_container=None):
        super().__init__(resample_N)

        display_log = st.sidebar.checkbox("Display Log")
        if display_log:
            self.makeDebugTbl()

        self.makeWEL(date_range)

        if onlyPlots:
            self.plots = self._plots()
        else:
            self._selects(sensor_container)
            self.plots = self._plots()

    def _selects(self,
                 sensor_container):
        sensors = sensor_container.multiselect("Inside Sensors",
                                               self.sensor_list,
                                               self.in_default)
        sensor_groups = [sensors]
        for sensor_group in sensor_groups:
            while len(sensor_group) < 1:
                st.warning('Please select at least one sensor per plot')
                st.stop()
        self._sensor_groups = sensor_groups
        return sensor_groups

    def _plots(self):
        tic = time.time()
        if self._sensor_groups is None:
            self._sensor_groups = [self.in_default]
        with st.spinner('Generating Plots'):
            plot = alt.vconcat(
                self.plotNonTime('T_diff', 'T_diff_eff').properties(
                                 width=self.def_width),
                self.plotNonTime('solar_w', 'geo_tot_w').properties(
                                 width=self.def_width)
            )
        plot = plot.configure_axis(
            labelFontSize=self.label_font_size,
            titleFontSize=self.title_font_size,
            titlePadding=41,
            domain=False
        ).configure_legend(
            labelFontSize=self.label_font_size,
            titleFontSize=self.title_font_size
        ).configure_view(
            cornerRadius=2
        )

        message([F"{'Altair plot gen:': <20}", F"{time.time() - tic:.2f} s"],
                tbl=self.mssg_tbl, mssgType='TIMING')

        return plot
