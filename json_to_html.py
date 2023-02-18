# pylint: disable=broad-except, unspecified-encoding, too-many-arguments, too-many-locals, too-many-statements
"""
 ╔╗ ┬┌┬┐┌─┐┬ ┬┌─┐┬─┐┌─┐┌─┐  ╔╦╗┌─┐─┐ ┬  ╦ ╦─┐ ┬
 ╠╩╗│ │ └─┐├─┤├─┤├┬┘├┤ └─┐   ║║├┤ ┌┴┬┘  ║ ║┌┴┬┘
 ╚═╝┴ ┴ └─┘┴ ┴┴ ┴┴└─└─┘└─┘  ═╩╝└─┘┴ └─  ╚═╝┴ └─
Bitshares Decentralized Exchange User Experience

Perform data wrangling server side before responding to the client
This consists of converting JSON into HTML
that can be easily inserted with JS
"""

# BITSHARES DEX UX MODULES
from rpc import rpc_ticker
from utilities import no_sci
import asyncio


async def orderbook_to_html(rpc, data, asset, currency, pool_data, pair):
    """
    convert json orderbook data to an html orderbook ux
    """
    book_html = build_table_header(asset, currency)
    for color in ["red", "green"]:
        bidask = "bids" if color == "green" else "asks"
        tsum = sum(i[2] for i in data[bidask])
        csums = [0]
        csums.extend(bid[2] + csums[-1] for bid in data[bidask])
        csums = csums[1:]
        book_html += build_table_body(color, data, bidask, tsum, csums)
        if color == "red":
            book_html += await build_last_price_section(
                rpc, pool_data, pair, asset, currency
            )
    final_bids = []
    csum = 0
    for bid in data["bids"]:
        csum += bid[2]
        final_bids.append([csum, bid[0]])
    final_asks = []
    csum = 0
    for ask in data["asks"]:
        csum += ask[2]
        final_asks.append([csum, ask[0]])
    # data = {
    #     "book": book_html,
    #     "bid": {
    #         "volume": [volume for volume, price in final_bids],
    #         "price": [price for volume, price in final_bids],
    #     },
    #     "ask": {
    #         "volume": [volume for volume, price in final_asks[::-1]],
    #         "price": [price for volume, price in final_asks[::-1]],
    #     },
    # }

    data = {
        "book": book_html,
        "bid": dict(
            zip(
                ["volume", "price"],
                list(zip(*final_bids)),
            )
        ),
        "ask": dict(
            zip(
                ["volume", "price"],
                list(zip(*final_asks)),
            )
        ),
    }
    return data


def build_table_header(asset, currency):
    """
    orderbook header helper function
    """
    return (
        f"<thead><tr><th>Price({asset})</th>"
        f"<th>Amount({currency})</th>"
        f"<th>Total({currency})</th></tr></thead>"
    )


def build_table_body(color, data, bidask, tsum, csums):
    """
    orderbook table body helper function
    """
    html = f"<tbody id='{color}'>"
    for idx, bid in enumerate(data[bidask][:: (-1 if bidask == "asks" else 1)]):
        csum = csums[-idx - 1] if color == "red" else csums[idx]
        html += build_table_row(color, bid, csum, tsum)
    html += "</tbody>"
    return html


def build_table_row(color, bid, csum, tsum):
    """
    orderbook table row helper function
    """
    html = f'<tr class="{color}-bg-'
    html += str(int((csum / tsum) * 100))
    html += f'" onclick="book_click({bid[0]}, {csum})">'
    html += f'<td class="{color}">'
    html += no_sci(bid[0]).ljust(16, "&").replace("&", "&nbsp;")
    html += "</td>"
    html += "<td>"
    html += no_sci(bid[2]).ljust(16, "&").replace("&", "&nbsp;")
    html += "</td>"
    html += "<td>"
    html += no_sci(csum).ljust(16, "&").replace("&", "&nbsp;")
    html += "</td>"
    html += "</tr>"
    return html


async def build_last_price_section(rpc, pool_data, pair, asset, currency):
    """
    orderbook latest price helper function
    """
    ticker = (
        {
            "percent_change": 0,
            "base_volume": 0,
            "latest": pool_data["balance_a"] / pool_data["balance_b"],
        }
        if pool_data
        else await rpc_ticker(rpc, pair)
    )
    last_price = no_sci(float(ticker["latest"]))
    volume = no_sci(ticker["base_volume"])
    percent_change = no_sci(ticker["percent_change"])
    html = '<tbody class="ob-heading"><tr><td><span>Last Price</span>'
    color = "red" if float(ticker["percent_change"]) < 0 else "green"
    html += f"<span class='{color}'>{last_price} {asset}</span></td>"
    html += f"<td><span>{currency}</span>{volume}</td>"
    html += (
        f"<td class='{color}'><span>Change</span>{percent_change}%</td></tr></tbody>"
    )

    return html


#########################################
async def create_asset_list(rpc, data, first_choice, base_asset, fast):
    list_of_assets = []
    for result in data:
        if result["symbol"] not in [i["symbol"] for i in list_of_assets]:
            # get_ticker for each pair
            if (not fast) and (not first_choice) and ("xyk" not in result.keys()):
                ticker = await rpc_ticker(rpc, f"{base_asset}:" + result["symbol"])
                await asyncio.sleep(0)
            else:
                ticker = {
                    "percent_change": 0,
                    "base_volume": 0,
                    "latest": 0,
                }
            print(ticker)
            list_of_assets.append(
                {
                    "symbol": result["symbol"],
                    "change": float(ticker["percent_change"]),
                    "ticker": no_sci(float(ticker["latest"])),
                    "volume": str(ticker["base_volume"]),
                    "ispool": "xyk" in result.keys(),
                    "id": result["id"] if ("xyk" in result.keys()) else "",
                    "greyscale": result["greyscale"],
                }
            )
    list_of_assets.sort(
        key=lambda x: (
            float(x["greyscale"]),
            # do a full (a-z + A-Z) caesar cypher on the symbol
            # to invert the sorting on it but not the above
            # THUS IS MAGIC
            [chr(-(ord(i) - 65) + 122) for i in str(x["symbol"])],
        ),
        reverse=True,
    )
    return list_of_assets


async def list_asset_to_html(rpc, data, first_choice, base_asset, fast):
    """
    Handle list_assets JSON
    """
    print(str(first_choice) * 10)
    list_of_assets = await create_asset_list(rpc, data, first_choice, base_asset, fast)
    if first_choice:
        # the user is selecting the first - asset
        picker_html = (
            "<thead><tr><th>Asset X          Asset Y          Asset"
            " K</th></tr></thead><tbody>"
        )
    else:
        # the user is selecting the second - currency
        picker_html = (
            "<thead><tr><th>Pairs         Last          "
            "Price         Change</th></tr></thead><tbody>"
        )
    idx = 0
    for asset in list_of_assets:
        if not first_choice:
            base = asset["id"] if asset["ispool"] else base_asset
            if asset["symbol"] != base:
                idx += 1
                picker_html += (
                    "<tr style='"
                    + ("background-color: #0B0D14; " if idx % 2 == 0 else "")
                    + "color:rgb"
                    + str(tuple([asset["greyscale"]] * 3))
                    + "' onclick=\"book('"
                    + base
                    + "','"
                )
                picker_html += asset["symbol"] + "')\"><td>"
                picker_html += f"{base}:"
                picker_html += asset["symbol"]
                picker_html += "</td><td>"
                picker_html += str(asset["ticker"])
                picker_html += '</td><td class="'
                picker_html += "red" if asset["change"] < 0 else "green"
                picker_html += '">' + str(asset["change"]) + "%</td></tr>"
        else:
            # the user is entering their first choice
            idx += 1
            picker_html += (
                "<tr style='"
                + ("background-color: #0B0D14; " if idx % 2 == 0 else "")
                + "color:rgb"
                + str(tuple([asset["greyscale"]] * 3))
                + (
                    "' onclick=\"book('" + asset["id"] + "', '"
                    if asset["ispool"]
                    else "' onclick=\"firstSearch('"
                )
            )
            picker_html += (
                ":".join([i for i in asset["symbol"].split("&nbsp;") if i][1:3]) + "')"
            )
            picker_html += '"><td>'
            picker_html += asset["symbol"]
            picker_html += "</td><td></td><td></td><td>&nbsp;</td></tr>"
    picker_html += "</tbody>"
    del list_of_assets
    return picker_html


async def json_to_html(
    ws, rpc, resource, data, asset, currency, first_choice, base_asset, pool_data
):
    """
    Perform data wrangling server side before responding to the client
    This consists of converting JSON into HTML
    that can be easily inserted with JS
    """
    if resource == "book":
        return await orderbook_to_html(
            rpc, data, asset, currency, pool_data, f"{asset}:{currency}"
        )
    elif resource == "list_assets":
        if not first_choice:
            await ws.send_media(
                {
                    "payload": await list_asset_to_html(
                        rpc, data, first_choice, base_asset, True
                    ),
                    "resource": resource,
                }
            )
        return await list_asset_to_html(rpc, data, first_choice, base_asset, False)
    else:
        return data
