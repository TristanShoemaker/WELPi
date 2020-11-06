import streamlit as st
import altair as alt
import time
from StreamPlot import StreamPlot
from log_message import message


class PandW(StreamPlot):
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
        pwr_sensors = sensor_container.multiselect("Power Sensors",
                                                   self.sensor_list,
                                                   self.pwr_default)
        water_sensors = sensor_container.multiselect("Water Sensors",
                                                     self.sensor_list,
                                                     self.water_default)
        sensor_groups = [pwr_sensors, water_sensors]
        for sensor_group in sensor_groups:
            while len(sensor_group) < 1:
                st.warning('Please select at least one sensor per plot')
                st.stop()
        self._sensor_groups = sensor_groups
        return sensor_groups

    def _plots(self):
        tic = time.time()
        if self._sensor_groups is None:
            self._sensor_groups = [self.pwr_default, self.water_default]
        with st.spinner('Generating Plots'):
            plot = alt.vconcat(
                self.plotStatus().properties(
                    width=self.def_width,
                    height=self.def_height * self.stat_height_mod
                ),
                self.plotPowerStack(['solar_w', 'power_tot',
                                     'house_ops_w'],
                                    axis_label="Power / kW").properties(
                    width=self.def_width,
                    height=self.def_height
                ),
                self.plotMainMonitor(self._sensor_groups[0],
                                     axis_label="Power / kW",
                                     ).properties(
                    width=self.def_width,
                    height=self.def_height * self.stat_height_mod
                ),
                self.plotMainMonitor(self._sensor_groups[1]).properties(
                    width=self.def_width,
                    height=self.def_height * self.pwr_height_mod
                ),
                self.plotMainMonitor('TAH_fpm',
                                     axis_label="Wind Speed / m/s",
                                     height_mod=self.pwr_height_mod,
                                     bottomPlot=True
                                     ).properties(
                    width=self.def_width,
                    height=self.def_height * self.stat_height_mod
                ),
                spacing=self.def_spacing
            ).resolve_scale(
                y='independent',
                color='independent'
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
