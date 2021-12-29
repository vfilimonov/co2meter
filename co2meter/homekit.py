""" Apple homekit accessory for CO2meter

    (c) Vladimir Filimonov, 2018
    E-mail: vladimir.a.filimonov@gmail.com
"""
import logging
import signal

from pyhap.accessory_driver import AccessoryDriver
from pyhap.accessory import Accessory, Category
import pyhap.loader as loader

import co2meter as co2

###############################################################################
PORT = 51826
PINCODE = b"800-11-400"
NAME = 'CO2 Monitor'
IDENTIFY = 'co2meter (https://github.com/vfilimonov/co2meter)'
CO2_THRESHOLD = 1200  # iPhone will show warning if the concentration is above
FREQUENCY = 45  # seconds - between consecutive reads from the device


###############################################################################
# Extended from: https://github.com/ikalchev/HAP-python
###############################################################################
class CO2Accessory(Accessory):
    category = Category.SENSOR  # This is for the icon in the iOS Home app.

    def __init__(self, mon=None, freq=FREQUENCY, monitoring=True, bypass_decrypt=False, **kwargs):
        """ Initialize sensor:
              - call parent __init__
              - save references to characteristics
              - (optional) set up callbacks

            If monitor object is not passed, it will be created.
            freq defines interval in seconds between updating the values.
        """
        if not monitoring and mon is None:
            raise ValueError('For monitoring=False monitor object should be passed')
        self.monitor = co2.CO2monitor(bypass_decrypt=bypass_decrypt) if mon is None else mon
        self.frequency = freq
        self.monitoring = monitoring
        super(CO2Accessory, self).__init__(NAME, **kwargs)

    #########################################################################
    def temperature_changed(self, value):
        """ Dummy callback """
        logging.info("Temperature changed to: %s" % value)

    def co2_changed(self, value):
        """ Dummy callback """
        logging.info("CO2 level is changed to: %s" % value)

    #########################################################################
    def _set_services(self):
        """ Add services to be supported (called from __init__).
            A loader creates Service and Characteristic objects based on json
            representation such as the Apple-defined ones in pyhap/resources/.
        """
        # This call sets AccessoryInformation, so we'll do this below
        # super(CO2Accessory, self)._set_services()

        char_loader = loader.get_char_loader()
        serv_loader = loader.get_serv_loader()

        # Mandatory: Information about device
        info = self.monitor.info
        serv_info = serv_loader.get("AccessoryInformation")
        serv_info.get_characteristic("Name").set_value(NAME, False)
        serv_info.get_characteristic("Manufacturer").set_value(info['manufacturer'], False)
        serv_info.get_characteristic("Model").set_value(info['product_name'], False)
        serv_info.get_characteristic("SerialNumber").set_value(info['serial_no'], False)
        serv_info.get_characteristic("Identify").set_value(IDENTIFY, False)
        # Need to ensure AccessoryInformation is with IID 1
        self.add_service(serv_info)

        # Temperature sensor: only mandatory characteristic
        serv_temp = serv_loader.get("TemperatureSensor")
        self.char_temp = serv_temp.get_characteristic("CurrentTemperature")
        serv_temp.add_characteristic(self.char_temp)

        # CO2 sensor: both mandatory and optional characteristic
        serv_co2 = serv_loader.get("CarbonDioxideSensor")
        self.char_high_co2 = serv_co2.get_characteristic("CarbonDioxideDetected")
        self.char_co2 = char_loader.get("CarbonDioxideLevel")
        serv_co2.add_characteristic(self.char_high_co2)
        serv_co2.add_opt_characteristic(self.char_co2)

        self.char_temp.setter_callback = self.temperature_changed
        self.char_co2.setter_callback = self.co2_changed

        self.add_service(serv_temp)
        self.add_service(serv_co2)

    #########################################################################
    def _read_and_set(self):
        if self.monitoring:
            vals = self.monitor.read_data_raw(max_requests=1000)
        else:
            try:
                vals = self.monitor._last_data
            except:
                return
        self.char_co2.set_value(vals[1])
        self.char_high_co2.set_value(vals[1] > CO2_THRESHOLD)
        self.char_temp.set_value(int(vals[2]))

    def run(self):
        """ We override this method to implement what the accessory will do when it is
            started. An accessory is started and stopped from the AccessoryDriver.

            It might be convenient to use the Accessory's run_sentinel, which is a
            threading. Event object which is set when the accessory should stop running.
        """
        self._read_and_set()
        while not self.run_sentinel.wait(self.frequency):
            self._read_and_set()

    def stop(self):
        """ Here we should clean-up resources if necessary.
            It is called by the AccessoryDriver when the Accessory is being stopped
            (it is called right after run_sentinel is set).
        """
        logging.info("Stopping accessory.")


###############################################################################
###############################################################################
def start_homekit(mon=None, port=PORT, host=None, monitoring=True,
                  handle_sigint=True, bypass_decrypt=False):
    logging.basicConfig(level=logging.INFO)

    acc = CO2Accessory(mon=mon, pincode=PINCODE, monitoring=monitoring, bypass_decrypt=bypass_decrypt)
    # Start the accessory on selected port
    driver = AccessoryDriver(acc, port=port, address=host)

    # We want KeyboardInterrupts and SIGTERM (kill) to be handled by the driver itself,
    # so that it can gracefully stop the accessory, server and advertising.
    if handle_sigint:
        signal.signal(signal.SIGINT, driver.signal_handler)
        signal.signal(signal.SIGTERM, driver.signal_handler)

    # Start it!
    driver.start()
    return driver


###############################################################################
if __name__ == '__main__':
    start_homekit()
