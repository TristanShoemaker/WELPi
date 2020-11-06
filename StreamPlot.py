import streamlit as st
import altair as alt
import pandas as pd
import numpy as np
import time
from WELData import WELData, mongoConnect


def message(message_text,
            tbl=None):
    timestamp = F"{time.strftime('%Y-%m-%d %H:%M:%S')}"
    if tbl is not None:
        message = pd.DataFrame([{"Message": message_text[0],
                                 "Value": message_text[1]}])
        message.set_index("Message", inplace=True)
        tbl.add_rows(message)
    if type(message_text) is list:
        print(F"[{timestamp}] {message_text[0]} {message_text[1]}", flush=True)
    else:
        print(F"[{timestamp}] {message_text}", flush=True)


@st.cache(hash_funcs={"pymongo.database.Database": id})
def _cachedMongoConnect():
    message("Mongo Connected")
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


def _createResize():
    return alt.selection(type='interval',
                         encodings=['x'])


class StreamPlot():
    def_width = 'container'
    def_height = 310
    def_spacing = 2
    stat_height_mod = 0.4
    cop_height_mod = 0.4
    pwr_height_mod = 0.8
    mark_text_font_size = 13
    label_font_size = 12
    title_font_size = 11
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
                   'dehumidifier_w', 'house_ops_w', 'power_tot_pi']
    in_default = ['T_room_T', 'D_room_T', 'V_room_T', 'fireplace_T', 'attic_T']
    out_default = ['TAH_in_T', 'TAH_out_T', 'loop_in_T', 'loop_out_T',
                   'outside_T', 'barn_T', 'basement_T']
    water_default = ['desup_T', 'desup_return_T', 'house_hot_T', 'tank_h2o_T',
                     'buderus_h2o_T']
    pwr_default = ['TAH_W', 'HP_W', 'power_tot']
    wthr_default = ['outside_shade_T', 'outside_T', 'weather_station_T']
    humid_default = ['weather_station_H', 'outside_shade_H', 'basement_H',
                     'fireplace_H']
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
                tbl=self.mssg_tbl)

    def _getDataSubset(self,
                       vars,
                       resample=True):
        if resample:
            source = self.dat_resample
        else:
            source = self.dat.data
        source = source.reset_index()
        try:
            source = source.melt(id_vars='dateandtime',
                                 value_vars=vars,
                                 var_name='label')
        except KeyError:
            message(["Key(s) not found in db:", F"{vars}"],
                    tbl=self.mssg_tbl)
            source = pd.DataFrame()
        return source

    def _createRules(self,
                     source):
        selectors = alt.Chart(source).mark_point(opacity=0).encode(
            x='dateandtime:T',
        ).add_selection(
            self.nearestTime
        )
        rules = alt.Chart(source).mark_rule().encode(
            x='dateandtime:T',
            color=alt.condition('isValid(datum.value)',
                                alt.ColorValue('gray'),
                                alt.ColorValue('red'))
        ).transform_filter(
            self.nearestTime
        )

        return [selectors, rules]

    def _createTimeText(self,
                        rules,
                        height_mod,
                        top=False):
        if top:
            flip = -1
        else:
            flip = 1
        time_text_dy = flip * (self.def_height * height_mod / 2 + 11)
        time_text = rules.mark_text(align='center',
                                    dx=0,
                                    dy=time_text_dy,
                                    fontSize=self.mark_text_font_size
                                    ).encode(
            text=alt.condition(self.nearestTime,
                               'dateandtime:T',
                               alt.value(' '),
                               format='%b %-d, %H:%M'),
            color=alt.ColorValue('black')
        )

        return time_text

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
            fill='black',
            width=800 / self.resample_N,
            clip=True,
            height=self.def_height * height_mod
        ).encode(
            x='dateandtime:T',
            opacity=alt.condition(alt.datum.value < 1,
                                  alt.value(0.06),
                                  alt.value(0))
        )

        return area

    def plotMainMonitor(self,
                        vars,
                        axis_label="Temperature / °C",
                        height_mod=1,
                        bottomPlot=False):
        source = self._getDataSubset(vars)

        label_unit = source['label'][0][-2:]
        if label_unit == '_w' or label_unit == '_W':
            source['value'] = source['value'] / 1000

        lines = alt.Chart(source).mark_line(
            interpolate='cardinal',
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
                                              offset=5)),
            strokeWidth=alt.condition(alt.datum.label == 'outside_T',
                                      alt.value(3),
                                      alt.value(2)),
        ).transform_calculate(
            new_label=alt.expr.slice(alt.datum.label, 0, -2)
        )

        points = lines.mark_point(size=40, filled=True).encode(
            opacity=alt.condition(self.nearestTime,
                                  alt.value(0.8),
                                  alt.value(0))
        )

        text = lines.mark_text(
            align='left',
            dx=5, dy=-5,
            fontSize=self.label_font_size
        ).encode(
            text=alt.condition(self.nearestTime,
                               'value:Q',
                               alt.value(' '),
                               format='.1f')
        )

        selectors, rules = self._createRules(source)

        latest_text = self._createLatestText(lines, 'value:Q')

        plot = alt.layer(
            self._plotNightAlt(), lines, points, text, selectors, rules,
            latest_text
        )

        if bottomPlot:
            time_text = self._createTimeText(rules, height_mod=height_mod)
            plot = alt.layer(plot, time_text)

        return plot

    def plotStatus(self):
        status_list = ['TAH_fan_b', 'heat_1_b', 'heat_2_b', 'zone_1_b',
                       'zone_2_b', 'humid_b', 'rev_valve_b', 'aux_heat_b']
        source = self._getDataSubset(status_list, resample=True)
        source.value = source.value % 2
        # source = source.loc[source.value != 0]

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

        selectors, rules = self._createRules(source)

        time_text = self._createTimeText(rules, self.stat_height_mod, top=True)

        plot = alt.layer(
            self._plotNightAlt(), chunks, selectors, rules, time_text
        )

        return plot

    def plotRollMean(self,
                     vars,
                     axis_label="COP Rolling Mean",
                     bottomPlot=False):
        source = self._getDataSubset(vars)

        rolling_frame = (3 * self.resample_N / ((self.dat.timerange[1]
                         - self.dat.timerange[0]).total_seconds() / 3600))
        rolling_frame = int(np.clip(rolling_frame, self.resample_N / 15,
                                    self.resample_N / 2))
        lines = alt.Chart(source).transform_window(
            rollmean='mean(value)',
            frame=[-rolling_frame, 0]
        ).mark_line(
            interpolate='cardinal',
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
            interpolate='cardinal',
            strokeWidth=2,
            strokeDash=[1, 2],
            opacity=0.8,
            clip=True
        ).encode(
            x=alt.X('dateandtime:T'),
            y=alt.Y('value:Q'),
            color='label'
        )

        points = lines.mark_point(size=40, filled=True).encode(
            opacity=alt.condition(self.nearestTime,
                                  alt.value(0.8),
                                  alt.value(0))
        )

        text = lines.mark_text(align='left', dx=5, dy=-5).encode(
            text=alt.condition(self.nearestTime,
                               'rollmean:Q',
                               alt.value(' '),
                               format='.1f')
        )

        selectors, rules = self._createRules(source)

        latest_text = self._createLatestText(lines, 'rollmean:Q')

        plot = alt.layer(
            self._plotNightAlt(), lines, raw_lines, points, text, selectors,
            rules, latest_text
        )

        if bottomPlot:
            time_text = self._createTimeText(rules, self.cop_height_mod)
            plot = alt.layer(plot, time_text)

        return plot

    def plotPowerStack(self,
                       vars,
                       axis_label="Power / kW",
                       height_mod=1,
                       bottomPlot=False):
        source = self._getDataSubset(vars)

        source['value'] = source['value'] / 1000
        solar_mask = source['label'] == 'solar_w'
        source.loc[solar_mask, 'value'] = -1 * source.loc[solar_mask, 'value']

        area = alt.Chart(source).mark_area(
            interpolate='cardinal',
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
                                              offset=5))
        ).transform_calculate(
            new_label=alt.expr.slice(alt.datum.label, 0, -2)
        ).transform_calculate(
            order=(str({label: idx for label, idx in enumerate(vars)})
                   + "[datum.label]")
        )

        points = area.mark_point(size=40, filled=True).encode(
            opacity=alt.condition(self.nearestTime,
                                  alt.value(0.8),
                                  alt.value(0))
        )

        text = area.mark_text(
            align='left',
            dx=5, dy=-5,
            fontSize=self.label_font_size
        ).encode(
            text=alt.condition(self.nearestTime,
                               'value:Q',
                               alt.value(' '),
                               format='.1f')
        )

        selectors, rules = self._createRules(source)

        latest_text = self._createLatestText(area, 'value:Q')

        plot = alt.layer(
            self._plotNightAlt(), area, points, text, selectors, rules,
            latest_text
        )

        if bottomPlot:
            time_text = self._createTimeText(rules, height_mod=height_mod)
            plot = alt.layer(plot, time_text)

        return plot
