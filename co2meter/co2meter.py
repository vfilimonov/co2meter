# coding=utf-8
""" Class for reading data from CO2 monitor.

    (c) Vladimir Filimonov, 2016-2021
    E-mail: vladimir.a.filimonov@gmail.com
"""
try:
    import hid
except AttributeError as e:
    if 'windll' in e.message:
        raise ImportError(('Import failed with an error "AttributeError: %s". '
                           'Possibly there''s a name conflict. Please check if '
                           'library "hid" is instlled and if so - uninstall it, '
                           'keeping only "hidapi".' % str(e)))
    else:
        raise
import datetime as dt
from contextlib import contextmanager
import threading
import time
import os

plt = None  # To be imported on demand only
try:
    import pandas as pd
    import numpy as np
except ImportError:
    pd = np = None

_CO2MON_HID_VENDOR_ID = 0x04d9
_CO2MON_HID_PRODUCT_ID = 0xa052
_CO2MON_MAGIC_WORD = b'Htemp99e'
_CO2MON_MAGIC_TABLE = (0, 0, 0, 0, 0, 0, 0, 0)

_CODE_END_MESSAGE = 0x0D
_CODE_CO2 = 0x50
_CODE_TEMPERATURE = 0x42

_COLORS = {'r': (0.86, 0.37, 0.34),
           'g': (0.56, 0.86, 0.34),
           'b': 'b'}

CO2_HIGH = 1200
CO2_LOW = 800


#############################################################################
def now():
    return dt.datetime.now().replace(microsecond=0)


#############################################################################
def list_to_longint(x):
    return sum([val << (i * 8) for i, val in enumerate(x[::-1])])


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
    def __init__(self, bypass_decrypt=False, interface_path=None):
        """ Initialize the CO2monitor object and retrieve basic HID info.

            Args:
                bypass_decrypt (bool): For certain CO2 meter models packages that
                    are sent over USB are not encrypted. In this case instance
                    of CO2monitor will return no data in .read_data().
                    If this happens, setting bypass_decrypt to True might
                    solve the issue.

                interface_path (bytes): when multiple devices are active, allows
                    you to choose which one should be used for this CO2monitor instance.
            See also:
                https://github.com/vfilimonov/co2meter/issues/16
        """
        self.bypass_decrypt = bypass_decrypt
        self._info = {'vendor_id': _CO2MON_HID_VENDOR_ID,
                      'product_id': _CO2MON_HID_PRODUCT_ID}
        self.init_device(interface_path)

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

    def init_device(self, interface_path=None):
        """" Finds a device in the list of available devices and opens one with interface_number or first available
                if no interface_number is None
        """
        checked_interfaces = []
        for interface in hid.enumerate(self._info['vendor_id'], self._info['product_id']):
            if interface_path is None or interface['path'] == interface_path:
                self._h = hid.device()
                self._info['path'] = interface['path']
                return

            checked_interfaces.append(interface)

        raise Exception('Unable to find hid device.', interface_path, checked_interfaces)

    #########################################################################
    def hid_open(self, send_magic_table=True):
        """ Open connection to HID device. If connection is already open,
            then only the counter of requests is incremented (so hid_close()
            knows how many sub-processes keep the HID handle)

            Parameters
            ----------
            send_magic_table : bool
                If True then the internal "magic table" will be sent to
                the device (it is used for decryption)
        """
        if self._status == 0:
            # If connection was not opened before
            self._h.open_path(self._info['path'])
            if send_magic_table:
                self._h.send_feature_report(self._magic_table)
        self._status += 1

    def hid_close(self, force=False):
        """ Close connection to HID device. If there were several hid_open()
            attempts then the connection will be closed only after respective
            number of calls to hid_close() method

            Parameters
            ----------
            force : bool
                Force-close of connection irrespectively of the counter of
                open requests
        """
        if force:
            self._status = 0
        elif self._status > 0:
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

    #########################################################################
    @property
    def info(self):
        """ Device info """
        return self._info

    @property
    def is_alive(self):
        """ If the device is still connected """
        try:
            with self.co2hid(send_magic_table=True):
                return True
        except:
            return False

    #########################################################################
    def _decrypt(self, message):
        """ Decode message received from CO2 monitor.
        """
        if self.bypass_decrypt:
            return message
        # Rearrange message and convert to long int
        msg = list_to_longint([message[i] for i in [2, 4, 0, 7, 1, 6, 5, 3]])
        # XOR with magic_table
        res = msg ^ self._magic_table_int
        # Cyclic shift by 3 to the right
        res = (res >> 3) | ((res << 61) & 0xFFFFFFFFFFFFFFFF)
        # Convert to list
        res = longint_to_list(res)
        # Subtract and convert to uint8
        res = [(r - mw) & 0xFF for r, mw in zip(res, self._magic_word)]
        return res

    @staticmethod
    def decode_message(msg):
        """ Decode value from the decrypted message

            Parameters
            ----------
            msg : list
                Decrypted message retrieved with hid_read() method

            Returns
            -------
            CntR : int
                CO2 concentration in ppm
            Tamb : float
                Temperature in Celsius
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
        return now(), co2, temp

    #########################################################################
    def read_data_raw(self, max_requests=50):
        with self.co2hid(send_magic_table=True):
            vals = self._read_co2_temp(max_requests=max_requests)
            self._last_data = vals
            return vals

    def read_data(self, max_requests=50):
        """ Listen to values from device and retrieve temperature and CO2.

            Parameters
            ----------
            max_requests : int
                Effective timeout: number of attempts after which None is returned

            Returns
            -------
            tuple (timestamp, co2, temperature)
            or
            pandas.DataFrame indexed with timestamp
                Results of measurements
        """
        if self._keep_monitoring:
            if pd is None:
                return self._data[-1]
            else:
                return self._data.iloc[[-1]]
        else:
            vals = self.read_data_raw(max_requests=max_requests)
            # If pandas is available - return pandas.DataFrame
            if pd is not None:
                vals = pd.DataFrame({'co2': vals[1], 'temp': vals[2]},
                                    index=[vals[0]])
            return vals

    #########################################################################
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
            The monitoring is started in a separate thread, so the current
            interpreter session is not blocked.

            Parameters
            ----------
            interval : float
                Interval in seconds between consecutive data reads
        """
        self._interval = interval
        if self._keep_monitoring:
            # If already started then we should not start a new thread
            return
        self._keep_monitoring = True
        t = threading.Thread(target=self._monitoring)
        t.start()

    def stop_monitoring(self):
        """ Stop continuous monitoring
        """
        self._keep_monitoring = False

    #########################################################################
    @property
    def data(self):
        """ All data retrieved with continuous monitoring
        """
        return self._data

    def log_data_to_csv(self, fname):
        """ Log data retrieved with continuous monitoring to CSV file. If the
            file already exists, then it will be appended.

            Note, that the method requires pandas package (so far alternative
            is not implemented).

            Parameters
            ----------
            fname : string
                Filename
        """
        if pd is None:
            raise NotImplementedError('Logging to CSV is implemented '
                                      'using pandas package only (so far)')
        if os.path.isfile(fname):
            # Check the last line to get the timestamp of the last record
            df = pd.read_csv(fname)
            last = pd.Timestamp(df.iloc[-1, 0])
            # Append only new data
            with open(fname, 'a') as f:
                self._data[self._data.index > last].to_csv(f, header=False)
        else:
            self._data.to_csv(fname)


#############################################################################
def read_csv(fname):
    """ Read data from CSV file.

        Parameters
        ----------
        fname : string
            Filename
    """
    if pd is None:
        raise NotImplementedError('Reading CSV files is implemented '
                                  'using pandas package only (so far)')
    return pd.read_csv(fname, index_col=0, parse_dates=0)


#############################################################################
def plot(data, plot_temp=False, ewma_halflife=30., **kwargs):
    """ Plot recorded data

        Parameters
        ----------
        data : pandas.DataFrame
            Data indexed by timestamps. Should have columns 'co2' and 'temp'
        plot_temp : bool
            If True temperature will be also plotted
        ewma_halflife : float
            If specified (not None) data will be smoothed using EWMA
    """
    global plt
    if plt is None:
        import matplotlib.pyplot as _plt
        plt = _plt

    if pd is None:
        raise NotImplementedError('Plotting is implemented so far '
                                  'using pandas package only')

    # DataFrames
    if (ewma_halflife is not None) and (ewma_halflife > 0):
        halflife = pd.Timedelta(ewma_halflife, 's') / np.mean(np.diff(data.index))
        co2 = pd.ewma(data.co2, halflife=halflife, min_periods=0)
        temp = pd.ewma(data.temp, halflife=2 * halflife, min_periods=0)
    else:
        co2 = data.co2
        temp = data.temp

    co2_r = co2.copy()
    co2_g = co2.copy()
    co2_r[co2_r <= CO2_HIGH] = np.NaN
    co2_g[co2_g >= CO2_LOW] = np.NaN

    # Plotting
    ax = kwargs.pop('ax', plt.gca())

    ax.fill_between(co2_r.index, co2_r.values, CO2_HIGH,
                    alpha=0.5, color=_COLORS['r'])
    ax.fill_between(co2_g.index, co2_g.values, CO2_LOW,
                    alpha=0.5, color=_COLORS['g'])

    ax.axhline(CO2_LOW, color=_COLORS['g'], lw=2, ls='--')
    ax.axhline(CO2_HIGH, color=_COLORS['r'], lw=2, ls='--')

    ax.plot(co2.index, co2.values, lw=2, color='k')

    yl = ax.get_ylim()
    ax.set_ylim([min(600, yl[0]), max(1400, yl[1])])
    ax.set_ylabel('CO2 concentration, ppm')
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=0,
             horizontalalignment='center')

    if plot_temp:
        ax2 = ax.twinx()
        ax2.plot(temp.index, temp.values, color=_COLORS['b'])
        ax2.set_ylabel('Temperature, °C')
        yl = ax2.get_ylim()
        ax2.set_ylim([min(19, yl[0]), max(23, yl[1])])
        ax2.grid('off')

    plt.tight_layout()


#############################################################################
# Entry points
#############################################################################
def start_homekit():
    from .homekit import start_homekit as start
    start()


def start_server():
    from .server import start_server as start
    start()


def start_server_homekit():
    from .server import start_server_homekit as start
    start()
