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

PORT = 51826
PINCODE = b"800-11-400"
NAME = "CO2 Monitor"
CO2_THRESHOLD = 1200


###############################################################################
# Extended from: https://github.com/ikalchev/HAP-python
###############################################################################
class CO2Accessory(Accessory):
    category = Category.SENSOR  # This is for the icon in the iOS Home app.

    def __init__(self, mon=None, freq=5, **kwargs):
        """ Initialize sensor:
              - call parent __init__
              - save references to characteristics
              - (optional) set up callbacks

            If monitor object is not passed, it will be created.
            freq defines interval in seconds between updating the values.
        """
        super(CO2Accessory, self).__init__(NAME, **kwargs)
        self.monitor = co2.CO2monitor() if mon is None else mon
        self.frequency = freq

    #########################################################################
    def temperature_changed(self, value):
        """ Dummy callback """
        print("Temperature changed to: ", value)

    def co2_changed(self, value):
        """ Dummy callback """
        print("CO2 level is changed to: ", value)

    #########################################################################
    def _set_services(self):
        """ Add services to be supported.

            A loader creates Service and Characteristic objects based on json
            representation such as the Apple-defined ones in pyhap/resources/.
        """
        super(CO2Accessory, self)._set_services()
        char_loader = loader.get_char_loader()

        # Temperature sensor: only mandatory characteristic
        serv_temp = loader.get_serv_loader().get("TemperatureSensor")
        self.char_temp = serv_temp.get_characteristic("CurrentTemperature")
        serv_temp.add_characteristic(self.char_temp)

        # CO2 sensor: both mandatory and optional characteristic
        serv_co2 = loader.get_serv_loader().get("CarbonDioxideSensor")
        self.char_high_co2 = serv_co2.get_characteristic("CarbonDioxideDetected")
        self.char_co2 = char_loader.get("CarbonDioxideLevel")
        serv_co2.add_characteristic(self.char_high_co2)
        serv_co2.add_opt_characteristic(self.char_co2)

        self.char_temp.setter_callback = self.temperature_changed
        self.char_co2.setter_callback = self.co2_changed

        self.add_service(serv_temp)
        self.add_service(serv_co2)

    #########################################################################
    def run(self):
        """ We override this method to implement what the accessory will do when it is
            started. An accessory is started and stopped from the AccessoryDriver.

            It might be convenient to use the Accessory's run_sentinel, which is a
            threading. Event object which is set when the accessory should stop running.
        """
        while not self.run_sentinel.wait(self.frequency):
            with self.monitor.co2hid(send_magic_table=True):
                vals = self.monitor._read_co2_temp(max_requests=1000)
                # print(vals)

            self.char_co2.set_value(vals[1])
            self.char_high_co2.set_value(vals[1] > CO2_THRESHOLD)
            self.char_temp.set_value(int(vals[2]))

    def stop(self):
        """ Here we should clean-up resources if necessary.
            It is called by the AccessoryDriver when the Accessory is being stopped
            (it is called right after run_sentinel is set).
        """
        print("Stopping accessory.")


###############################################################################
def start_homekit_accessory():
    acc = CO2Accessory(pincode=PINCODE)

    # Start the accessory on selected port
    driver = AccessoryDriver(acc, port=PORT)

    # We want KeyboardInterrupts and SIGTERM (kill) to be handled by the driver itself,
    # so that it can gracefully stop the accessory, server and advertising.
    signal.signal(signal.SIGINT, driver.signal_handler)
    signal.signal(signal.SIGTERM, driver.signal_handler)

    # Start it!
    driver.start()


###############################################################################
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    start_homekit_accessory()
