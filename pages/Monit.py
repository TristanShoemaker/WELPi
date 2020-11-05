import streamlit as st
import altair as alt
import time
from StreamPlot import StreamPlot, message


class Monit(StreamPlot):
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
        in_sensors = sensor_container.multiselect("Inside Sensors",
                                                  self.sensor_list,
                                                  self.in_default)
        # out_sensors = sensor_container.multiselect("Loop Sensors",
        #                                            stp.sensor_list,
        #                                            stp.out_default)
        # sensor_groups = [in_sensors, out_sensors]
        sensor_groups = [in_sensors]
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
                self.plotStatus().properties(
                    width=self.def_width,
                    height=self.def_height * self.stat_height_mod
                ),
                self.plotMainMonitor(self._sensor_groups[0]).properties(
                    width=self.def_width,
                    height=self.def_height * self.pwr_height_mod
                ),
                self.plotPowerStack(['solar_w', 'power_tot',
                                     'house_ops_w'],
                                    axis_label="Electrical Power / kW"
                                    ).properties(
                    width=self.def_width,
                    height=self.def_height * self.pwr_height_mod
                ),
                # self.plotMainMonitor(sensor_groups[1]).properties(
                #     width=self.def_width,
                #     height=self.def_height * self.pwr_height_mod
                # ),
                self.plotRollMean(['COP', 'well_COP']).properties(
                    width=self.def_width,
                    height=self.def_height * self.cop_height_mod
                ),
                self.plotRollMean(['deg_day_eff'],
                                  axis_label="House Efficiency / W/°C",
                                  bottomPlot=True
                                  ).properties(
                    width=self.def_width,
                    height=self.def_height * self.cop_height_mod,
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
