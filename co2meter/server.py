""" Flask server for CO2meter

    (c) Vladimir Filimonov, 2018
    E-mail: vladimir.a.filimonov@gmail.com
"""
from __future__ import print_function
import optparse
import threading
import time
import glob
import os
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

import flask

import co2meter as co2

_LOCALHOST = '127.0.0.1'
_DEFAULT_PORT = '1201'
_DEFAULT_INTERVAL = 5  # seconds
_LOG_CSV = 'co2_log.csv'
_URL = 'https://github.com/vfilimonov/co2meter'

###############################################################################
app = flask.Flask(__name__)


###############################################################################
@app.route('/')
def home():
    data = read_logs(log=False, sessions=True)
    vals = data.split('\n')[-2].split(',')
    return ('<h1>CO2 monitoring server</h1> <font size="+2">'
            '%s<br>CO2 concentration: %s<br>Temperature: %s</font>'
            '<br><br><br>Author: Vladimir Filimonov<br>GitHub: <a href="%s">%s</a>'
            % (vals[0], vals[1], vals[2], _URL, _URL))


#############################################################################
@app.route('/log')
def log():
    data = read_logs(log=True, sessions=True)
    return '<h1>Full log</h1>' + wrap_table(data)


@app.route('/session')
def session():
    # Since we've done a clean-up at start, there should be only one log_*.csv
    data = read_logs(log=False, sessions=True)
    return '<h1>Current session</h1>' + wrap_table(data)


#############################################################################
@app.route('/log.csv')
def log_csv():
    data = read_logs(log=True, sessions=True)
    return wrap_csv(data, 'log.csv')


@app.route('/session.csv')
def session_csv():
    # Since we've done a clean-up at start, there should be only one log_*.csv
    data = read_logs(log=False, sessions=True)
    return wrap_csv(data, 'session.csv')


#############################################################################
@app.route('/kill')
def shutdown():
    server_stop()
    global _monitoring
    _monitoring = False
    return 'Server shutting down...'


#############################################################################
# Monitoring routines
#############################################################################
def read_logs(log=True, sessions=True):
    """ read log files """
    data = 'timestamp,co2,temp\n'
    if log:
        try:
            with open(_LOG_CSV, 'r') as f:
                data += f.read()
        except FileNotFoundError:
            pass
    if sessions:
        for fn in sorted(glob.iglob('log_*.csv')):
            with open(fn, 'r') as f:
                data += f.read()
    return data


#############################################################################
def monitoring_CO2(mon, interval, fname):
    """ Tread for monitoring / logging """
    with mon.co2hid(send_magic_table=True):
        while _monitoring:
            # Request concentration and temperature
            vals = mon._read_co2_temp(max_requests=1000)
            print(vals)

            # Append to file
            with open(fname, 'a') as f:
                f.write('%s,%d,%.1f\n' % vals)

            # Sleep
            time.sleep(interval)


#############################################################################
def start_monitor(interval=_DEFAULT_INTERVAL):
    """ Start CO2 monitoring in a thread """
    # Clean-up logs
    with open(_LOG_CSV, 'a') as log:
        for fn in sorted(glob.iglob('log_*.csv')):
            print('Appending: %s -> %s' % (fn, _LOG_CSV))
            with open(fn, 'r') as f:
                log.write(f.read())
            os.remove(fn)

    # Start monitoring in a thread
    mon = co2.CO2monitor()
    fname = 'log_%d.csv' % (time.time())
    global _monitoring
    _monitoring = True
    t = threading.Thread(target=monitoring_CO2, args=(mon, interval, fname))
    t.start()


#############################################################################
# Server routines
#############################################################################
def server_start(app, default_host=_LOCALHOST, default_port=_DEFAULT_PORT,
                 default_interval=_DEFAULT_INTERVAL):
    """ Runs Flask instance using command line arguments """
    # Based on http://flask.pocoo.org/snippets/133/
    parser = optparse.OptionParser()
    parser.add_option("-H", "--host",
                      help="Hostname of the Flask app [default %s]" % default_host,
                      default=default_host)
    parser.add_option("-P", "--port",
                      help="Port for the Flask app [default %s]" % default_port,
                      default=default_port)
    parser.add_option("-I", "--interval",
                      help="Interval in seconds for CO2meter requests [default %d]" % default_interval,
                      default=default_interval)
    options, _ = parser.parse_args()

    # start monitoring and server
    start_monitor(interval=int(options.interval))
    app.run(host=options.host, port=int(options.port))


def server_stop():
    func = flask.request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()


def wrap_csv(data, fname='output.csv'):
    """ Make response downloadable """
    si = StringIO(data)
    output = flask.make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=%s" % fname
    output.headers["Content-type"] = "text/csv"
    return output


def wrap_table(data):
    """ Return HTML for table """
    res = ('<table><thead><tr><th>Timestamp</th><th>CO2 concentration</th>'
           '<th>Temperature</th></tr></thead><tbody>')
    for line in data.split('\n')[1:]:
        res += '<tr>' + ''.join(['<td>%s</td>' % d for d in line.split(',')]) + '</tr>'
    res += '</tbody></table>'
    return res


###############################################################################
if __name__ == '__main__':
    # start_monitor()  # start_server() will take care of that
    server_start(app)
