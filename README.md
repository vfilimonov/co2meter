# CO2meter

CO2meter is a Python interface to the USB CO2 monitor.


## Installation

Preprequisites are libraries (1) `libusb`, `hidapi` and (2) Python package `hid`.

#### 1a. OSX

Necessarry libraries could be installed via [Homebrew](http://brew.sh/):

	brew install libusb hidapi

#### 1b. Linux (NB! not tested)

In Ubunti, `libusb` could be retrieved via `apt-get`

	sudo apt-get install libusb-1.0-0-dev

TODO

#### 1c. Windows (NB! not tested)

TODO

#### 2. Installation of python package

First install `pid` package:

	pip install hid
	
Then installation of `co2meter` could be done via the same `pip` utility:

	pip install co2meter

Optionally, if [pandas package](http://pandas.pydata.org/) is available then the data will be retrieved as pandas.DataFrames rather than list of tuples. 

## Usage

#### Basic use

The interface is implemented as a class:

	import co2monitor as co2
	co2mon = co2.CO2monitor()
	
Standard info of the device which is connected:

	mon.info

Read CO2 and temperature values from the device with the timestamp:

	mon.read_data()
	
If `pandas` is available, the output will be formated as `pandas.DataFrame` with columns `co2` and `temp` and datetime-index with the timestamp of measurement. Otherwise tuple `(timestamp, co2, temperature)` will be retured.

#### Continuous monitoring

The library uses `threading` module to keep continuous monitoring of the data in the background and storing it in the internal buffer. The following command starts the thread which will listen to new values every 10 seconds:

	mon.start_monitoring(interval=10)	

After this command, python will be free to execute other code in a usual way, and new data will be retrieved in the background (parallel thread) and stored in an internal property `data`. This property will be constantly updated and the data could be retrieved at any point. For example, if `pandas` is available, then the following command will plot saved CO2 and temperature data 
	
	mon.data.plot(secondary_y='temp')
	
The data could be at any point logged to CSV file (NB! `pandas` required). If the file already exists, then only new data (i.e. with timestamps later than the one recorded in the last line) will be appened to the end of file:

	mon.log_data_to_csv('log_co2.csv')
	
The following command stops the background thread, when it is not needed anymore:

	mon.stop_monitoring()

## Notes

* The output from the device is encrypted. I've found no description of the algorythm, except some GitHub libraries with almost identical implementation of decoding: [dmage/co2mon](https://github.com/dmage/co2mon/blob/master/libco2mon/src/co2mon.c), [maizy/ambient7](https://github.com/maizy/ambient7/blob/master/mt8057-agent/src/main/scala/ru/maizy/ambient7/mt8057agent/MessageDecoder.scala), [Lokis92/h1](https://github.com/Lokis92/h1/blob/master/co2java/src/Co2mon.java). The code in this repository is based on the repos above, but made a little bit more readable (method `_decrypt(self)`).

## Resources

Useful websites:

* [CO2MeterHacking](https://revspace.nl/CO2MeterHacking) with brief description of the protocol
* [ZG01 CO2 Module manual](https://revspace.nl/images/2/2e/ZyAura_CO2_Monitor_Carbon_Dioxide_ZG01_Module_english_manual-1.pdf) (PDF)
* [USB Communication Protocol](http://www.co2meters.com/Documentation/AppNotes/AN135-CO2mini-usb-protocol.pdf) (PDF)
* Habrahabr.ru posts with the description, review and tests of the device: [part 1](http://habrahabr.ru/company/masterkit/blog/248405/), [part 2](http://habrahabr.ru/company/masterkit/blog/248401/), [part 3](http://habrahabr.ru/company/masterkit/blog/248403/) (Russian, 3 parts)

Scientific and commercial infographics:


* Results of Berkeley Lab research studies showed that elevated indoor carbon dioxide impairs decision-making performance. [Original research paper *U. Satish et al. in Environmental Health Perspectives, 120(12), 2012*](http://ehp.niehs.nih.gov/1104789/) and [feature story] (https://newscenter.lbl.gov/2012/10/17/elevated-indoor-carbon-dioxide-impairs-decision-making-performance/):
![Impact of CO2 on human decision making process](https://newscenter.lbl.gov/wp-content/uploads/sites/2/2012/10/CO2-Figure2.png)
* Commercial infographics on CO2 concentration and indoor air quality ([from tester.co.uk](http://www.tester.co.uk/extech-co220-co2-air-quality-monitor)):
![CO2 concentration and indoor air quality](http://www.tester.co.uk/media/wysiwyg/ted/product/extech-co220-co2-concentration.jpg)
* Commercial infographics on CO2 concentration and productivity ([from dadget.ru](http://dadget.ru/katalog/zdorove/detektor-uglekislogo-gaza)):
![CO2 concentration and productivity](http://dadget.ru/image/data/01/mt8057-01.jpg)

## License

CO2meter package is released under the MIT license.