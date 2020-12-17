import streamlit as st
import altair as alt
import time
from StreamPlot import StreamPlot
from log_message import message


class PandW(StreamPlot):
    water_default = ['desup_T', 'desup_return_T', 'house_hot_T', 'tank_h2o_T',
                     'buderus_h2o_T']
    # pwr_default = ['TAH_W', 'HP_W', 'power_tot']
    work_default = ['liqu_refrig_T', 'gas_refrig_T', 'loop_in_T', 'loop_out_T',
                    'TAH_in_T', 'TAH_out_T']
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
        work_sensors = sensor_container.multiselect("Geo Working Sensors",
                                                    self.sensor_list,
                                                    self.work_default)
        water_sensors = sensor_container.multiselect("Water Sensors",
                                                     self.sensor_list,
                                                     self.water_default)
        sensor_groups = [work_sensors, water_sensors]
        for sensor_group in sensor_groups:
            while len(sensor_group) < 1:
                st.warning('Please select at least one sensor per plot')
                st.stop()
        self._sensor_groups = sensor_groups
        return sensor_groups

    def _plots(self):
        tic = time.time()
        if self._sensor_groups is None:
            self._sensor_groups = [self.work_default, self.water_default]
        with st.spinner('Generating Plots'):
            plot = alt.vconcat(
                self.plotStatus().properties(
                    width=self.def_width,
                    height=self.def_height * self.stat_height_mod
                ),
                self.plotMainMonitor(self._sensor_groups[0]).properties(
                    width=self.def_width,
                    height=self.def_height
                ),
                self.plotMainMonitor('TAH_fpm',
                                     axis_label="Wind Speed / m/s",
                                     height_mod=self.pwr_height_mod
                                     ).properties(
                    width=self.def_width,
                    height=self.def_height * self.stat_height_mod
                ),
                self.plotMainMonitor(self._sensor_groups[1],
                                     bottomPlot=True).properties(
                    width=self.def_width,
                    height=self.def_height
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
