# pylint: disable=broad-except, unspecified-encoding, too-many-locals
"""
 ╔╗ ┬┌┬┐┌─┐┬ ┬┌─┐┬─┐┌─┐┌─┐  ╔╦╗┌─┐─┐ ┬  ╦ ╦─┐ ┬
 ╠╩╗│ │ └─┐├─┤├─┤├┬┘├┤ └─┐   ║║├┤ ┌┴┬┘  ║ ║┌┴┬┘
 ╚═╝┴ ┴ └─┘┴ ┴┴ ┴┴└─└─┘└─┘  ═╩╝└─┘┴ └─  ╚═╝┴ └─
Bitshares Decentralized Exchange User Experience

make requests to kibana to get historical data
and parse the discrete data that is received into candles
"""
# STANDARD MOUDLES
import asyncio
import json
import time
from bisect import bisect

import aiohttp

# BITSHARES DEX UX MODULES
from config import (
    KIBANA_BATCH,
    KIBANA_CANDLE_LIFE,
    KIBANA_CLIP,
    KIBANA_HISTORY,
    KIBANA_OVERLAP,
    KIBANA_SLEEP,
)
from database import Sql
from kibana_queries import kibana_fills, kibana_swaps
from rpc import lookup_account_names
from sql_utils import id_name_lookup, precision
from utilities import it, to_iso_date


# THIRD PARTY MODULES


def make_candles(data, interval):
    """
    make candles from discrete data and perform (FIXME:possibly unnecessary)
    operations on them
    """
    interval = int(interval * 1000)
    # data = [[unix, price, volume], ...]
    data = discrete_to_candles(data, interval)
    # [{}, {}, {}]
    data = {
        "time": [i["unix"] for i in data],
        "high": [i["high"] for i in data],
        "low": [i["low"] for i in data],
        "open": [i["open"] for i in data],
        "close": [i["close"] for i in data],
        "volume": [i["volume"] for i in data],
    }
    return [
        {
            "time": int(unix),
            "open": data["open"][idx],
            "high": data["high"][idx],
            "low": data["low"][idx],
            "close": data["close"][idx],
            "volume": data["volume"][idx],
        }
        for idx, unix in enumerate(data["time"])
    ]


def get_end_unix(sql, market):
    """
    query how old the sql database data is for this market
    """
    query = [{"query": "SELECT end_unix FROM klines where pair=?", "values": (market,)}]
    return sql.execute(query)[0]["end_unix"]


async def get_trade_history(sql, market, start, stop):
    """
    Retrieve the trade history from kibana
    for a specified market within the specified time range.
    Parameters:
    sql (sqlite3 connection object): An established sqlite3 connection object.
    market (str): The market name.
    start (int): Start time in Unix timestamp format.
    stop (int): Stop time in Unix timestamp format.
    Returns:
    list: A list of trade history data, if any was found, else an empty list
    """
    # Check if data is old enough to refresh
    sql_end_unix = get_end_unix(sql, market)
    if stop - sql_end_unix < (KIBANA_CANDLE_LIFE):
        print("DEBUG: KIBANA: candles are not old enough for kibana query")
        return []
    start = start * 1000
    stop = stop * 1000
    final = []
    pdata = {}

    async with aiohttp.ClientSession() as session:
        while True:
            params = (
                kibana_swaps(market, start, stop)
                if market.startswith("1.19.")
                else kibana_fills(market, start, stop)
            )
            # Send the kibana query
            async with session.get(
                "https://es.bts.mobi/bitshares-*/_search",
                data=json.dumps(params),
                headers={"Content-Type": "application/json"},
            ) as response:
                data = await response.json()
                # print(data)
            # Stop if there's no new data,
            # the data is the same as the previous query,
            # or if the batch size has been reached
            if (
                (len(data["hits"]["hits"]) <= 1)
                or (pdata == data)
                or (len(final) >= KIBANA_BATCH)
            ):
                break
            pdata = data
            print(it("purple", f"[DEBUG]: KIBANA: Length of return list: {len(final)}"))
            data = parse_price_history(sql, data)
            final.extend(data)
            stop = sorted(data, key=lambda x: x[0])[0][0]
            # Wait before sending another query
            await asyncio.sleep(KIBANA_SLEEP)
    return final


def format_raw_history_data(data):
    """
    make the returned kibana data indexing for swaps and fills identical
    """
    data = json.loads(
        json.dumps(data)
        .replace("pays", "paid")
        .replace("receives", "received")
        .replace("operation_history.operation_result.keyword", "operation_history.op")
    )
    data = {
        i["sort"][0]: {
            **{
                k: v[0] if isinstance(v, list) else v
                for k, v in json.loads(
                    i["fields"]["operation_history.op"][0].replace("\\", "")
                )[1].items()
                if k in ["paid", "received"]
            },
            "account": i["fields"]["account_history.account.keyword"][0],
            "blocknum": i["fields"]["block_data.block_num"][0],
            "op_id": i["fields"]["account_history.operation_id"][0],
        }
        for i in data["hits"]["hits"]
    }
    return data


def process_operations_history(sql, data):
    """
    Process raw operations history data and convert the amounts to a readable format.
    Args:
        sql (object): SQL connection object to retrieve the precision of an asset.
        data (dict): Raw data of operations history.
    Returns:
        dict: Operations history data with amounts converted to a readable format.
    """
    precision_map = {}
    processed_data = {}
    for timestamp, operation in data.items():
        for direction in ["paid", "received"]:
            if operation[direction]["asset_id"] not in precision_map:
                precision_map[operation[direction]["asset_id"]] = precision(
                    sql, operation[direction]["asset_id"]
                )
        processed_data[timestamp] = {
            **{
                direction: {
                    "amount": float(operation[direction]["amount"])
                    / 10 ** precision_map[operation[direction]["asset_id"]],
                    "asset_id": operation[direction]["asset_id"],
                }
                for direction in ["paid", "received"]
            },
            "account": operation["account"],
            "blocknum": operation["blocknum"],
            "op_id": operation["op_id"],
        }
    return processed_data


def parse_price_history(sql, data):
    """
    Parse the price history of assets in a pool by processing the raw history data,
    converting amounts to float and calculating prices based on the asset pair.
    Parameters:
        sql (object): A SQL connection object.
        data (dict): The raw history data to be processed.
    Returns:
        list: A list of lists containing
        timestamp, price, amount, account, blocknum, and op_id.
    """
    data = format_raw_history_data(data)
    data = process_operations_history(sql, data)
    assets = [
        list(data.values())[0]["paid"]["asset_id"],
        list(data.values())[0]["received"]["asset_id"],
    ]
    assets = [int(i[4:]) for i in assets]
    assets.sort()
    assets = [f"1.3.{str(i)}" for i in assets]
    data2 = []
    for timestamp, operation in data.items():
        price = (
            operation["paid"]["amount"] / operation["received"]["amount"]
            if (
                operation["paid"]["asset_id"] == assets[0]
                and operation["received"]["asset_id"] == assets[1]
            )
            else operation["received"]["amount"] / operation["paid"]["amount"]
            if (
                operation["paid"]["asset_id"] == assets[1]
                and operation["received"]["asset_id"] == assets[0]
            )
            else 0
        )
        if price:
            data2.append(
                [
                    timestamp,
                    price,
                    operation["received"]["amount"],
                    operation["account"],
                    operation["blocknum"],
                    operation["op_id"],
                ]
            )
        else:
            print(timestamp, operation)
    return data2


async def format_onhover(rpc, data, inv):
    """
    acct_name
    acct_id
    trx_id
    blocknum
    unix
    utc
    quote amt
    base amt
    price
    data = [[unix], [price], [volume], [acct], [block], [op]]
    """
    if not data:
        return data
    # eliminate duplicate account IDs in the data
    unique_account_ids = list(set(data[3]))
    lookup = await lookup_account_names(rpc, unique_account_ids)
    # Build the formatted data
    formatted_data = []
    for idx, acc_id in enumerate(data[3]):
        account_name = lookup.get(acc_id, "")
        unix_time = data[0][idx]
        price = 1 / data[1][idx] if inv else data[1][idx]
        volume = data[2][idx]
        op_id = data[5][idx]
        blocknum = data[4][idx]
        base_amt = volume / price
        utc_time = to_iso_date(unix_time)
        entry = f"{account_name}<br>{acc_id}<br>{op_id}<br>{blocknum}<br>"
        entry += f"{unix_time}<br>{utc_time}<br>{volume}<br>{base_amt}<br>"
        entry += f"{price}"
        formatted_data.append(entry)
    return formatted_data


def discrete_to_candles(discrete, size):
    """
    Converts a list of discrete data points into candle data.
    Args:
    - discrete (list): A list of discrete data points in the format
    [[unix_timestamp, price, volume], ...].
    - size (int): The size of the candles to create in seconds.
    Returns:
    - list: A list of candle data in the format
    [{"high": float, "low": float, "open": float,
    "close": float, "unix": int, "volume": float}, ...].
    """
    # Create a dictionary to store the discrete data points
    buckets = {}
    # Calculate the start and stop times for the candles
    start = int(size * (min(d[0] for d in discrete) // size))
    stop = int(size * (max(d[0] for d in discrete) // size))
    # Create a list of breaks to divide the data into candles
    breaks = list(range(start - 2 * size, stop + 2 * size, size))
    # Group the discrete data points into the buckets dictionary
    for event in discrete:
        # Find the correct bucket for the event
        bucket = breaks[bisect(breaks, event[0])]
        # Add the event to the correct bucket
        buckets.setdefault(bucket, []).append(event)
    # Convert the buckets into candle data
    return [
        {
            "high": max(d[1] for d in data),
            "low": min(d[1] for d in data),
            "open": data[0][1],
            "close": data[-1][1],
            "unix": bucket,
            "volume": sum(i[2] for i in data),
        }
        for bucket, data in buckets.items()
    ]


def append_to_candles(data):
    """
    This function updates the historical candlestick data for various time intervals.
    Parameters:
    data (dict): A dictionary of dictionaries with the following keys:
        ["discrete", "c900", "c1800", "c3600", "c7200", "c14400", "c43200", "c86400"]
        The "discrete" key holds a list of discrete data points
        of the format [unix, price, volume].
        The other keys hold historical candlestick data of the given interval.
        Each candlestick is a dictionary with keys:
        ["open", "high", "low", "close", "volume", "time"]
    Returns:
    dict: The updated dictionary of historical candlestick data.
    """
    # Create a dictionary keyed by unix time of all candle sizes in the sql database
    sql_candles_by_unix = {
        k: {i["time"]: i for i in v} for k, v in data.items() if k != "discrete"
    }
    sql_candles_by_unix = {
        i: sql_candles_by_unix[i] for i in sorted(sql_candles_by_unix)
    }
    # Append new data to each candle type
    for interval in [900, 1800, 3600, 7200, 14400, 43200, 86400]:
        # candles is a list of kline dicts parsed from kibana
        period = f"c{str(interval)}"
        if len(data["discrete"]) == 0:
            candles = []
        else:
            candles = make_candles(list(zip(*data["discrete"])), interval)
        candles_by_unix = {i["time"]: i for i in candles}
        candles_by_unix = {i: candles_by_unix[i] for i in sorted(candles_by_unix)}
        # data is a dictionary with keys
        # "c86400", "c43200", "c14400", "c7200", "c3600", "c1800", "c900"
        # Update the object to send back to SQL with the candle data for this interval
        data[period] = [  # Preferably get the candle from kibana, else from SQL
            candles_by_unix.get(unix, sql_candles_by_unix[period].get(unix, {}))
            # For each unix timestamp
            for unix in {
                # A set of unix timestamps among a list of potential duplicates
                kline["time"]
                for kline in (candles + data[period])
            }
        ]
        # Sorted and clipped by KIBANA_CLIP
        data[period] = sorted(data[period], key=lambda x: x["time"])[-1 * KIBANA_CLIP :]
    return data


async def append_to_discrete(rpc, sql, market, data, start, inv):
    """
    This function retrieves recent trade history for a given market,
    appends the latest data to an existing data set
    :param rpc: Connection to the RPC server
    :type rpc: object
    :param sql: Connection to the SQL database
    :type sql: object
    :param market: The market to retrieve trade history for
    :type market: str
    :param data: The existing data set to append to
    :type data: dict
    :return: The updated data set with recent trade history and formatted for display
    :rtype: dict
    """
    stop = time.time() + 10  # always query a few seconds in the future
    startel = time.time()
    # retrieve recent trade history
    recent_data = await get_trade_history(sql, market, start, stop)
    print(time.time() - startel)
    # unzip and add the recent data to the existing data set
    data["discrete"] = [list(i) for i in zip(*data["discrete"])]
    data["discrete"].extend(recent_data[:KIBANA_CLIP])
    data["discrete"] = sorted(data["discrete"], key=lambda x: x[0])[:KIBANA_CLIP]
    data["discrete"] = [list(i) for i in zip(*data["discrete"])]
    if len(data["discrete"]) == 0:
        return data, stop
    # format the data for display
    if len(data["discrete"]) == 6:
        data["discrete"].append(await format_onhover(rpc, data["discrete"], inv))
    else:
        data["discrete"][6] = await format_onhover(rpc, data["discrete"], inv)
    return data, stop


def update_database_candles(sql, market, data, stop):
    """
    Update the klines in the database with new data.
    Parameters:
        sql (object): SQL connection object
        market (str): Market symbol
        data (dict): Dictionary containing the updated data
    Returns:
        None
    """
    # Get the end_unix time from the database
    sql_end_unix = get_end_unix(sql, market)
    # Check if the data is fresh enough to be updated
    if stop - sql_end_unix < (KIBANA_CANDLE_LIFE):
        stop = sql_end_unix
    # Prepare the query for updating the klines
    query = [
        {
            "query": (
                "UPDATE klines "
                "SET end_unix=?, c86400=?, c43200=?, c14400=?, "
                "c7200=?, c3600=?, c1800=?, c900=?, discrete=? "
                "WHERE pair=?"
            ),
            "values": (
                stop,
                json.dumps(data["c86400"]),
                json.dumps(data["c43200"]),
                json.dumps(data["c14400"]),
                json.dumps(data["c7200"]),
                json.dumps(data["c3600"]),
                json.dumps(data["c1800"]),
                json.dumps(data["c900"]),
                json.dumps(data["discrete"]),
                market,
            ),
        }
    ]
    sql.execute(query)


async def fetch_candles(ws, rpc, market, chart_type, candle_size):
    """
    Fetches candles for a given market, with a given chart type, from the SQL database.
    Args:
        rpc (object): The RPC client instance.
        market (str): The market in the format of "<base_symbol>:<quote_symbol>"
        chart_type (str): The chart type that specifies how the candle data is formatted
    Returns:
        dict: The candle data, with keys are period and values being the list of data.
    """

    sql = Sql()
    # Get the market name in the required format
    if not market.startswith("1.19"):
        # the market is asset_id:currency_id for this kline trading pair
        market = ":".join([id_name_lookup(sql, i) for i in market.split(":")])
        # in the database the klines are stored oldest token first, regardless of the user request
        sql_market = ":".join(
            [
                f"1.3.{x}"
                for x in sorted(
                    [int(i[4:]) for i in market.split(":")]
                )
            ]
        )
    else:
        sql_market = market
    # Get the data from the SQL database
    query = [{"query": "SELECT * FROM klines WHERE pair=?", "values": (market,)}]
    result = sql.execute(query)
    # If data exists in the database, use it as the start time, otherwise use 1 year ago
    if result and (result[0]["c86400"] is not None):

        start = result[0]["end_unix"] - KIBANA_OVERLAP
        candles_sql = {
            k: v for k, v in result[0].items() if k.startswith("c") or k == "discrete"
        }
    else:
        # If no data exists, create a new row in the database
        if not result:
            print("Creating a row for", market)
            query = [
                {
                    "query": "INSERT INTO klines (pair, end_unix) VALUES (?, ?)",
                    "values": (market, time.time() - KIBANA_CANDLE_LIFE),
                }
            ]
            sql.execute(query)
        start = time.time() - KIBANA_HISTORY
        candles_sql = {
            "discrete": [],
            **{f"c{i}": [] for i in [900, 1800, 3600, 7200, 14400, 43200, 86400]},
        }
    # Update the candle data in the database
    candles_sql, stop = await append_to_discrete(
        rpc, sql, market, candles_sql, start, market != sql_market
    )
    candles_sql = append_to_candles(candles_sql)
    update_database_candles(sql, market, candles_sql, stop)
    # Rename the fields for compatibility with different charting libraries
    ret = {
        period: candles_sql[period]
        if period == "discrete"
        else format_chart_type(chart_type, candles_sql[period])
        for period in candles_sql
    }

    # JS needs the chart_type and candle_size
    ret = [
        chart_type,
        ret[candle_size],
        candle_size,
    ]

    if market != sql_market:
        # for idx, item in enumerate(ret[1][0]):
        #     ret_new[0].append(item)
        #     ret_new[1].append(1/ret[1][1][idx])
        #     ret_new[2].append(ret[1][2][idx])
        #     ret_new[3].append(ret[1][3][idx])
        #     ret_new[4].append(ret[1][4][idx])
        #     ret_new[5].append(ret[1][5][idx])
        #     ret_new[6].append(ret[1][6][idx])
        ret[1] = (
            # for discrete we just invert the price; idx=1
            [
                list(i)
                for i in list(
                    zip(
                        [
                            [j if idx != 1 else 1 / j for idx, j in enumerate(i)]
                            for i in list(zip(ret[1]))
                        ]
                    )
                )
            ]
            if candle_size == "discrete"
            # for non-discrete we invert everything except time and volume
            else [
                {
                    k: (1 / v if (("time" not in k) and ("volume" not in k)) else v)
                    for k, v in i.items()
                }
                for i in ret[1]
            ]
        )

    await ws.send_media({"payload": ret, "resource": "candles"})


def format_chart_type(chart_type, data):
    """
    Rename some fields for compatibility with different charting libraries
    """
    ret = None
    if chart_type == "candle":
        # Regular candles require milliseconds to second conversion
        ret = [
            {
                "time": item["time"] / 1000,
                **{k: v for k, v in item.items() if k != "time"},
            }
            for item in data
        ]
    elif chart_type == "line":
        # Remove hlocv and replace with "value" as copy of "close"
        ret = [{"time": item["time"] / 1000, "value": item["close"]} for item in data]
    elif chart_type == "advanced":
        # Add timestamp column as copy of time
        ret = [
            {
                "timestamp": item["time"],
                **{k: v for k, v in item.items() if k != "time"},
            }
            for item in data
        ]
    # Sort ret by time (or timestamp)
    return sorted(
        ret,
        key=lambda x: x["time"] if chart_type in ["candle", "line"] else x["timestamp"],
    )
