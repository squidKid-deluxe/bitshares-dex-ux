# BITSHARES DEX UX

## Bitshares Decentralized Exchange User Experience

A framework for server side rendering DEX UI/UX in Python with minimal dependencies

###  Release

Developer Pre-Alpha

### Known Bugs:

Yes

### Operating System

Linux compliant; other operating systems not tested

### Features:

Pools and Limit Order Books on one interface

- Market Picker
- Kline Charts
- Depth of Market
- Order Book

### TODO:

- Authentication, Beet?
- Buy/Sell/Cancel 
- Send and Gateway Ops
- Market History
- Open Orders
- Fill Orders
- Cancel Orders
- Stake / Unstake from Pool

### Stack:

- Socketify
- Falcon
- PyPy
- Aiohttp
- Sqlite
- Bitshares Elastic Search Node
- Bitshares API Node
- Native JS
- HTML
- Crypo CSS
- Beet?

### Install:

[Install pypy3.9](https://www.pypy.org/download.html)

Create a symlink to your PATH:

`sudo ln -s path/to/pypy3.9/binary "/bin/pypy3.9"`

Then run:

`pypy3.9 -m pip install -r requirements.txt` 

### Usage:

Start the data server:

```
pypy3.9 -m socketify falcon_app:app
```

In a separate terminal, run 

```
pypy3.9 -m socketify falcon_website:ui
```

to start the website server.

Then, open `127.0.0.1:8000/index.html` in your favorite web browser.

Click `Trade Now`

NOTE: Tested with Brave and Firefox browsers, others may or may not work.

### JavaScript Dependencies:

[Plotly](https://plotly.com/)
[TradingView LightWeightCharts](https://www.tradingview.com/lightweight-charts/)
[KLineChart](https://klinecharts.com/)

### Python Dependencies:

```
aiohttp[speedups]~=3.8.4
falcon~=3.1.1
socketify
```
