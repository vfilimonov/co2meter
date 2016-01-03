""" Class for reading data from CO2 monitor.

    (c) Vladimir Filimonov, 2016
    E-mail: vladimir.a.filimonov@gmail.com
"""
import hid
import datetime as dt
from contextlib import contextmanager
import threading
import time
try:
    import pandas as pd
except ImportError:
    pd = None

_CO2MON_HID_VENDOR_ID = 0x04d9
_CO2MON_HID_PRODUCT_ID = 0xa052
_CO2MON_MAGIC_WORD = 'Htemp99e'
_CO2MON_MAGIC_TABLE = (0, 0, 0, 0, 0, 0, 0, 0)

_CODE_END_MESSAGE = 0x0D
_CODE_CO2 = 0x50
_CODE_TEMPERATURE = 0x42


#############################################################################
def list_to_longint(x):
    return sum([val << (i*8) for i, val in enumerate(x[::-1])])


#############################################################################
def longint_to_list(x):
    return [(x >> i) & 0xFF for i in (56, 48, 40, 32, 24, 16, 8, 0)]


#############################################################################
def convert_temperature(val):
    """ Convert temperature from Kelvin (unit of 1/16th K) to Celsius
    """
    return val * 0.0625 - 273.15


#############################################################################
# Class to operate with CO2 monitor
#############################################################################
class CO2monitor:
    def __init__(self):
        self._info = {'vendor_id': _CO2MON_HID_VENDOR_ID,
                      'product_id': _CO2MON_HID_PRODUCT_ID}
        self._h = hid.device()
        # Number of requests to open connection
        self._status = 0

        self._magic_word = [((w << 4) & 0xFF) | (w >> 4)
                            for w in bytearray(_CO2MON_MAGIC_WORD)]
        self._magic_table = _CO2MON_MAGIC_TABLE
        self._magic_table_int = list_to_longint(_CO2MON_MAGIC_TABLE)

        # Initialisation of continuous monitoring
        if pd is None:
            self._data = []
        else:
            self._data = pd.DataFrame()

        self._keep_monitoring = False
        self._interval = 10

        # Device info
        with self.co2hid():
            self._info['manufacturer'] = self._h.get_manufacturer_string()
            self._info['product_name'] = self._h.get_product_string()
            self._info['serial_no'] = self._h.get_serial_number_string()

    def hid_open(self, send_magic_table=True):
        """ Open connection to HID device """
        if self._status == 0:
            # If connection was not opened before
            self._h.open(self._info['vendor_id'], self._info['product_id'])
            if send_magic_table:
                self._h.send_feature_report(self._magic_table)
        self._status += 1

    def hid_close(self):
        """ close connection to HID device """
        if self._status > 0:
            self._status -= 1
        if self._status == 0:
            self._h.close()

    def hid_read(self):
        """ Read 8-byte string from HID device """
        msg = self._h.read(8)
        return self._decrypt(msg)

    @contextmanager
    def co2hid(self, send_magic_table=True):
        self.hid_open(send_magic_table=send_magic_table)
        try:
            yield
        finally:
            self.hid_close()

    @property
    def info(self):
        """ Device info """
        return self._info

    def _decrypt(self, message):
        """ Decode message received from CO2 monitor.
        """
        # Rearrange message and convert to long int
        msg = list_to_longint([message[i] for i in [2, 4, 0, 7, 1, 6, 5, 3]])
        # XOR with magic_table
        res = msg ^ self._magic_table_int
        # Cyclic shift by 3 to the right
        res = (res>>3) | ((res<<61) & 0xFFFFFFFFFFFFFFFF)
        # Convert to list
        res = longint_to_list(res)
        # Subtract and convert to uint8
        res = [(r-mw) & 0xFF for r, mw in zip(res, self._magic_word)]
        return res

    @staticmethod
    def decode_message(msg):
        """ Decode value from the decrypted list:
            - CntR: CO2 concentration in ppm
            - Tamb: Temperature in Kelvin (unit of 1/16th K)
        """
        # Expected 3 zeros at the end
        bad_msg = (msg[5] != 0) or (msg[6] != 0) or (msg[7] != 0)
        # End of message should be 0x0D
        bad_msg |= msg[4] != _CODE_END_MESSAGE
        # Check sum: LSB of sum of first 3 bytes
        bad_msg |= (sum(msg[:3]) & 0xFF) != msg[3]
        if bad_msg:
            return None, None

        value = (msg[1] << 8) | msg[2]

        if msg[0] == _CODE_CO2:  # CO2 concentration in ppm
            return int(value), None
        elif msg[0] == _CODE_TEMPERATURE:  # Temperature in Celsius
            return None, convert_temperature(value)
        else:  # Other codes - so far not decoded
            return None, None

    def _read_co2_temp(self, max_requests=50):
        """ Read one pair of values from the device.
            HID device should be open before
        """
        co2, temp = None, None
        for ii in range(max_requests):
            _co2, _temp = self.decode_message(self.hid_read())
            if _co2 is not None:
                co2 = _co2
            if _temp is not None:
                temp = _temp
            if (co2 is not None) and (temp is not None):
                break
        ts = dt.datetime.now().replace(microsecond=0)
        return ts, co2, temp

    def read_data(self, max_requests=50):
        """ Listen to values from device and retrieve temperature and CO2.
            - Max_requests: limits number of requests (i.e. timeout)
            - num_values: number of values to retrieve (default: 1)
        """
        with self.co2hid(send_magic_table=True):
            vals = self._read_co2_temp(max_requests=max_requests)

        # If pandas is accessible - return pandas.DataFrame
        if pd is not None:
            vals = pd.DataFrame({'co2': vals[1], 'temp': vals[2]},
                                index=[vals[0]])
        return vals

    def _monitoring(self):
        """ Private function for continuous monitoring.
        """
        with self.co2hid(send_magic_table=True):
            while self._keep_monitoring:
                vals = self._read_co2_temp(max_requests=1000)
                if pd is None:
                    self._data.append(vals)
                else:
                    vals = pd.DataFrame({'co2': vals[1], 'temp': vals[2]},
                                        index=[vals[0]])
                    self._data = self._data.append(vals)
                time.sleep(self._interval)

    def start_monitoring(self, interval=5):
        """ Start continuous monitoring of the values and collecting them
            in the list / pandas.DataFrame.
            - Interval: defines interval between consecutive reads in seconds.
        """
        self._keep_monitoring = True
        self._interval = interval
        t = threading.Thread(target=self._monitoring)
        t.start()

    def stop_monitoring(self):
        """ Stop continuous monitoring
        """
        self._keep_monitoring = False

    @property
    def data(self):
        """ Data retrieved with continuous monitoring
        """
        return self._data
