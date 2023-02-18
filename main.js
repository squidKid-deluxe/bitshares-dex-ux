/*
 ╔╗ ┬┌┬┐┌─┐┬ ┬┌─┐┬─┐┌─┐┌─┐  ╔╦╗┌─┐─┐ ┬  ╦ ╦─┐ ┬
 ╠╩╗│ │ └─┐├─┤├─┤├┬┘├┤ └─┐   ║║├┤ ┌┴┬┘  ║ ║┌┴┬┘
 ╚═╝┴ ┴ └─┘┴ ┴┴ ┴┴└─└─┘└─┘  ═╩╝└─┘┴ └─  ╚═╝┴ └─
Bitshares Decentralized Exchange User Experience
*/

/* MARKET CHARTING */
function invert_market() {
    pair = pair.split(":").reverse().join(":");
    asset = pair.split(":")[0];
    currency = pair.split(":")[1];
    use_inv = !use_inv;
    socketResource.send(JSON.stringify({"resource":"book", "pair":pair, "contract":contract}));
    socketResource.send(JSON.stringify({"resource":"ticker", "pair":pair, "contract":contract}));
    socketResource.send(JSON.stringify({"resource":"candles", "chart_type":"line", "candle_size":"c86400", "contract":contract, "pair":pair}));
}

function log_button() {
    use_log = !use_log;
    //full_update();
    sendChartReq();
}

function sendChartReq() {
    /**
     * Sends a request to get more candle data for a chart.
     * @return {void}
     */
    var candleSize = document.querySelector('input[name="options"]:checked')
        .value;
    var chartType = document.querySelector('input[name="candles"]:checked')
        .value;
    console.log(candleSize, chartType);
    socketResource.send(
        JSON.stringify(
            {
                "resource":"candles",
                "candle_size":candleSize,
                "chart_type": chartType,
                "contract":contract
            }
            )
        );
}

function chartHandler(candleData) {
    /**
     * Handles the received candle data and plots it on the correct chart.
     * Determine which plotting function to use based on the candle data type
     * Schedule another request to be sent after some time
     * @param {Array} candleData - An array containing the candle data to be plotted.
     * @return {void}
     */
    console.log(candleData);
    if (candleData[2] !== "discrete") {
        if (candleData[0] === "advanced") {
            advanced(candleData[1]);
        } else {
            TradingViewLightWeight(candleData[1], candleData[0]);
        }
    } else {
        plotlyChart(candleData);
    }
    setTimeout(sendChartReq, 3600000);
}


function TradingViewLightWeight(candleData, chartType) {
    /**
     * Plot candle or line chart data; all time scales except discrete
     *
     * Tradingview LightweightCharts Library
     *
     * @param {Array} candleData - The data to be plotted
     * @param {String} chart_type - The type of chart to be plotted (candle or line)
     */
    console.log(candleData);
    const chart = LightweightCharts.createChart("chart-window", {
        height: 550,
        layout: {
            backgroundColor: "#070e20",
            textColor: "rgba(255, 255, 255, 0.9)",
            background: {
                type: 'solid',
                color: 'transparent'
            },
        },
        grid: {
            vertLines: {
                color: "rgba(197, 203, 206, 0)",
            },
            horzLines: {
                color: "rgba(197, 203, 206, 0)",
            },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },
        rightPriceScale: {
            borderColor: "rgba(197, 203, 206, 0.8)",
        },
        timeScale: {
            borderColor: "rgba(197, 203, 206, 0.8)",
        },
    });
    let candleSeries;
    if (chartType === "candle") {
        candleSeries = chart.addCandlestickSeries({
            upColor: "#26de81",
            downColor: "#ff231f",
            borderDownColor: "#ff231f",
            borderUpColor: "#26de81",
            wickDownColor: "#ff231f",
            wickUpColor: "#26de81",
        });
    } else {
        const color = candleData[0].value > candleData[candleData.length - 1]
            .value ? '255, 0, 0' : '0, 255, 0';
        candleSeries = chart.addAreaSeries({
            topColor: `rgba(${color}, 0.56)`,
            bottomColor: `rgba(${color}, 0.04)`,
            lineColor: `rgba(${color}, 1)`,
            lineWidth: 2,
        });
    }
    candleSeries.applyOptions({
        priceFormat: {
            type: "price",
            precision: 6,
            minMove: 0.000001,
        },
    });

    candleSeries.priceScale('right').applyOptions({
		mode: use_log ? 1 : 0,
		invertScale: false,
	});
    /* FIXME LOGO WATERMARK */
    // const container = document.getElementById('chart_window');
    // const background = document.createElement('div');
    // // place below the chart
    // // background.style.zIndex = ;
    // background.style.position = 'absolute';
    // // set size and position to match container
    // background.style.inset = '0px';
    // background.style.top = '-400px';
    // background.style.backgroundSize = '50%';
    // background.style.backgroundImage = `url("/assets/bitshares.png")`;
    // background.style.backgroundRepeat = 'no-repeat';
    // background.style.backgroundPosition = 'center';
    // background.style.opacity = '0.1';
    // container.appendChild(background);
    candleSeries.setData(candleData);
}


function advanced(candleData) {
    /**
     * plot "advanced" chart data; all time scales except discrete
     *
     * KlineCharts Library
     *
     * @param {Array} candleData - The data to be plotted
     */

    // FIXME implement "styles.yAxis.type:log" in verstion 7.3.1+
    let chart;
    console.log(use_log)
    let logScale = use_log ? "log" : "normal";
    console.log(logScale)
    klinecharts.dispose('kline-window');
    //try {klinecharts.dispose('kline-window')} catch {};
    chart = klinecharts.init('kline-window', {"styles":{"yAxis":{"type":logScale}}});



    //chart.Styles.yAxis = {"type": logScale};
    if (createIndicators) {
        chart.createIndicator('MA', false, {
            id: 'candle_pane'
        });
        chart.createIndicator('VOL');
        createIndicators = false;
    }
    console.log(chart);
    chart.applyNewData(candleData);
}


function plotlyChart(candleData) {
    /*
     * plot "discrete" chart with irregular timestamps
     * use different chart types for each
     *
     *
     * line = line
     * candle = dashed marker only
     * advanced = dot with data on hover over
     *
     * Plotly Library
     *
     * @param {Array} candleData - The data to be plotted
     */
    var type = candleData[0];
    if (type === "advanced") {
        let chart = document.getElementById("chart-window")
        chart.innerHTML = "";
        chart.style.display = "block";
        chart = document.getElementById("kline-window")
        chart.style.display = "none";
    }
    var bidp = candleData[1][0];
    var bidv = candleData[1][1];
    var maxp = Math.max.apply(Math, bidp);
    var minp = Math.min.apply(Math, bidp);
    var maxv = Math.max.apply(Math, bidv);
    var data = [{
        x: bidp,
        y: bidv,
        text: type === "advanced" ? candleData[1][6] : [],
        mode: type !== "line" ? "markers" : "line",
        "type": type === "candle" ? "line" : "scatter",
        showlegend: false,
        name: "",
        marker: {
            size: type === "candle" ? 4 : 1,
            symbol: type === "candle" ? "line-ew-open" : ""
        },
        line: {
            color: bidv[0] < bidv.at(-1) ? '#00FF00' : '#FF0000',
            width: type === "line" ? 1 : 0,
        },
    }];
    console.log(use_log);
    var layout = {
        xaxis: {
            range: [minp, maxp],
            title: "",
            color: "#fff",
            autorange: true
        },
        yaxis: {
            range: [0, maxv],
            title: "",
            color: "#fff",
            type: use_log ? "log" : "linear",
            autorange: true
        },
        plot_bgcolor: "#131722",
        paper_bgcolor: "#131722",
        margin: {
            l: 30,
            r: 30,
            b: 50,
            t: 30,
            pad: 20,
        },
    };
    Plotly.newPlot("chart-window", data, layout, {
        displayModeBar: false
    });
}


/* MARKET DEPTH */
function plotDepth(event) {
    /**
     * depth of market chart
     *
     * Plotly Library
     *
     * @param {Array} event - the orderbook to be plotted on the chart
     */
    const bidp = event.bid.price;
    const bidv = event.bid.volume;
    const askp = event.ask.price;
    const askv = event.ask.volume;
    // Use destructuring assignment to combine the arrays into one.
    const prices = [...bidp, ...askp];
    const volumes = [...bidv, ...askv];
    const maxp = Math.max(...prices);
    const minp = Math.min(...prices);
    const maxv = Math.max(...volumes);
    // Use object destructuring to define the properties of the line object.
    const bidLine = {
        x: bidp,
        y: bidv,
        mode: "lines",
        fill: "tozeroy",
        showlegend: false,
        name: "",
        line: {
            shape: "hv",
            color: "#26de81",
            width: 1
        }
    };
    const askLine = {
        x: askp,
        y: askv,
        mode: "lines",
        fill: "tozeroy",
        showlegend: false,
        name: "",
        line: {
            shape: "hv",
            color: "#ff231f",
            width: 1
        }
    };
    const data = [bidLine, askLine];
    const layout = {
        xaxis: {
            range: [minp, maxp],
            title: "",
            color: "#fff"
        },
        yaxis: {
            range: [0, maxv],
            title: "",
            color: "#fff",
            showticklabels: false
        },
        plot_bgcolor: "#131722",
        paper_bgcolor: "#131722",
        margin: {
            l: 30,
            r: 30,
            b: 50,
            t: 30,
            pad: 20
        }
    };
    Plotly.newPlot("myPlot", data, layout, {
        displayModeBar: false
    });
}


/* ORDERBOOK */
function bookClick(price, amount) {
    /*
     * do something with the price and amount from a clicked order
     */
    let assetAmountInput = document.querySelector("#assetAmount");
    let currencyAmountInput = document.querySelector("#currencyAmount");
    // update the input elements
    assetAmountInput[0].value = amount / price;
    currencyAmountInput[0].value = amount;
    assetAmountInput[1].value = amount / price;
    currencyAmountInput[1].value = amount;
}
/* MARKET PICKER */
function book(base, market) {
    /*
     * when a search result is clicked on, bring up the order book
     * for that result by redirecting to the page with the proper pair
     * note this will be used for both pools and orderbooks
     * for pools the contract will be 1.19.x or for orderbook contract is always 1.0.0
     */
    let letpair = pair;
    if ((base === undefined) && (baseAssetForBook === undefined)) {
        base = asset;
        market = currency;
        baseAssetForBook = asset;
        currencyForBook = currency;
    } else {
        if (base === undefined) {
            // when base is unavailable default
            base = baseAssetForBook;
            market = currencyForBook;
        } else {
            if (!base.includes("1.19.")) {
                pair = base + "_" + market;
                letpair = base + "_" + market;
                asset = base;
                currency = market;
                contract = "1.0.0";
            } else {
            console.log(market);
                pair = market;
                letpair = market;
                asset = market.split(":")[0];
                currency = market.split(":")[1];
                contract = base;
            }
            full_update();

            // if (base.includes("1.19.")) {
            //     window.location.href = "exchange.html?pair=" + market + "&contract=" + base;
            // } else {
            //     window.location.href = "exchange.html?pair=" + base + "_" + market + "&contract=1.0.0";
            // }
        }
    }
//    let baseAsset = base;
//    let marketAsset = market
    // let baseAsset = base || baseAssetForBook;
    // let marketAsset = market || currencyForBook;
    // // If `base` is not undefined, redirect to the exchange page with the proper pair
    // if (base) {
    //     window.location.href = `exchange.html?pair=${baseAsset}_${marketAsset}`;
    // }
    // Update currency and pair
//    currency = marketAsset;
//`${base}:${market}`
    socketResource.send(JSON.stringify({"resource":"book", "pair":pair, "contract":contract}));
}


function reList(search) {
    /*
     * re-send a list assets request and add the event listener
     * all market picker requests pass through here to websocket
     */
    var obj = firstChoice ? "pick-a" : "market-pairs";
    var params = {
        "resource":"list_assets",
        "search":search,
        "assetA":assetA,
        "useMPA":useMPA,
        "useLPT":useLPT,
        "useUIA":useUIA,
        "usePool":usePool,
        "firstChoice":firstChoice,
        "useBTS":useBTS,
    };
    socketResource.send(JSON.stringify(params));
}


function firstSearch(token) {
    /*
    * The first round of market picker search
    */
    firstChoice = !firstChoice;
    assetA = token;
    document.getElementById("coinsearch").value = "USD";
    onEnter("wss");
}


function onEnter(refresh) {
    /*
     * set the search results to `Loading`
     * capture the search query from the search box
     * perform a WS request to the falcon server
     * wait for the response and put the response in the search result box.
     */
    if ((event && event.keyCode == 13) || refresh) {
        var obj = firstChoice ? "pick-a" : "market-pairs";
        var notobj = firstChoice ? "market-pairs" : "pick-a";
        document.getElementById(notobj == "market-pairs" ? "search-results" : notobj).style.display = "none";
        document.getElementById(obj == "market-pairs" ? "search-results" : obj).style.display = "block";
        console.log(obj);
        document.getElementById(obj).innerHTML = "<tbody><tr><td>Loading...</td></tr></tbody>";
        console.log(document.getElementById("coinsearch").value);
        reList(document.getElementById("coinsearch").value);//.trim()
    }
}


function clickFilter() {
    /*
     * toggle filtering of mpas from search results
     */
    useBTS = false;
    useMPA = false;
    useUIA = false;
    useLPT = false;
    usePool = false;
    window["use" + document.querySelector('input[name="filter"]:checked').value] = true;
    onEnter("wss");
}

/* TICKER */
function sendTickerReq() {
    socketResource.send(JSON.stringify({"resource":"ticker", "pair":pair, "contract":contract}));
}


/* INITALIZATION */
function initPair(pairReq, assetReq, currencyReq, contractReq) {
    const isPairValid = typeof pairReq === 'string' && pairReq.length > 0;
    const isAssetValid = typeof assetReq === 'string' && assetReq.length > 0;
    const isCurrencyValid = typeof currencyReq === 'string' && currencyReq
        .length > 0;
    if (!isPairValid || !isAssetValid || !isCurrencyValid) {
        console.error('Invalid arguments provided to initPair');
        return;
    }
    pair = pairReq;
    asset = assetReq;
    currency = currencyReq;
    contract = contractReq;
    initializeWebSockets();
}


function full_update() {
    console.log(pair, contract);
    socketResource.send(JSON.stringify({"resource":"book", "pair":pair, "contract":contract}));
    socketResource.send(JSON.stringify({"resource":"ticker", "pair":pair, "contract":contract}));
    socketResource.send(JSON.stringify({"resource":"blocknum"}));
    socketResource.send(JSON.stringify({"resource":"candles", "chart_type":"line", "candle_size":"c86400", "contract":contract, "pair":pair}));
    onEnter("wss");
}



function initializeWebSockets() {
  socketResource = new WebSocket('ws://127.0.0.1:8001/?resource=book&pair=' + pair + "&contract=" + contract);
  
    socketResource.addEventListener('message', (event) => {
    const data = JSON.parse(event.data);
    switch (data.resource) {
      case 'book':
        handleOrderbookMessage(data.payload);
        break;
      case 'blocknum':
        handleBlocknumMessage(data.payload);
        break;
      case 'ticker':
        handleTickerMessage(data.payload);
        break;
      case 'list_assets':
        handleMarketPairsMessage(data.payload);
        break;
      case 'candles':
        handleCandlesMessage(data.payload);
        break;
      default:
        // Handle unknown message resources
        console.log(data.resource);
        break;
    };
  });
    socketResource.addEventListener('open', (event) => {
        full_update()
    });
};



/* HANDLE MESSAGE */
function handleOrderbookMessage(event) {
    /*
    *
    */
    document.getElementById("orderbook").innerHTML =
        "<tbody><tr><td>Loading...</td></tr></tbody>";
    const bookElement = document.getElementById("orderbook");
    bookElement.innerHTML = event.book;
    const redBook = document.getElementById("red");
    redBook.scrollTop = redBook.scrollHeight;
    plotDepth(event);
    document.querySelectorAll("#asset")[0].value = asset;
    document.querySelectorAll("#currency")[0].value = currency;
    document.querySelectorAll("#asset")[1].value = asset;
    document.querySelectorAll("#currency")[1].value = currency;
    try {
        clearTimeout(booktimeout);
    } catch (e) {
        console.log(e);
    };
    booktimeout = setTimeout(book, 10000);
};
function handleBlocknumMessage(event) {
    /*
    *
    */
    document.getElementById("blocknum").innerHTML = event;
    setTimeout(function() {socketResource.send(JSON.stringify({"resource":"blocknum"}));}, 1000)
};
function handleTickerMessage(event) {
    /*
    *
    */
    document.getElementById("ticker").innerHTML = JSON.stringify(event);
    setTimeout(sendTickerReq, 10000);
};
function handleMarketPairsMessage(event) {
    /*
    *
    */
    document.getElementById(firstChoice ? "pick-a" : "market-pairs")
        .innerHTML = event;
};
function handleCandlesMessage(event) {
    /*
    *
    */
    var chart_type=document.querySelector('input[name="candles"]:checked').value;
    if (chart_type === "advanced") {
        var chart = document.getElementById("chart-window")
        chart.innerHTML = "";
        chart.style.display = "none";
        var chart = document.getElementById("kline-window")
        chart.style.display = "block";
        //klinecharts.dispose('kline-window');
    } else {
        var chart = document.getElementById("chart-window")
        chart.innerHTML = "";
        chart.style.display = "block";
        var chart = document.getElementById("kline-window")
        chart.style.display = "none";
    };
    // console.log(JSON.parse(event.data))
    chartHandler(event);
};


/* GLOBAL VARIABLES */
var assetA = "BTC";
var firstChoice = true;
var useMPA = true;
var useLPT = false;
var useUIA = false;
var usePool = false;
var useBTS = false;
var pair = "";
var currency = "";
var asset = "";
var contract = "";
var baseAssetForBook;
var currencyForBook;
var booktimeout;
var socketResource;
var createIndicators = true;
var use_log = false;
var use_inv = false;
