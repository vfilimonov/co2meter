# CO2meter

CO2meter is a Python interface to the USB CO2 monitor with monitoring and logging tools, flask web-server for visualization and Apple HomeKit compatibility.


# Installation


### Prerequisites

##### OSX

Necessary libraries (`libusb`, `hidapi`) could be installed via [Homebrew](http://brew.sh/):

	brew install libusb hidapi

##### Linux (including Raspberry Pi)

`libusb` could be retrieved via `apt-get`

	sudo apt-get install libusb-1.0-0-dev libudev-dev

If the script is not intended to be started under `root`, proper permissions for the device should be set. Put the following two lines into a file `/etc/udev/rules.d/98-co2mon.rules`:

	KERNEL=="hidraw*", ATTRS{idVendor}=="04d9", ATTRS{idProduct}=="a052", GROUP="plugdev", MODE="0666"
	SUBSYSTEM=="usb", ATTRS{idVendor}=="04d9", ATTRS{idProduct}=="a052", GROUP="plugdev", MODE="0666"

and run `sudo udevadm control --reload-rules && udevadm trigger`.

###### Windows
For installation of `hidapi` package [Microsoft Visual C++ Compiler for Python](https://www.microsoft.com/en-us/download/details.aspx?id=44266) is required.

**Note**: Some users have reported, that for certain models of CO2 meter devices under Windows a special software should be running in order for the `CO2Meter` to work (see [issue #16](https://github.com/vfilimonov/co2meter/issues/16)). More speficically, `ZG.exe` downloaded from "ZyAura" website (the link is [in the comment](https://github.com/vfilimonov/co2meter/issues/16#issuecomment-871743048)). 


### Installation of python package

Then installation of `co2meter` could be done via the `pip` utility:

	pip install hidapi co2meter

Optionally, if [pandas package](http://pandas.pydata.org/) is available then the data will be retrieved as pandas.DataFrames rather than list of tuples.

**Note 1**: there could be a potential name conflict with the library `hid`. In this case the import of the module in python will fail with the error `AttributeError: 'module' object has no attribute 'windll'` (see [here](https://github.com/vfilimonov/co2meter/issues/1)). If this happens, please try uninstalling `hid` module (executing `pip uninstall hid` in the console).

**Note 2**: there were reports on issues with installation on Raspbian Stretch Lite (#5), where build failed with and `error code 1` in `gcc`. Most likely the reason is in missing dependencies. Possible solution is [described in the comment](https://github.com/vfilimonov/co2meter/issues/5#issuecomment-407378515).

### Optional: flask web-server

In order to be able to start monitoring web-server a few extra packages are needed. Basic web-server will allow reading the current value in browser, downloading data in CSV/JSON and monitoring the status with a simple dashboard. Dependencies could be installed via pip:

	pip install -U flask pandas


### Optional: Apple HomeKit compatibility

In order to be able to add co2monitor to Apple Home application (iPhone/iPad) HAP-python of version 1.1.5 is required (it was reported that the `co2meter` [is incompatible with the newer version](https://github.com/vfilimonov/co2meter/issues/7)):

	pip install HAP-python==1.1.5

In case when the "hosting server" is running on OSX no extra libraries are needed. For Linux (e.g. Raspberry Pi) servers you will need Avahi/Bonjour installed (due to zeroconf package):

	sudo apt-get install libavahi-compat-libdnssd-dev

**Note**: It was reported, that newer version of zeroconf has [compatibility issues](https://github.com/vfilimonov/co2meter/issues/17), but reverting to 0.23 remediated this:

	pip install -U zeroconf==0.23

**Note**: Setup was tested on Python 3.5. `homekit` compatibility might not be available on Python 2.7 (see #7).


# General usage

### Basic use

The interface is implemented as a class:

	import co2meter as co2
	mon = co2.CO2monitor()

Standard info of the device which is connected:

	mon.info

Read CO2 and temperature values from the device with the timestamp:

	mon.read_data()

If `pandas` is available, the output will be formatted as `pandas.DataFrame` with columns `co2` and `temp` and datetime-index with the timestamp of measurement. Otherwise tuple `(timestamp, co2, temperature)` will be returned.

**Note**: For certain CO2 meter models packages that are sent over USB are not encrypted. In this case `mon.read_data()` could hang without any data returning (see issue #16). If this happens, instantiating CO2monitor object as `mon = co2.CO2monitor(bypass_decrypt=True)` might solve the issue.

### Continuous monitoring

The library uses `threading` module to keep continuous monitoring of the data in the background and storing it in the internal buffer. The following command starts the thread which will listen to new values every 10 seconds:

	mon.start_monitoring(interval=10)

After this command, python will be free to execute other code in a usual way, and new data will be retrieved in the background (parallel thread) and stored in an internal property `data`. This property will be constantly updated and the data could be retrieved at any point. For example, if `pandas` is available, then the following command will plot saved CO2 and temperature data

	mon.data.plot(secondary_y='temp')

The data could be at any point logged to CSV file (NB! `pandas` required). If the file already exists, then only new data (i.e. with timestamps later than the one recorded in the last line) will be appened to the end of file:

	mon.log_data_to_csv('log_co2.csv')

The following command stops the background thread, when it is not needed anymore:

	mon.stop_monitoring()

### Plotting data

The data that was logged to CSV file could be read usig function `read_csv()`:

	old_data = co2.read_csv('log_co2.csv')

CO2 and temperature data could be plotted using `matplotlib` package with the function `plot()` of the module:

	co2.plot(old_data)

Or the following command will plot CO2 data together with the temperature from the internal buffer (see "continuous monitoring"):

	co2.plot(mon.data, plot_temp=True)

By default all data is smoothed using Exponentially Weighted Moving Average with half-life of approximately 30 seconds. This parameter could be changed, or smoothing could be switched off (parameter set to `None`):

	co2.plot(mon.data, plot_temp=True, ewma_halflife=None)

Note, that both plotting and reading CSV files requires `pandas` package to be installed.


## Apple HomeKit compatibility

It is possible to start use your CO2 Monitor with Apple HomeKit. In order for doing that run the following command in the terminal:

	co2meter_homekit

which by default will launch the HomeKit Accessory service listening to the local IP address on the port 51826.

Once the `co2meter_homekit` script is up and running, device could be added to the Apple Home app on iPhone/iPad. For this first make sure that both the iPhone and the machine where `co2meter_homekit` are in the same network (e.g. that iPhone is connected to the WiFi)
launch the *Home app* -> *+* -> *Add accessory* -> *Don't have a code or can't scan?* -> *CO2 Meter*. When asked for PIN code type `800-11-400` (it is hardcoded in [homekit.py](https://github.com/vfilimonov/co2meter/blob/master/co2meter/homekit.py)).

## Monitoring web-server

The web-server is started by the following command in the terminal

	co2meter_server

It will start server by default on the `localhost` on the port 1201 and saving the log to the file `logs\co2.csv`. Both host, port and the log file name could be configured, for example:

	co2meter_server -H 10.0.1.2 -P 8000 -N "Living room"

Once started, it could be accessed via browser at a given address (`http://127.0.0.1:1201` in the first case and `http://10.0.1.2:8000`). The main page will show last readout from the sensor and links to the log history in CSV and JSON formats and a dashboard with the recent charts:
![Screenshot - dash web-server](https://user-images.githubusercontent.com/1324881/36342020-0c2df1ac-13f8-11e8-978a-b1e3e92a3ea4.png)

CO2/temperature readings are stored in the `logs` folder. By default (if `-N` parameter of the command line is not specified), all values will be appended to the single log file (`co2.csv`), however if there's a need to have separate logs (e.g. in case when device is used in several places and logs are not to be confused), the name could be set up from the command line. Dashboard allows to check history of all available logs. In order to change name of the log on a running server, use the following GET call: `http://host:port/rename?name=new_name`.

Finally, HomeKit and web-server could be combined:

	co2meter_server_homekit

which will start homekit accessory and flask web-server on the local IP address.

**Note** If necessary, `bypass_decrypt` argument could be passed to the command line (e.g. `co2meter_server --bypass-decrypt`).

## Running web-server as a service

The low-key solution for running server on the remote machine (e.g. on Raspberry py) is to call

	nohup co2meter_server_homekit -N default_room &

Another alternative is to register it as a [service in the system](https://www.raspberrypi.org/documentation/linux/usage/systemd.md). For this create the file `/etc/systemd/system/co2server.service` under `sudo` (be sure to provide an appropriate full path to `co2meter_server_homekit` and choose proper `WorkingDirectory`):

	[Unit]
	Description=CO2 monitoring service
	After=network.target

	[Service]
	ExecStart=/home/pi/.virtualenvs/system3/bin/co2meter_server_homekit -N default_room
	WorkingDirectory=/home/pi/home/co2
	Restart=always
	User=pi

	[Install]
	WantedBy=multi-user.target

Then the server could be started:

	sudo systemctl start co2server.service

as well as stopped (`systemctl stop`), restarted (`systemctl restart`) or its terminal output could be displayed (`systemctl status`). If you'd like to start it automatically on reboot, call:

	sudo systemctl enable co2server.service


# Notes

* The output from the device is encrypted. I've found no description of the algorithm, except some GitHub libraries with almost identical implementation of decoding: [dmage/co2mon](https://github.com/dmage/co2mon/blob/master/libco2mon/src/co2mon.c), [maizy/ambient7](https://github.com/maizy/ambient7/blob/master/mt8057-agent/src/main/scala/ru/maizy/ambient7/mt8057agent/MessageDecoder.scala), [Lokis92/h1](https://github.com/Lokis92/h1/blob/master/co2java/src/Co2mon.java). This code is based on the repos above (method `CO2monitor._decrypt()`).
* The web-server does not do caching (yet) and was not tested (yet) over a long period of up-time.
* The whole setup is a bit heavy for such simple problem and (in case someone has time) could be simplified: e.g. talking to the device (in linux) could be done via reading/writing to `/dev/hidraw*`, parsing of the CSV and transformations could be done without `pandas`.


# Resources

Useful websites:

* [CO2MeterHacking](https://revspace.nl/CO2MeterHacking) with brief description of the protocol
* [ZG01 CO2 Module manual](https://revspace.nl/images/2/2e/ZyAura_CO2_Monitor_Carbon_Dioxide_ZG01_Module_english_manual-1.pdf) (PDF)
* [USB Communication Protocol](http://www.co2meters.com/Documentation/AppNotes/AN135-CO2mini-usb-protocol.pdf) (PDF)
* Habrahabr.ru blog-posts with the description, review and tests of the device: [part 1](http://habrahabr.ru/company/masterkit/blog/248405/), [part 2](http://habrahabr.ru/company/masterkit/blog/248401/), [part 3](http://habrahabr.ru/company/masterkit/blog/248403/) (Russian, 3 parts)

Scientific and commercial infographics:


* Results of Berkeley Lab research studies showed that elevated indoor carbon dioxide impairs decision-making performance. Original research paper [*U. Satish et al. in Environmental Health Perspectives, 120(12), 2012*](http://ehp.niehs.nih.gov/1104789/) and a [feature story] (https://newscenter.lbl.gov/2012/10/17/elevated-indoor-carbon-dioxide-impairs-decision-making-performance/):
![Impact of CO2 on human decision making process](https://user-images.githubusercontent.com/1324881/36335365-b850af5c-137f-11e8-9bdd-487e4865be3d.png)
* Commercial infographics on CO2 concentration and indoor air quality ([from tester.co.uk](http://www.tester.co.uk/extech-co220-co2-air-quality-monitor)):
![CO2 concentration and indoor air quality](https://user-images.githubusercontent.com/1324881/36335369-bad5c820-137f-11e8-9193-c3ef1658d609.jpg)
* Commercial infographics on CO2 concentration and productivity ([from dadget.ru](http://dadget.ru/katalog/zdorove/detektor-uglekislogo-gaza)):
![CO2 concentration and productivity](https://user-images.githubusercontent.com/1324881/36335370-bc92728a-137f-11e8-8066-8f2295638c7c.jpg)

# Many kudos to contributors

@svart, @hurricup, @beckbria, @ngoldbaum

# License

CO2meter package is released under the MIT license.
