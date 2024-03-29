import streamlit as st
import altair as alt
import time
from StreamPlot import StreamPlot
from log_message import message


class Wthr(StreamPlot):
    wthr_default = ['outside_shade_T', 'outside_T', 'weather_station_T',
                    'barn_T']
    out_humid_default = ['weather_station_H', 'outside_shade_H']
    in_humid_default = ['D_room_H', 'V_room_H', 'T_room_H', 'fireplace_H']
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
        wthr_sensors = sensor_container.multiselect("Weather Temp Sensors",
                                                    self.sensor_list,
                                                    self.wthr_default)
        in_humid_sens = sensor_container.multiselect("Indoor Humidity Sensors",
                                                     self.sensor_list,
                                                     self.in_humid_default)
        sensor_groups = [wthr_sensors, in_humid_sens]
        for sensor_group in sensor_groups:
            while len(sensor_group) < 1:
                st.warning('Please select at least one sensor per plot')
                st.stop()
        self._sensor_groups = sensor_groups
        return sensor_groups

    def _plots(self):
        tic = time.time()
        if self._sensor_groups is None:
            self._sensor_groups = [self.wthr_default, self.in_humid_default]
        with st.spinner('Generating Plots'):
            plot = alt.vconcat(
                self.plotStatus().properties(
                    width=self.def_width,
                    height=self.def_height * self.stat_height_mod
                ),
                self.plotMainMonitor(self._sensor_groups[0]).properties(
                    width=self.def_width,
                    height=self.def_height * self.stat_height_mod
                ),
                self.plotMainMonitor(self.out_humid_default,
                                     axis_label="Outdoor Humidity / %",
                                     ).properties(
                    width=self.def_width,
                    height=self.def_height * self.stat_height_mod
                ),
                self.plotMainMonitor(self._sensor_groups[1],
                                     axis_label="Indoor Humidity / %",
                                     ).properties(
                    width=self.def_width,
                    height=self.def_height * self.stat_height_mod
                ),
                self.plotMainMonitor('rain_accum_R',
                                     axis_label='Rain / mm',
                                     ).properties(
                    width=self.def_width,
                    height=self.def_height * self.cop_height_mod
                ),
                self.plotMainMonitor('weather_station_W',
                                     axis_label='Wind / km/h',
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
                tbl=self.mssg_tbl, mssgType='TIMING')

        return [plot]
