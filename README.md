## House Sensor Monitoring System
[Starting](https://github.com/TristanShoemaker/WELPy) as a way to plot and
analyze data from a geothermal heating/cooling system collected by a
[WEL](http://www.welserver.com) server system, this project has expanded into a
home sensor data collection server running on a Raspberry Pi 4, with an EC2
hosted streamlit frontend.

### Data Server Side:
A MongoDB server runs on the pi for the database. Supervisor runs `async_func`,
which continuously and asynchronously collects data from different sensor
sources on a timed schedule. This includes temperature probe, energy usage,
and A/C logic level data from the WEL, as well as home and solar power from a
Sense current clamp monitor and also radio data. Supervisor additionally runs
`rtl_read`, which continuously collects temperature, weather and humidity data
which is broadcast from acurite nodes on 433.92 MHz ISM using an RTL-SDR. Data
is cleaned, formatted and stored in the database to be retrieved later.

### Frontend side:
`streamlit_pi` runs on AWS EC2, although it ran originally on the RPi as well.
A webpage is setup in python using streamlit. Data is plotted using through
`StreampPlot` using Altair, a vega-lite python wrapper. `Streamplot` pulls a 
timerange of data from the RPi Mongo server using `WELData`, which prepares 
data for plotting and calculates additional metrics for the house systems. 
Different views of the data are split into "pages" which define the plots and 
inputs available for each view, and are kept in the pages folder.

### Misc:
`log_messages` provides a standardized logging system across both servers by
adding timestamps and color and generally aids in debugging. 

`utilities/refill_mongo` was used to populate the mongo database with archive
data from the WEL system. 

`requirements.txt` allows for quickly installing the python dependencies with
`pip3 -r requirements.txt`.
