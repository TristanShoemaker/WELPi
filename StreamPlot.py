import streamlit as st
import altair as alt
import pandas as pd
import numpy as np
import time
from WELData import WELData, mongoConnect
from log_message import message


@st.cache(hash_funcs={"pymongo.database.Database": id})
def _cachedMongoConnect():
    return mongoConnect()


# @st.cache()
# def _cachedMemCache():
#     message("MemCache Connected")
#     return libmc.Client(['localhost'])


@st.cache(allow_output_mutation=True, show_spinner=False)
def _cachedWELData(date_range,
                   data_source='Pi'):
    return WELData(timerange=date_range,
                   data_source=data_source,
                   dl_db_path="/home/ubuntu/WEL/log_db/",
                   mongo_connection=_cachedMongoConnect())


def _createNearestTime():
    return alt.selection(type='single',
                         nearest=True,
                         on='mouseover',
                         fields=['dateandtime'],
                         empty='none')


# def _createResize():
#     return alt.selection(type='interval',
#                          encodings=['x'])


class StreamPlot():
    def_width = 'container'
    def_height = 320
    def_spacing = 2
    stat_height_mod = 0.4
    cop_height_mod = 0.3
    pwr_height_mod = 0.75
    mark_text_font_size = 14
    label_font_size = 13
    title_font_size = 12
    sensor_list = ['TAH_W', 'HP_W',  'TAH_fpm', 'liqu_refrig_T',
                   'gas_refrig_T', 'loop_in_T', 'loop_out_T', 'outside_T',
                   'power_tot', 'living_T', 'desup_T', 'house_hot_T',
                   'TAH_in_T', 'aux_heat_b', 'heat_1_b', 'heat_2_b',
                   'rev_valve_b', 'TAH_fan_b', 'humid_b', 'zone_1_b',
                   'zone_2_b', 'TAH_out_T', 'desup_return_T', 'buderus_h2o_T',
                   'wood_fire_T', 'tank_h2o_T', 'trist_T', 'base_T',
                   'daylight', 'T_diff', 'COP', 'well_W', 'well_COP',
                   'V_room_H', 'V_room_T', 'weather_station_H',
                   'weather_station_T', 'weather_station_W', 'fireplace_H',
                   'fireplace_T', 'D_room_H', 'D_room_T', 'T_room_H',
                   'T_room_T', 'attic_H', 'attic_T', 'basement_H',
                   'basement_T', 'outside_shade_H', 'outside_shade_T',
                   'weather_station_A', 'weather_station_R',  'barn_T',
                   'barn_H', 'deg_day_eff', 'solar_w', 'house_w',
                   'dehumidifier_w', 'house_ops_w', 'power_tot_pi',
                   'furnace_w', 'barn_sump_T', 'barn_sump_2_T', 'barn_sump_H'
                   'TES_sense_w']
    resample_N = None
    dat = None
    dat_resample = None
    nearestTime = None
    resize = None
    mssg_tbl = None

    def __init__(self,
                 resample_N=300):
        self.nearestTime = _createNearestTime()
        self.resample_N = resample_N
        # self.resize = _createResize()

    def makeDebugTbl(self):
        st.sidebar.subheader("Log:")
        self.mssg_tbl = st.sidebar.table()

    def makeWEL(self,
                date_range,
                force_refresh=False):
        tic = time.time()
        if not force_refresh:
            dat = _cachedWELData(date_range)
        else:
            dat = WELData(timerange=date_range,
                          mongo_connection=_cachedMongoConnect())
        resample_T = (dat.timerange[1] - dat.timerange[0]) / self.resample_N
        self.dat_resample = dat.data.resample(resample_T).mean()
        self.dat = dat
        message([F"{'WEL Data init:': <20}", F"{time.time() - tic:.2f} s"],
                tbl=self.mssg_tbl, mssgType='TIMING')

    def _getDataSubset(self,
                       vars,
                       id_vars='dateandtime',
                       resample=True):
        if resample:
            source = self.dat_resample
        else:
            source = self.dat.data
        source = source.reset_index()
        try:
            source = source.melt(id_vars=id_vars,
                                 value_vars=vars,
                                 var_name='label')
        except KeyError:
            goodKeys = []
            badKeys = []
            for key in vars:
                if key in source:
                    goodKeys.append(key)
                else:
                    badKeys.append(key)
            message(["Key(s) not found in db:", F"{badKeys}"],
                    tbl=self.mssg_tbl, mssgType='WARNING')
            source = source.melt(id_vars=id_vars,
                                 value_vars=goodKeys,
                                 var_name='label')

        return source

    def _createRules(self,
                     source,
                     tooltip=True,
                     timetext=False,
                     timetexttop=False,
                     timetextheightmod=1,
                     field='value:Q'):
        selectors = alt.Chart(source.data).mark_point(opacity=0).encode(
            x='dateandtime:T',
        ).add_selection(
            self.nearestTime
        )

        rules = alt.Chart(source.data).mark_rule().encode(
            x='dateandtime:T',
            color=alt.condition('isValid(datum.value)',
                                alt.ColorValue('gray'),
                                alt.ColorValue('red'))
        ).transform_filter(
            self.nearestTime
        )

        if timetext:
            if timetexttop:
                flip = -1
            else:
                flip = 1
            time_text_dy = flip * (self.def_height
                                   * timetextheightmod / 2 + 11)
            time_text = rules.mark_text(align='center',
                                        dx=0,
                                        dy=time_text_dy,
                                        fontSize=self.mark_text_font_size + 1
                                        ).encode(
                text=alt.condition(self.nearestTime,
                                   'dateandtime:T',
                                   alt.value(' '),
                                   format='%b %-d, %H:%M')
            )
            rules = rules + time_text

        if tooltip:
            points = source.mark_point(size=40, filled=True).encode(
                opacity=alt.condition(self.nearestTime,
                                      alt.value(0.8),
                                      alt.value(0))
            )
            text = source.mark_text(
                align='left',
                dx=5, dy=-10,
                fontSize=self.mark_text_font_size
            ).encode(
                text=alt.condition(self.nearestTime,
                                   field,
                                   alt.value(' '),
                                   format='.1f')
            )

            return selectors + rules + points + text

        return selectors + rules

    def _createLatestText(self,
                          lines,
                          field):
        # print(dir(lines))
        opacity = 0.7
        latest_text = lines.mark_text(
            align='left',
            dx=30,
            fontSize=self.mark_text_font_size,
            opacity=opacity
        ).transform_window(
            rank='rank()',
            sort=[alt.SortField('dateandtime', order='descending')]
        ).encode(
            text=alt.condition(alt.datum.rank == 1,
                               field,
                               alt.value(' '),
                               format='.1f')
        )

        latest_text_tick = lines.mark_tick(
            strokeDash=[1, 1],
            xOffset=15,
            size=15,
            thickness=2
        ).transform_window(
            rank='rank()',
            sort=[alt.SortField('dateandtime', order='descending')]
        ).encode(
            opacity=alt.condition(alt.datum.rank == 1,
                                  alt.value(opacity),
                                  alt.value(0))
        )

        return alt.layer(latest_text, latest_text_tick)

    def _plotNightAlt(self,
                      height_mod=1):
        source = self._getDataSubset('daylight')
        area = alt.Chart(source).mark_bar(
            fill='purple',
            width=800 / self.resample_N,
            clip=True,
            height=self.def_height * height_mod
        ).encode(
            x='dateandtime:T',
            opacity=alt.condition(alt.datum.value < 1,
                                  alt.value(0.15),
                                  alt.value(0))
        )

        return area

    def plotMainMonitor(self,
                        vars,
                        axis_label="Temperature / °C",
                        height_mod=1,
                        bottomPlot=False):
        source = self._getDataSubset(vars)

        lines = alt.Chart(source).mark_line(
            interpolate='basis',
            clip=True
        ).encode(
            x=alt.X('dateandtime:T',
                    # scale=alt.Scale(domain=self.resize),
                    axis=alt.Axis(title=None,
                                  labels=False,
                                  grid=False,
                                  ticks=False,
                                  domainWidth=0)),
            y=alt.Y('value:Q',
                    scale=alt.Scale(zero=False),
                    axis=alt.Axis(title=axis_label,
                                  orient='right',
                                  grid=True,
                                  tickMinStep=1)),
            color=alt.Color('new_label:N',
                            legend=alt.Legend(title='Sensors',
                                              orient='left',
                                              offset=5))
        ).transform_calculate(
            new_label=alt.expr.slice(alt.datum.label, 0, -2)
        )

        rule = self._createRules(lines, timetext=bottomPlot,
                                 timetextheightmod=height_mod)

        latest_text = self._createLatestText(lines, 'value:Q')

        plot = alt.layer(
            self._plotNightAlt(), lines, rule, latest_text
        )

        return plot

    def plotStatus(self):
        status_list = ['TAH_fan_b', 'heat_1_b', 'heat_2_b', 'zone_1_b',
                       'zone_2_b', 'humid_b', 'rev_valve_b', 'aux_heat_b']
        source = self._getDataSubset(status_list)
        source.value = source.value % 2

        chunks = alt.Chart(source).mark_bar(
            width=800 / self.resample_N,
            clip=True
        ).encode(
            x=alt.X('dateandtime:T',
                    # scale=alt.Scale(domain=self.resize),
                    axis=alt.Axis(title=None,
                                  labels=False,
                                  grid=False,
                                  ticks=False,
                                  orient='top',
                                  offset=16)),
            y=alt.Y('new_label:N',
                    title=None,
                    axis=alt.Axis(orient='right',
                                  grid=False),
                    sort=status_list),
            opacity=alt.condition(alt.datum.value > 0,
                                  alt.value(1),
                                  alt.value(0)),
            color=alt.Color('new_label:N', legend=None)
        ).transform_calculate(
            new_label=alt.expr.slice(alt.datum.label, 0, -2)
        )

        out_source = self._getDataSubset(['outside_T'])
        outside = alt.Chart(out_source).mark_line(
            interpolate='basis',
            opacity=0.6,
            strokeDash=[3, 2]
        ).encode(
            x='dateandtime:T',
            y=alt.Y('value:Q', title='Outside / °C',
                    axis=alt.Axis(orient='left', grid=False),
                    scale=alt.Scale(zero=False)),
            color=alt.value('grey')
        )

        rule = self._createRules(outside, timetext=True, timetexttop=True,
                                 timetextheightmod=self.stat_height_mod)

        plot = alt.layer(
            self._plotNightAlt(), chunks, outside, rule
        ).resolve_scale(y='independent')

        return plot

    def plotRollMean(self,
                     vars,
                     axis_label="COP Rolling Mean",
                     height_mod=1,
                     bottomPlot=False):
        source = self._getDataSubset(vars)

        rolling_frame = (2 * self.resample_N / ((self.dat.timerange[1]
                         - self.dat.timerange[0]).total_seconds() / 3600))
        rolling_frame = int(np.clip(rolling_frame, self.resample_N / 48,
                                    self.resample_N / 2))
        rolling_source = pd.DataFrame({'rolling_limit': source.dateandtime
                                       .iloc[-rolling_frame]}, index=[0])
        lines = alt.Chart(source).transform_window(
            rollmean='mean(value)',
            frame=[-rolling_frame, 0]
        ).mark_line(
            interpolate='basis',
            strokeWidth=2
        ).encode(
            x=alt.X('dateandtime:T',
                    # scale=alt.Scale(domain=self.resize),
                    axis=alt.Axis(grid=False,
                                  labels=False,
                                  ticks=False),
                    title=None),
            y=alt.Y('rollmean:Q',
                    scale=alt.Scale(zero=False),
                    axis=alt.Axis(orient='right',
                                  grid=True),
                    title=axis_label),
            color=alt.Color('label', legend=alt.Legend(title='Efficiencies',
                                                       orient='left',
                                                       offset=5))
        )

        raw_lines = alt.Chart(source).mark_line(
            interpolate='basis',
            strokeWidth=2,
            strokeDash=[1, 2],
            opacity=0.8,
            clip=True
        ).encode(
            x=alt.X('dateandtime:T'),
            y=alt.Y('value:Q'),
            color='label'
        )

        window_line = alt.Chart(rolling_source).mark_rule().encode(
            x='rolling_limit:T',
            color=alt.ColorValue('purple')
        )

        rule = self._createRules(lines, field='rollmean:Q',
                                 timetext=bottomPlot,
                                 timetextheightmod=height_mod)

        latest_text = self._createLatestText(lines, 'rollmean:Q')

        plot = alt.layer(
            self._plotNightAlt(), lines, raw_lines, rule, latest_text,
            window_line
        )

        return plot

    def plotPowerStack(self,
                       vars,
                       axis_label="Power / kW",
                       height_mod=1,
                       bottomPlot=False):
        source = self._getDataSubset(vars)
        try:
            source['value'] = source['value'] / 1000
            solar_mask = source['label'] == 'solar_w'
            source.loc[solar_mask, 'value'] = -1 * source.loc[solar_mask,
                                                              'value']
        except KeyError:
            pass
        order = (str({label: idx for label, idx in enumerate(vars)})
                 + "[datum.label]")
        area = alt.Chart(source).mark_area(
            interpolate='basis',
            clip=True,
            opacity=0.9
        ).encode(
            x=alt.X('dateandtime:T',
                    # scale=alt.Scale(domain=self.resize),
                    axis=alt.Axis(title=None,
                                  labels=False,
                                  grid=False,
                                  ticks=False,
                                  domainWidth=0)),
            y=alt.Y('value:Q',
                    scale=alt.Scale(zero=False),
                    axis=alt.Axis(title=axis_label,
                                  orient='right',
                                  grid=True)),
            order="order:O",
            color=alt.Color('new_label:N',
                            legend=alt.Legend(title='Sensors',
                                              orient='left',
                                              offset=5),
                            sort=vars)
        ).transform_calculate(
            new_label=alt.expr.slice(alt.datum.label, 0, -2)
        ).transform_calculate(
            order=order
        )

        rule = self._createRules(area, tooltip=False, timetext=bottomPlot,
                                 timetextheightmod=height_mod)

        latest_text = self._createLatestText(area, 'value:Q')

        plot = alt.layer(
            self._plotNightAlt(), area, rule, latest_text
        )

        return plot

    def plotNonTime(self,
                    id_var,
                    vars):
        source = self._getDataSubset(vars, id_vars=[id_var, 'heat_1_b',
                                                    'heat_2_b'])
        # modes = self._getDataSubset(['heat_2_b'], id_vars=id_var)
        source['heat_1_b'] = source['heat_1_b'] % 2
        source['heat'] = (source['heat_2_b'] % 2 > 0) + 1
        source['heat'] = source['heat'].astype('str')
        source = source.dropna()

        rolling_frame = (1 * self.resample_N / ((self.dat.timerange[1]
                         - self.dat.timerange[0]).total_seconds() / 3600))
        rolling_frame = int(np.clip(rolling_frame, self.resample_N / 15,
                                    self.resample_N / 2))

        points = alt.Chart(source).transform_window(
            rollmean='mean(value)',
            frame=[-rolling_frame, 0]
        ).mark_point().encode(
            x=alt.X(F"{id_var}:Q", scale=alt.Scale(zero=False)),
            y=alt.Y("value:Q", axis=alt.Axis(title=vars)),
            color='heat:N'
        )

        # reg = points.transform_regression(
        #     F"{id_var}",
        #     "value",
        #     method='exp',
        # ).mark_line().encode(color=alt.ColorValue('black'))

        # reg_params = points.transform_regression(
        #     F"{id_var}",
        #     "value",
        #     method='exp',
        #     params=True
        # ).mark_text(align='left').encode(
        #     x=alt.value(20),  # pixels from left
        #     y=alt.value(20),  # pixels from top
        #     text=alt.Text('rSquared:N', format='.4f'),
        #     color=alt.ColorValue('black')
        # )

        return points
