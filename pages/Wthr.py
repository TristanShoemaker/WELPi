import streamlit as st
import altair as alt
import time
from StreamPlot import StreamPlot, message


class Wthr(StreamPlot):
    _sensor_groups = None
    plots = None

    def __init__(self,
                 resample_N,
                 date_range,
                 onlyPlots=False,
                 sensor_container=None):
        super().__init__(resample_N)
        self.makeWEL(date_range)
        if onlyPlots:
            self.plots = self._plots()
        else:
            self._selects(sensor_container)
            self.plots = self._plots()

    def _selects(self,
                 sensor_container):
        wthr_sensors = sensor_container.multiselect("Weather Temp Sensors",
                                                    self.sensor_list,
                                                    self.wthr_default)
        humid_sensors = sensor_container.multiselect("Humidity Sensors",
                                                     self.sensor_list,
                                                     self.humid_default)
        sensor_groups = [wthr_sensors, humid_sensors]
        for sensor_group in sensor_groups:
            while len(sensor_group) < 1:
                st.warning('Please select at least one sensor per plot')
                st.stop()
        self._sensor_groups = sensor_groups
        return sensor_groups

    def _plots(self):
        tic = time.time()
        if self._sensor_groups is None:
            self._sensor_groups = [self.wthr_default, self.humid_default]
        with st.spinner('Generating Plots'):
            plot = alt.vconcat(
                self.plotStatus().properties(
                    width=self.def_width,
                    height=self.def_height * self.stat_height_mod
                ),
                self.plotMainMonitor(self._sensor_groups[0]).properties(
                    width=self.def_width,
                    height=self.def_height * self.pwr_height_mod
                ),
                self.plotMainMonitor(self._sensor_groups[1],
                                     axis_label="Humidity / %",
                                     ).properties(
                    width=self.def_width,
                    height=self.def_height * self.pwr_height_mod
                ),
                self.plotMainMonitor('weather_station_R',
                                     axis_label='Rain Accumulation / mm',
                                     ).properties(
                    width=self.def_width,
                    height=self.def_height * self.cop_height_mod
                ),
                self.plotMainMonitor('weather_station_W',
                                     axis_label='Wind Speed / km/h',
                                     height_mod=self.cop_height_mod,
                                     bottomPlot=True
                                     ).properties(
                    width=self.def_width,
                    height=self.def_height * self.cop_height_mod
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
                tbl=self.mssg_tbl)

        return plot
