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

try:
    import dash
    import dash_core_components as dcc
    import dash_html_components as html
    from dash.dependencies import Output, Event, Input
    import pandas as pd
    import plotly
except ImportError:
    dash = None

import co2meter as co2

_LOCALHOST = '127.0.0.1'
_DEFAULT_PORT = '1201'
_DEFAULT_INTERVAL = 5  # seconds
_DASH_INTERVAL = 30000  # milliseconds
_LOG_CSV = 'co2_log.csv'
_URL = 'https://github.com/vfilimonov/co2meter'

###############################################################################
app = flask.Flask(__name__)


###############################################################################
@app.route('/')
def home():
    data = read_logs(log=False, sessions=True)
    vals = data.split('\n')[-2].split(',')
    return ('<h1>CO2 monitoring server</h1>'
            '<font size="+2">%s<br>CO2 concentration: %s<br>Temperature: %s</font>'
            '<br><br><a href="/session">Current session</a> (<a href="/session.csv">csv</a>,&nbsp;<a href="/session.json">json</a>)'
            '<br><a href="/log">Full log</a> (<a href="/log.csv">csv</a>,&nbsp;<a href="/log.json">json</a>)'
            '<br><a href="/dashboard">Dashboard</a>'
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
@app.route('/<string:name>.csv')
def get_csv(name):
    if name.lower() == 'log':
        data = read_logs(log=True, sessions=True)
    elif name.lower() == 'session':
        data = read_logs(log=False, sessions=True)
    else:
        return 'Error: unknown file'
    return wrap_csv(data, name + '.csv')


@app.route('/<string:name>.json')
def get_json(name):
    if name.lower() == 'log':
        data = read_logs(log=True, sessions=True)
    elif name.lower() == 'session':
        data = read_logs(log=False, sessions=True)
    else:
        return 'Error: unknown file'
    return wrap_json(data)


#############################################################################
@app.route('/kill')
def shutdown():
    server_stop()
    global _monitoring
    _monitoring = False
    return 'Server shutting down...'


#############################################################################
# Dash sever
#############################################################################
if dash is not None:
    app_dash = dash.Dash(__name__, server=app, url_base_pathname='/dashboard')

    page = [
        html.H2(children='CO2 monitor dashboard'),
        html.Div(id='contents'),
        dcc.Graph(id='temp-graph'),
        dcc.Interval(id='interval-component', interval=_DASH_INTERVAL, n_intervals=0),
    ]
    app_dash.layout = html.Div(children=page)

    #########################################################################
    def prepare_graph():
        data = read_logs(log=True, sessions=True)
        data = pd.read_csv(StringIO(data), parse_dates=[0])
        fig = plotly.tools.make_subplots(rows=2, cols=1, vertical_spacing=0,
                                         print_grid=False, shared_xaxes=True)
        fig['layout']['margin'] = {'l': 30, 'r': 10, 'b': 30, 't': 10}
        fig['layout']['legend'] = {'x': 0, 'y': 1, 'xanchor': 'left'}
        fig.append_trace({
            'x': data['timestamp'],
            'y': data['co2'],
            'name': 'CO2 concentration',
            'mode': 'lines+markers',
            'type': 'scatter'
        }, 1, 1)
        fig.append_trace({
            'x': data['timestamp'],
            'y': data['temp'],
            'name': 'Temperature',
            'mode': 'lines+markers',
            'type': 'scatter'
        }, 2, 1)
        return fig

    @app_dash.callback(Output('temp-graph', 'figure'),
                       [Input('interval-component', 'n_intervals')])
    def update_graph(n):
        return prepare_graph()


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
            # print(vals)

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
def run_app(app, default_host=_LOCALHOST, default_port=_DEFAULT_PORT,
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
    parser.add_option("-d", "--debug",
                      action="store_true", dest="debug",
                      help=optparse.SUPPRESS_HELP)
    parser.add_option("-m", "--nomonitoring",
                      help="No live monitoring (only flask server)",
                      action="store_true", dest="no_monitoring")
    parser.add_option("-s", "--noserver",
                      help="No server (only monitoring to file)",
                      action="store_true", dest="no_server")
    options, _ = parser.parse_args()

    # start monitoring and server
    if not options.no_monitoring:
        start_monitor(interval=int(options.interval))
    if not options.no_server:
        app.run(host=options.host, port=int(options.port), debug=options.debug)


def server_start():
    run_app(app)


def server_stop():
    func = flask.request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()


###############################################################################
def wrap_csv(data, fname='output.csv'):
    """ Make CSV response downloadable """
    si = StringIO(data)
    output = flask.make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=%s" % fname
    output.headers["Content-type"] = "text/csv"
    return output


def wrap_json(data):
    """ Convert CSV to JSON and make it downloadable """
    entries = [_.split(',') for _ in data.split('\n') if _ != '']
    js = {'timestamp': [_[0] for _ in entries[1:]],
          'co2': [int(_[1]) for _ in entries[1:]],
          'temp': [float(_[2]) for _ in entries[1:]]}
    return flask.jsonify(js)


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
    # start_server() will take care of start_monitor()
    server_start()
