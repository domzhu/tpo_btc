from MP import MpFunctions
import requests
from dash import Dash, dcc, html
from dash.dependencies import Input, Output
import pandas as pd
import plotly.graph_objs as go
import datetime as dt
import numpy as np
import warnings

warnings.filterwarnings('ignore')

app = Dash(__name__)

def get_ticksize(data, freq=30):
    numlen = int(len(data) / 2)
    tztail = data.tail(numlen).copy()
    tztail['tz'] = tztail.Close.rolling(freq).std()
    tztail = tztail.dropna()
    ticksize = np.ceil(tztail['tz'].mean() * 0.25)
    return max(int(ticksize), 1)

def get_data(url):
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list) or len(data) == 0:
        raise ValueError(f"Unexpected response: {data}")

    df = pd.DataFrame(data)
    df = df.apply(pd.to_numeric)
    df[0] = pd.to_datetime(df[0], unit='ms')
    df.columns = ['datetime', 'Open', 'High', 'Low', 'Close', 'volume', 'Close_time', 'Quote_asset_volume', 'Trades', 'Taker_base_vol', 'Taker_quote_vol', 'Ignore']
    df = df[['datetime', 'Open', 'High', 'Low', 'Close', 'volume']]
    df.set_index('datetime', inplace=False)
    return df

def get_recent_history(days=4, symbol="BTCBUSD", interval="30m"):
    now = dt.datetime.utcnow()
    start = (now - dt.timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = now
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    url = (
        f"https://api.binance.com/api/v3/klines?symbol={symbol}"
        f"&interval={interval}&startTime={start_ms}&endTime={end_ms}&limit=1000"
    )
    try:
        return get_data(url)
    except Exception:
        alt_url = (
            f"https://www.binance.com/api/v3/klines?symbol={symbol}"
            f"&interval={interval}&startTime={start_ms}&endTime={end_ms}&limit=1000"
        )
        return get_data(alt_url)

def get_live_data(symbol="BTCBUSD", interval="1m"):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=1000"
    try:
        return get_data(url)
    except Exception:
        alt_url = f"https://www.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=1000"
        return get_data(alt_url)

# Load last four complete days plus today's session
df = get_recent_history(days=4)

# Setup chart context
context_days = len([group[1] for group in df.groupby(df.index.date)])
freq = 2
avglen = context_days - 2
mode = 'tpo'
trading_hr = 24
day_back = 0
ticksz = get_ticksize(df.copy(), freq=freq) * 2
textsize = 10

symbol = 'BTC-USD Live' if day_back == 0 else 'Historical Mode'

dfnflist = [group[1] for group in df.groupby(df.index.date)]
dates = [day.index[0] for day in dfnflist]
dates.append(pd.Timestamp(dt.datetime.today().strftime('%Y-%m-%d') + ' 23:59:59'))

date_mark = {
    str(i): {
        'label': str(i),
        'style': {'color': 'blue', 'fontsize': '4', 'text-orientation': 'upright'}
    } for i in range(len(dates))
}

mp = MpFunctions(data=df.copy(), freq=freq, style=mode, avglen=avglen, ticksize=ticksz, session_hr=trading_hr)
mplist_full = mp.get_context()
listmp_hist = mplist_full[0][:-1]
distribution_hist = mplist_full[1].iloc[:-1].reset_index(drop=True)

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dcc.Link('Twitter', href='https://twitter.com/beinghorizontal'),
    html.Br(),
    dcc.Link('python source code', href='http://www.github.com/beinghorizontal'),
    html.H4('@beinghorizontal'),
    dcc.Graph(id='beinghorizontal'),
    dcc.Interval(id='interval-component', interval=5 * 1000, n_intervals=0),
    html.P([
        html.Label("Time Period"),
        dcc.RangeSlider(
            id='slider',
            pushable=1,
            marks=date_mark,
            min=0,
            max=len(dates),
            step=None,
            value=[len(dates) - 2, len(dates) - 1]
        )
    ], style={'width': '80%', 'fontSize': '14px', 'padding-left': '100px', 'display': 'inline-block'})
])

@app.callback(
    Output('beinghorizontal', 'figure'),
    [Input('interval-component', 'n_intervals'), Input('slider', 'value')]
)
def update_graph(n, value):
    global listmp_hist, distribution_hist

    df_live1 = get_live_data()
    df_live1 = df_live1.dropna()
    dflive30 = df_live1.resample('30min').agg({
        'datetime': 'last',
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'volume': 'sum'
    })

    df2 = pd.concat([df, dflive30])
    df2 = df2.drop_duplicates('datetime')

    ticksz_live = get_ticksize(dflive30.copy(), freq=2)
    mplive = MpFunctions(data=dflive30.copy(), freq=freq, style=mode, avglen=avglen, ticksize=ticksz_live, session_hr=trading_hr)
    mplist_live = mplive.get_context()
    listmp_live = mplist_live[0]
    df_distribution_live = mplist_live[1]
    df_distribution_concat = pd.concat([distribution_hist, df_distribution_live]).reset_index(drop=True)

    df_updated_rank = mp.get_dayrank()
    ranking = df_updated_rank[0]
    power = ranking.power
    power1 = ranking.power1
    breakdown = df_updated_rank[1]
    dh_list = ranking.highd
    dl_list = ranking.lowd

    listmp = listmp_hist + listmp_live
    DFList = [group[1] for group in df2.groupby(df2.index.date)]
    df3 = df2[(df2.index >= dates[value[0]]) & (df2.index <= dates[value[1]])]

    fig = go.Figure(data=[go.Candlestick(
        x=df3.index,
        open=df3['Open'],
        high=df3['High'],
        low=df3['Low'],
        close=df3['Close'],
        name=symbol,
        opacity=0.3
    )])

    # ... (retain rest of your TPO plotting logic from previous callback function) ...

    return fig

if __name__ == '__main__':
    app.run_server(port=8000, host='127.0.0.1', debug=True)
