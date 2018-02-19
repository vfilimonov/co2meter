""" Flask server for CO2meter

    (c) Vladimir Filimonov, 2018
    E-mail: vladimir.a.filimonov@gmail.com
"""
import optparse
import logging
import threading
import time
import glob
import os
import socket
import signal
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

_DEFAULT_HOST = '127.0.0.1'
_DEFAULT_PORT = '1201'
_DEFAULT_INTERVAL = 30  # seconds
_DASH_INTERVAL = 30000  # milliseconds
_DEFAULT_NAME = 'co2'
_URL = 'https://github.com/vfilimonov/co2meter'
_COLORS = {'r': '#FF4136', 'y': '#FFDC00', 'g': '#2ECC40'}
_RANGE_MID = [800, 1200]

_name = _DEFAULT_NAME

_SPANS = [{'label': 'Last hour', 'value': '1H'},
          {'label': 'Last day', 'value': '24H'},
          {'label': 'Last week', 'value': '7D'},
          {'label': 'Last month', 'value': '30D'},
          {'label': 'Full log', 'value': ''}]

###############################################################################
mon = None

###############################################################################
app = flask.Flask(__name__)


###############################################################################
_IMG_G = '1324881/36358454-d707e2f4-150e-11e8-9bd1-b479e232f28f'
_IMG_Y = '1324881/36358456-d8b513ba-150e-11e8-91eb-ade37733b19e'
_IMG_R = '1324881/36358457-da3e3e8c-150e-11e8-85af-855571275d88'
_HTML_TEMPLATE = r"""
<h1>CO2 monitoring server</h1>
<div>
<div style="position: relative; float: left;">
<img src="https://user-images.githubusercontent.com/%s.jpg">
</div>
<div>
<font size="+2">%s<br>CO2 concentration: %s<br>Temperature: %s&#8451;</font>
<br><br><a href="/log">Data log</a>
(<a href="/log.csv">csv</a>,&nbsp;<a href="/log.json">json</a>)%s
</div>
</div>
<br>Author: Vladimir Filimonov<br>GitHub: <a href="%s">%s</a>
"""


@app.route('/')
def home():
    try:
        vals = list(mon._last_data)
        vals[-1] = '%.1f' % vals[-1]
    except:
        data = read_logs()
        vals = data.split('\n')[-2].split(',')

    if int(vals[1]) >= _RANGE_MID[1]:
        color = _COLORS['r']
        img = _IMG_R
    elif int(vals[1]) < _RANGE_MID[0]:
        color = _COLORS['g']
        img = _IMG_G
    else:
        color = _COLORS['y']
        img = _IMG_Y
    co2 = '<font color="%s">%s ppm</font>' % (color, vals[1])

    if dash is None:
        url_dash = ''
    else:
        url_dash = '<br><a href="/dashboard">Dashboard</a>'
    return _HTML_TEMPLATE % (img, vals[0], co2, vals[2], url_dash, _URL, _URL)


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
@app.route('/rename')
def get_shape_positions():
    args = flask.request.args
    logging.info('rename', args.to_dict())
    new_name = args.get('name', default=None, type=str)
    if new_name is None:
        return 'Error: new log name is not specified!'
    global _name
    _name = new_name
    return 'Log name has changed to "%s"' % _name


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
    app_dash.title = 'CO2 monitor'

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

        # Check if mobile
        try:
            agent = flask.request.headers.get('User-Agent')
            phones = ['iphone', 'android', 'blackberry', 'fennec', 'iemobile']
            staticPlot = any(phone in agent.lower() for phone in phones)
        except RuntimeError:
            staticPlot = False

        # return layout
        ST = {'float': 'left', 'width': '25%'}
        CFG = {'displayModeBar': False, 'queueLength': 0, 'staticPlot': staticPlot}
        page = [
            html.H2(children='CO2 monitor dashboard'),
            html.Div(children=[html.Div([dd_name], style=ST, id='div-dd-name'),
                               html.Div([dd_span], style=ST, id='div-dd-span'),
                               ], id='controls', style={'height': '40px'}),
            html.Div(children=[dcc.Graph(id='temp-graph', config=CFG)],
                     id='div-graph'),
            #html.Div([html.P('<font size="-2" color="#DDDDDD">by Vladimir Filimonov</font>')]),
            html.Div(style={'height': '10'}),
            html.Div('by Vladimir Filimonov', style={'color': '#DDDDDD', 'fontSize': 14, 'text-align': 'right'}),
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
        elif span == '30D':
            data = data.resample('1H').mean()
        elif span == '':
            if len(data) > 3000:  # Resample only long series
                data = data.resample('1H').mean()

        co2_min = min(500, data['co2'].min() - 50)
        co2_max = max(2000, data['co2'].max() + 50)

        # x-span
        rect_green = {'type': 'rect', 'layer': 'below',
                      'xref': 'paper', 'x0': 0, 'x1': 1,
                      'yref': 'y', 'y0': co2_min, 'y1': _RANGE_MID[0],
                      'fillcolor': _COLORS['g'],
                      'opacity': 0.2, 'line': {'width': 0},
                      }
        rect_yellow = dict(rect_green)
        rect_yellow['y0'] = _RANGE_MID[0]
        rect_yellow['y1'] = _RANGE_MID[1]
        rect_yellow['fillcolor'] = _COLORS['y']
        rect_red = dict(rect_green)
        rect_red['y0'] = _RANGE_MID[1]
        rect_red['y1'] = co2_max
        rect_red['fillcolor'] = _COLORS['r']

        # Make figure
        fig = plotly.tools.make_subplots(rows=2, cols=1, vertical_spacing=0.1,
                                         print_grid=False, shared_xaxes=True,
                                         subplot_titles=('CO2 concentration', 'Temperature'))
        fig['layout']['margin'] = {'l': 30, 'r': 10, 'b': 30, 't': 30}
        fig['layout']['showlegend'] = False
        fig['layout']['shapes'] = [rect_green, rect_yellow, rect_red]
        fig.append_trace({
            'x': data.index,
            'y': data['co2'],
            'mode': 'lines+markers',
            'type': 'scatter',
            'yaxis': {'range': [co2_min, co2_max]},
        }, 1, 1)
        fig.append_trace({
            'x': data.index,
            'y': data['temp'],
            'mode': 'lines+markers',
            'type': 'scatter',
            'yaxis': {'range': [min(15, data['temp'].min()),
                                max(27, data['temp'].max())]},
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
def write_to_log(vals):
    """ file name for a current log """
    # Create file if does not exist
    fname = os.path.join('logs', _name + '.csv')
    if not os.path.exists('logs'):
        os.makedirs('logs')
    if not os.path.isfile(fname):
        with open(fname, 'a') as f:
            f.write('timestamp,co2,temp\n')
    # Append to file
    with open(fname, 'a') as f:
        f.write('%s,%d,%.1f\n' % vals)


def monitoring_CO2(mon, interval):
    """ Tread for monitoring / logging """
    while _monitoring:
        # Request concentration and temperature
        vals = mon.read_data_raw(max_requests=1000)
        logging.info('[%s] %d ppm, %.1f deg C' % tuple(vals))
        # Write to log and sleep
        write_to_log(vals)
        time.sleep(interval)


#############################################################################
def start_monitor(name=_DEFAULT_NAME, interval=_DEFAULT_INTERVAL):
    """ Start CO2 monitoring in a thread """
    logging.basicConfig(level=logging.INFO)

    global mon, _monitoring
    _monitoring = True
    mon = co2.CO2monitor()
    mon.read_data_raw()
    t = threading.Thread(target=monitoring_CO2, args=(mon, interval))
    t.start()
    return t


#############################################################################
# Server routines
#############################################################################
def my_ip():
    """ Get my local IP address """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))  # Google Public DNS
        return s.getsockname()[0]


def start_server_homekit():
    """ Start monitoring, flask/dash server and homekit accessory """
    # Based on http://flask.pocoo.org/snippets/133/
    try:
        from .homekit import PORT, start_homekit
    except:
        # the case of running not from the installed module
        from homekit import PORT, start_homekit

    host = my_ip()
    parser = optparse.OptionParser()
    parser.add_option("-H", "--host",
                      help="Hostname of the Flask app [default %s]" % host,
                      default=host)
    parser.add_option("-P", "--port-flask",
                      help="Port for the Flask app [default %s]" % _DEFAULT_PORT,
                      default=_DEFAULT_PORT)
    parser.add_option("-K", "--port-homekit",
                      help="Port for the Homekit accessory [default %s]" % PORT,
                      default=PORT)
    parser.add_option("-N", "--name",
                      help="Name for the log file [default %s]" % _DEFAULT_NAME,
                      default=_DEFAULT_NAME)
    options, _ = parser.parse_args()

    global _name
    _name = options.name

    # Start monitoring
    t_monitor = start_monitor(name=options.name)
    # Start homekit
    t_homekit = start_homekit(mon=mon, host=options.host, port=int(options.port_homekit),
                              monitoring=False, handle_sigint=False)

    # # Register Ctrl-C Call-backs
    # def handle_control_c(*args, **kwargs):
    #     logging.info('Shutting down homekit...')
    #     t_homekit.signal_handler(*args, **kwargs)
    #     logging.info('Shutting down monitoring...')
    #     global _monitoring
    #     _monitoring = False
    #     time.sleep(2)
    #     logging.info('Shutting down flask server...')
    #     import sys
    #     sys.exit(0)
    #
    # signal.signal(signal.SIGINT, handle_control_c)

    # Start server
    app.run(host=options.host, port=int(options.port_flask))


#############################################################################
def start_server():
    """ Runs Flask instance using command line arguments """
    # Based on http://flask.pocoo.org/snippets/133/
    parser = optparse.OptionParser()
    parser.add_option("-H", "--host",
                      help="Hostname of the Flask app [default %s]" % _DEFAULT_HOST,
                      default=_DEFAULT_HOST)
    parser.add_option("-P", "--port",
                      help="Port for the Flask app [default %s]" % _DEFAULT_PORT,
                      default=_DEFAULT_PORT)
    parser.add_option("-I", "--interval",
                      help="Interval in seconds for CO2meter requests [default %d]" % _DEFAULT_INTERVAL,
                      default=_DEFAULT_INTERVAL)
    parser.add_option("-N", "--name",
                      help="Name for the log file [default %s]" % _DEFAULT_NAME,
                      default=_DEFAULT_NAME)
    parser.add_option("-m", "--nomonitoring",
                      help="No live monitoring (only flask server)",
                      action="store_true", dest="no_monitoring")
    parser.add_option("-s", "--noserver",
                      help="No server (only monitoring to file)",
                      action="store_true", dest="no_server")
    options, _ = parser.parse_args()

    global _name
    _name = options.name

    # Start monitoring
    if not options.no_monitoring:
        start_monitor(name=options.name, interval=int(options.interval))

    # Start server
    if not options.no_server:
        app.run(host=options.host, port=int(options.port))


def stop_server():
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
    start_server()
    # start_server_homekit()
