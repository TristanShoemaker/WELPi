import subprocess

"""
rtl command:

rtl_433 -R 40 -R 55 -R 74 -R 163 -C si -F json

[-R <device> | help] Enable only the specified device decoding protocol (can be
    used multiple times)
    [40]  Acurite 592TXR Temp/Humidity, 5n1 Weather Station, 6045 Lightning, 3N1,
        Atlas
    [55]  Acurite 606TX Temperature Sensor
    [74]  Acurite 00275rm,00276rm Temp/Humidity with optional probe
    [163]  Acurite 590TX Temperature with optional Humidity

[-C native | si | customary] Convert units in decoded output.

[-F kv | json | csv | mqtt | influx | syslog | null | help] Produce decoded
    output in given format.
"""
