# PyDatastream

CO2meter is a Python interface to the USB CO2 monitor.


## Installation

Preprequisites are libraries `libusb`, `hidapi` and Python package `hid`.

### Installation of USB and HID libraries

##### OSX

Necessarry libraries could be done via [Homebrew](http://brew.sh/):

	brew install libusb hidapi

##### Linux (not tested)

In Ubunti, `libusb` could be retrieved via `apt-get`

	sudo apt-get install libusb-1.0-0-dev

##### Windows (not tested)

I wish I knew....

### Installation of python package

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

#### Continuous monitoring

The library uses `threading` module to keep continuous monitoring of the data and storing it in the internal buffer. The following command starts the thread which will listen to new values every 10 seconds:

	mon.start_monitoring(interval=10)	

The data could be retrieved from internal property `data`. For example, if `pandas` is available then the following command will plot saved CO2 and temperature data 
	
	mon.data.plot(secondary_y='temp')
	
This command stops the background process:

	mon.stop_monitoring()

## Notes

* The output from the device is decrypted. I've found no description of the algorythm, except some GitHub libraries with almost identical implementation of decoding: [dmage/co2mon](https://github.com/dmage/co2mon/blob/master/libco2mon/src/co2mon.c), [maizy/ambient7](https://github.com/maizy/ambient7/blob/master/mt8057-agent/src/main/scala/ru/maizy/ambient7/mt8057agent/MessageDecoder.scala), [Lokis92/h1](https://github.com/Lokis92/h1/blob/master/co2java/src/Co2mon.java). The code in this repository is based on the repos above, but made a little bit more readable (method `_decrypt(self)`).

## Resources

Some useful webpages:

* [CO2MeterHacking](https://revspace.nl/CO2MeterHacking) with brief description of the protocol
* [ZG01 CO2 Module manual](https://revspace.nl/images/2/2e/ZyAura_CO2_Monitor_Carbon_Dioxide_ZG01_Module_english_manual-1.pdf) (PDF)
* [USB Communication Protocol](http://www.co2meters.com/Documentation/AppNotes/AN135-CO2mini-usb-protocol.pdf) (PDF)
* Habrahabr posts with the description, review and tests of the device: [part 1](http://habrahabr.ru/company/masterkit/blog/248405/), [part 2](http://habrahabr.ru/company/masterkit/blog/248401/), [part 3](http://habrahabr.ru/company/masterkit/blog/248403/) (Russian, 3 parts)

## License

CO2meter is released under the MIT license.