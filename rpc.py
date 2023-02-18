# pylint: disable=broad-except
"""
 ╔╗ ┬┌┬┐┌─┐┬ ┬┌─┐┬─┐┌─┐┌─┐  ╔╦╗┌─┐─┐ ┬  ╦ ╦─┐ ┬
 ╠╩╗│ │ └─┐├─┤├─┤├┬┘├┤ └─┐   ║║├┤ ┌┴┬┘  ║ ║┌┴┬┘
 ╚═╝┴ ┴ └─┘┴ ┴┴ ┴┴└─└─┘└─┘  ═╩╝└─┘┴ └─  ╚═╝┴ └─
Bitshares Decentralized Exchange User Experience
"""

# STANDARD MOUDLES
import asyncio
import random
import time
from math import ceil

import aiohttp

import contextlib

# BITSHARES DEX UX MODULES
from sql_utils import precision
from utilities import chunks, it, to_iso_date, get_nonce
from config import RPC_USE_INTERNAL_HANDLER

NODES = [
    "wss://api.bts.mobi/wss",
    "wss://newyork.bitshares.im/wss",
    # "wss://bts.open.icowallet.net/ws",
    # "wss://api.dex.trading",
    # "wss://eu.nodes.bitshares.ws/wss",
    # "wss://dex.iobanker.com/wss",
    # "wss://api.bitshares.bhuz.info",
    # "wss://public.xbts.io/ws",
    # "wss://api-us.61bts.com",
    # "wss://btsws.roelandp.nl/ws",
    # "wss://node.xbts.io/wss",
    # "wss://hongkong.bitshares.im",
    # "wss://bts.mypi.win/wss",
    # "wss://cloud.xbts.io/ws",
    # "wss://api.bitshares.info",
    # "wss://api.61bts.com",
    # "wss://api.btslebin.com/wss",
    # "wss://api.bts.btspp.io:10100/ws",
    # "wss://singapore.bitshares.im/ws",
]


# async def main():
#     rpc = await wss_handshake()
#     print(await rpc_get_objects(rpc, ["1.2.0"]))
#     rpc.close()
#
# if __name__ == "__main__":
#     asyncio.run(main())
async def wss_handshake():
    """
    Create a websocket handshake
    """
    with contextlib.suppress(AttributeError):
        await wss_handshake.session.close()
    while True:
        try:
            node = random.choice(NODES)
            start = time.time()
            print("await websocket connect", node)
            # rpc = await websockets.connect(node, open_timeout=10)
            wss_handshake.session = aiohttp.ClientSession()
            rpc = await wss_handshake.session.ws_connect("wss://api.bts.mobi/wss")
            # rpc = wss(node, timeout=3)
            if time.time() - start < 100:
                print("connected, MOON!")
                break
            else:
                print(it("orange", "websocket connection timed out"))
        except Exception as error:
            print(
                it(
                    "orange",
                    "Websocket handshake failed with error '"
                    + str(error)
                    + "'. Trying again...",
                )
            )
    return rpc


async def wss_query(rpc, params):
    """
    Send and receive websocket requests
    """
    nonce = get_nonce()
    try:
        wss_query.nonce_dict
    except AttributeError:
        wss_query.nonce_dict = {}

    query = {"method": "call", "params": params, "jsonrpc": "2.0", "id": nonce}
    i = 0
    ret = {}
    while True:
        try:
            try:
                await rpc.send_json(query)
                async for msg in rpc:
                    resp = msg.json()
                    wss_query.nonce_dict[int(resp["id"])] = resp
                    if nonce in wss_query.nonce_dict:
                        ret = wss_query.nonce_dict.pop(nonce)
                        break
            except Exception as error:
                if "Concurrent call to receive() is not allowed" not in str(error):
                    raise
                await asyncio.sleep(0.01)
                continue
            break
        except Exception as error:
            print(
                it("orange", "Websocket query failed with error '" + str(error) + "'")
            )
            if not RPC_USE_INTERNAL_HANDLER:
                raise
            await asyncio.sleep((i / 2) ** 2)
            i += 1
            if i % 3 == 0:
                print(
                    it(
                        "purple",
                        "Websocket query failed 3 times in a row, re-connecting...",
                    )
                )
                await rpc.close()
                rpc = await wss_handshake()
            if i % 15 == 0:
                print(
                    it(
                        "red",
                        "Websocket query failed 15 times, quitting for server"
                        " reconnect...",
                    )
                )
                ret = {}
                break
    try:
        ret = ret["result"]  # if there is result key take it
    except Exception:
        print(ret)
    return ret


async def lookup_account_names(rpc, account_ids):
    chunked_ids = chunks(account_ids, ceil(len(account_ids) / 100))
    lookup = {}
    for chunk in chunked_ids:
        lookup = {
            **lookup,
            **dict(
                zip(
                    chunk,
                    [i["name"] for i in (await rpc_get_objects(rpc, chunk)).values()],
                )
            ),
        }
    return lookup


async def rpc_get_objects(rpc, object_ids):
    """
    Return data about objects in 1.7.x, 2.4.x, 1.3.x, etc. format
    """
    ret = await wss_query(rpc, ["database", "get_objects", [object_ids]])
    print(ret, len(ret))
    if isinstance(ret, dict):
        ret = [ret]
    return {object_ids[idx]: item for idx, item in enumerate(ret) if item is not None}


async def rpc_ticker(rpc, pair):
    """
    RPC the latest ticker price
    ~
    :RPC param base: symbol name or ID of the base asset
    :RPC param quote: symbol name or ID of the quote asset
    :RPC returns: The market ticker for the past 24 hours
    """
    asset, currency = pair.split(":")
    return await wss_query(rpc, ["database", "get_ticker", [currency, asset, False]])


async def get_max_object(rpc, space):
    """
    get the maximum object id within this instance space
    using a modified exponential search
    allow for missing values
    """
    power = 5
    max_object = 0
    while True:
        ids = [f"{space}{int(max_object + i ** power)}" for i in range(1, 777)]
        try:
            objects = [
                int(v["id"].split(".")[2])
                for v in (await rpc_get_objects(rpc, ids)).values()
                if v is not None
            ]
            max_object = max(objects)
            if len(objects) == 1:
                power -= 0.5
            if power < 1:
                break
        except Exception:
            power -= 0.5
    return max_object


async def get_liquidity_pool_volume(rpc, pools):
    """
    get the sum amount a volume for a given set of liquidity pools
    """
    return {
        i["id"]: int(i["statistics"]["_24h_exchange_a2b_amount_a"])
        + int(i["statistics"]["_24h_exchange_b2a_amount_a"])
        for i in await wss_query(
            rpc, ["database", "get_liquidity_pools", [pools, False, True]]
        )
    }


async def base_quote(data):
    """
    convert graphene prices to human readable
    """
    # calculate the base feed amount in human terms
    base = int(data["base"]["amount"])
    base_asset_id = data["base"]["asset_id"]
    base_precision = precision("", base_asset_id)
    # calculate the quote data amount in human terms
    quote = int(data["quote"]["amount"])
    quote_asset_id = data["quote"]["asset_id"]
    quote_precision = precision("", quote_asset_id)
    # convert fractional human price to floating point
    return (base / 10**base_precision) / (quote / 10**quote_precision)


async def rpc_get_feed(rpc, data_id):
    """
    return the oracle feed price for a given MPA
    """
    # given the bitasset_data_id, get the median feed price
    feed = (await rpc_get_objects(rpc, [data_id]))[data_id]["median_feed"][
        "settlement_price"
    ]
    return base_quote(feed)


async def rpc_market_history(rpc, currency_id, asset_id, period, start, stop):
    print(
        to_iso_date(start),
        to_iso_date(stop),
    )
    return await wss_query(
        rpc,
        [
            "history",
            "get_market_history",
            [
                currency_id,
                asset_id,
                period,
                to_iso_date(start),
                to_iso_date(stop),
            ],
        ],
    )


async def rpc_book(rpc, pair, depth=3):
    """
    Remote procedure call orderbook bids and asks
    ~
    :RPC param str(base): symbol name or ID of the base asset
    :RPC param str(quote): symbol name or ID of the quote asset
    :RPC param int(limit): depth of the order book to retrieve (max limit 50)
    :RPC returns: Order book of the market
    """
    asset, currency = pair.split(":")
    order_book = await wss_query(
        rpc,
        [
            "database",
            "get_order_book",
            [currency, asset, depth],
        ],
    )
    asks = []
    bids = []
    for i, _ in enumerate(order_book["asks"]):
        price = float(order_book["asks"][i]["price"])
        if price == 0:
            print(f"WARN: zero price in asks {pair}")
        asset_volume = float(order_book["asks"][i]["quote"])
        currency_volume = float(order_book["asks"][i]["quote"]) * price
        asks.append((price, asset_volume, currency_volume))
    for i, _ in enumerate(order_book["bids"]):
        price = float(order_book["bids"][i]["price"])
        if price == 0:
            print(f"WARN: zero price in bids {pair}")
        asset_volume = float(order_book["bids"][i]["quote"])
        currency_volume = float(order_book["bids"][i]["quote"]) * price
        bids.append((price, asset_volume, currency_volume))
    # Sort the order book by price
    asks.sort(key=lambda x: x[0], reverse=False)
    bids.sort(key=lambda x: x[0], reverse=True)
    return {"asks": asks, "bids": bids}


async def lookup_asset_symbol(rpc, asset_name):
    """
    lookup an asset id from as asset name
    """
    return (await wss_query(rpc, ["database", "lookup_asset_symbols", [[asset_name]]]))[
        0
    ]["id"]


async def get_pools_by_asset(rpc, token, a_or_b):
    """
    get the ids of liquidity pools from their assets
    """
    query = ["database", f"get_liquidity_pools_by_asset_{a_or_b}", [token]]
    # print(query)
    return await wss_query(rpc, query)


async def list_assets(rpc, asset, depth=10):
    """
    perform list_asses query to blockchain
    """
    # typing because why not
    return await wss_query(rpc, ["database", "list_assets", [str(asset), int(depth)]])


async def main():
    rpc = await wss_handshake()
    print(await rpc_get_objects(rpc, ["1.2.0"]))
    await rpc.close()


if __name__ == "__main__":
    asyncio.run(main())
