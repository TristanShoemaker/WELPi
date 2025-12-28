import pandas as pd
import subprocess
import json
import time
from log_message import message
from async_func import SourceConnects

"""
rtl command:

[-R <device> | help] Enable only the specified device decoding protocol (can be
    used multiple times)
    [40]  Acurite 592TXR Temp/Humidity, 5n1 Weather Station, 6045 Lightning,
        3N1, Atlas
    [55]  Acurite 606TX Temperature Sensor
    [74]  Acurite 00275rm,00276rm Temp/Humidity with optional probe

[-C native | si | customary] Convert units in decoded output.

[-F kv | json | csv | mqtt | influx | syslog | null | help] Produce decoded
    output in given format.
"""
rtl_cmd = "rtl_433 -R 40 -R 55 -R 74 -C si -F json".split()


id_to_name = {'2669': {'name': 'D_room',
                       'sensors': ['temperature_C', 'humidity']},
              '13097': {'name': 'V_room',
                        'sensors': ['temperature_C', 'humidity']},
              '7177': {'name': 'T_room',
                       'sensors': ['temperature_C', 'humidity']},
              '13945': {'name': 'fireplace',
                        'sensors': ['temperature_C', 'humidity']},
              '450_5': {'name': 'weather_station',
                        'sensors': ['wind_avg_km_h', 'temperature_C',
                                    'humidity']},
              '450_6': {'name': 'weather_station',
                        'sensors': ['wind_avg_km_h', 'wind_dir_deg',
                                    'rain_mm']},
              '450_7': {'name': 'weather_station',
                        'sensors': ['wind_avg_km_h', 'uv', 'lux']},
              '3838': {'name': 'basement',
                       'sensors': ['temperature_C', 'humidity']},
              '3634': {'name': 'outside_shade',
                       'sensors': ['temperature_C', 'humidity']},
              '7285': {'name': 'attic',
                       'sensors': ['temperature_C', 'humidity']},
              '4856': {'name': 'barn',
                       'sensors': ['temperature_C', 'humidity']},
              '3202': {'name': 'barn_sump',
                       'sensors': ['temperature_C', 'temperature_1_C',
                                   'humidity']},
              }

quantity_short = {'temperature_C': 'T',
                  'temperature_1_C': '2_T',
                  'humidity': 'H',
                  'wind_avg_km_h': 'W',
                  'wind_dir_deg': 'A',
                  'rain_mm': 'R',
                  'uv': 'UV',
                  'lux': 'LUX'}


def processLine(line):
    line = json.loads(line)
    packet = {}
    try:
        id = F"{line['id']}_{line['message_type']}"
    except KeyError:
        id = str(line['id'])

    try:
        for quantity in id_to_name[id]['sensors']:
            sensor_name = (F"{id_to_name[id]['name']}_"
                           F"{quantity_short[quantity]}")
            packet[sensor_name] = float(line[quantity])
        return packet
    except KeyError:
        message([F"Unknown Sensor ID: {id}", F"\n{line}"], mssgType='WARNING')


def accumulate(p):
    signals = pd.DataFrame()
    tic = time.time()
    for line in p.stdout:
        packet = processLine(line)
        signals = signals.append(packet, ignore_index=True)
        if time.time() - tic >= 29:
            break
    message("Found Signals:", mssgType='HEADER')
    [print(F"{22 * ' '}{idx: <25}{value}", flush=True)
     for idx, value in signals.count().items()]
    signals.drop_duplicates(inplace=True)
    return signals.mean().to_dict()


def main():
    message("\n    Restarted ...", mssgType='ADMIN')
    mc = SourceConnects.connectMemCache()
    time.sleep(5)
    with subprocess.Popen(rtl_cmd, stdout=subprocess.PIPE, text=True) as p:
        while True:
            signals = accumulate(p)
            mc_result = mc.set("rtl", signals)
            if not mc_result:
                message("RTL failed to cache", mssgType='ERROR')
            else:
                message("Succesful cache", mssgType='SUCCESS')


if __name__ == "__main__":
    main()
