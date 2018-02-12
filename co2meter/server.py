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

_name = 'co2log'

_LOCALHOST = '127.0.0.1'
_DEFAULT_PORT = '1201'
_DEFAULT_INTERVAL = 30  # seconds
_DASH_INTERVAL = 30000  # milliseconds
_DEFAULT_NAME = 'co2'
_URL = 'https://github.com/vfilimonov/co2meter'

_SPANS = [{'label': 'Last hour', 'value': '1H'},
          {'label': 'Last day', 'value': '24H'},
          {'label': 'Last week', 'value': '7D'},
          {'label': 'Last month', 'value': '30D'},
          {'label': 'Full log', 'value': ''}]

###############################################################################
app = flask.Flask(__name__)


###############################################################################
@app.route('/')
def home():
    data = read_logs()
    vals = data.split('\n')[-2].split(',')
    return ('<h1>CO2 monitoring server</h1>'
            '<font size="+2">%s<br>CO2 concentration: %s<br>Temperature: %s</font>'
            '<br><br><a href="/log">Data log</a> '
            '(<a href="/log.csv">csv</a>,&nbsp;<a href="/log.json">json</a>)'
            '<br><a href="/dashboard">Dashboard</a>'
            '<br><br><br>Author: Vladimir Filimonov<br>GitHub: <a href="%s">%s</a>'
            % (vals[0], vals[1], vals[2], _URL, _URL))


#############################################################################
@app.route('/log', defaults={'logname': None})
@app.route('/log/<string:logname>')
def log(logname):
    data = read_logs(name=logname)
    return '<h1>Full log</h1>' + wrap_table(data)


@app.route('/log.csv', defaults={'logname': None})
@app.route('/log/<string:logname>.csv')
def log_csv(logname):
    data = read_logs(name=logname)
    return wrap_csv(data, logname)


@app.route('/log.json', defaults={'logname': None})
@app.route('/log/<string:logname>.json')
def log_json(logname):
    data = read_logs(name=logname)
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

    def dash_layout():
        # Get list of files
        files = glob.glob('logs/*.csv')
        files = [os.path.splitext(os.path.basename(_))[0] for _ in files]
        files = [{'label': _, 'value': _} for _ in files]
        fn = _name

        dd_name = dcc.Dropdown(id='name-dropdown', value=fn, options=files,
                               clearable=False, searchable=False)
        dd_span = dcc.Dropdown(id='span-dropdown', value='24H', options=_SPANS,
                               clearable=False, searchable=False)

        # return layout
        ST = {'float': 'left', 'width': '25%'}
        page = [
            html.H2(children='CO2 monitor dashboard'),
            html.Div(children=[html.Div([dd_name], style=ST, id='div-dd-name'),
                               html.Div([dd_span], style=ST, id='div-dd-span'),
                               ], id='controls', style={'height': '40px'}),
            dcc.Graph(id='temp-graph'),
            dcc.Interval(id='interval-component', interval=_DASH_INTERVAL, n_intervals=0),
        ]
        return html.Div(children=page)

    app_dash.layout = dash_layout

    #########################################################################
    def prepare_graph(name=None, span='24H'):
        data = read_logs(name)
        data = pd.read_csv(StringIO(data), parse_dates=[0]).set_index('timestamp')
        if span != '':
            data = data.last(span)

        if span == '24H':
            data = data.resample('60s').mean()
        elif span == '7D':
            data = data.resample('600s').mean()
        elif span == '30D' or span == '':
            data = data.resample('1H').mean()

        fig = plotly.tools.make_subplots(rows=2, cols=1, vertical_spacing=0,
                                         print_grid=False, shared_xaxes=True)
        fig['layout']['margin'] = {'l': 30, 'r': 10, 'b': 30, 't': 10}
        fig['layout']['legend'] = {'x': 0, 'y': 1, 'xanchor': 'left'}
        fig.append_trace({
            'x': data.index,
            'y': data['co2'],
            'name': 'CO2 concentration',
            'mode': 'lines+markers',
            'type': 'scatter'
        }, 1, 1)
        fig.append_trace({
            'x': data.index,
            'y': data['temp'],
            'name': 'Temperature',
            'mode': 'lines+markers',
            'type': 'scatter'
        }, 2, 1)
        return fig

    @app_dash.callback(Output('temp-graph', 'figure'),
                       [Input('interval-component', 'n_intervals'),
                        Input('name-dropdown', 'value'),
                        Input('span-dropdown', 'value'),
                        ])
    def update_graph(n, name, span):
        return prepare_graph(name, span)


#############################################################################
# Monitoring routines
#############################################################################
def read_logs(name=None):
    """ read log files """
    if name is None:
        name = _name
    with open(os.path.join('logs', name + '.csv'), 'r') as f:
        data = f.read()
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
def start_monitor(name=_DEFAULT_NAME, interval=_DEFAULT_INTERVAL):
    """ Start CO2 monitoring in a thread """
    fname = os.path.join('logs', name + '.csv')
    if not os.path.exists('logs'):
        os.makedirs('logs')
    if not os.path.isfile(fname):
        with open(fname, 'a') as f:
            f.write('timestamp,co2,temp\n')

    global _monitoring
    _monitoring = True

    mon = co2.CO2monitor()
    t = threading.Thread(target=monitoring_CO2, args=(mon, interval, fname))
    t.start()


#############################################################################
# Server routines
#############################################################################
def run_app(app, default_host=_LOCALHOST, default_port=_DEFAULT_PORT,
            default_interval=_DEFAULT_INTERVAL, default_name=_DEFAULT_NAME):
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
    parser.add_option("-N", "--name",
                      help="Name for the log file [default %s]" % default_name,
                      default=default_name)
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

    # Name for the current session
    global _name
    _name = options.name

    # start monitoring and server
    if not options.no_monitoring:
        start_monitor(name=options.name, interval=int(options.interval))
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
def wrap_csv(data, fname='output'):
    """ Make CSV response downloadable """
    if fname is None:
        fname = 'log'
    si = StringIO(data)
    output = flask.make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=%s.csv" % fname
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
