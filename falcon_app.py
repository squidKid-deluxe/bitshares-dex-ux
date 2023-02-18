# pylint:disable=no-member, broad-except, unspecified-encoding
# pylint:disable=too-many-locals, too-many-branches, too-many-statements,
"""
 ╔╗ ┬┌┬┐┌─┐┬ ┬┌─┐┬─┐┌─┐┌─┐  ╔╦╗┌─┐─┐ ┬  ╦ ╦─┐ ┬
 ╠╩╗│ │ └─┐├─┤├─┤├┬┘├┤ └─┐   ║║├┤ ┌┴┬┘  ║ ║┌┴┬┘
 ╚═╝┴ ┴ └─┘┴ ┴┴ ┴┴└─└─┘└─┘  ═╩╝└─┘┴ └─  ╚═╝┴ └─
Bitshares Decentralized Exchange User Experience
"""
# STANDARD MODULES
import asyncio
import contextlib
import json
import time
import traceback

# THIRD PARTY MODULES
import falcon
import falcon.asgi
import websockets

# BITSHARES DEX UX MODULES
from database import Sql
from json_to_html import json_to_html
from kibana import fetch_candles, format_chart_type
from rpc import rpc_book, rpc_get_objects, rpc_ticker, wss_handshake
from sql_utils import id_name_lookup, list_assets_sql
from utilities import it


async def serve_blocknum(ws, rpc):
    try:
        await ws.send_media(
            {
                "resource": "blocknum",
                "payload": (await rpc_get_objects(rpc, ["2.1.0"]))["2.1.0"][
                    "head_block_number"
                ],
            }
        )
    except Exception as error:
        print(error)
        rpc = error_handler("", rpc)


async def serve_ticker(ws, rpc, contract, pair):
    await ws.send_media(
        {
            "resource": "ticker",
            "payload": (
                "" if contract.startswith("1.19.") else await rpc_ticker(rpc, pair)
            ),
        }
    )


async def serve_picker(args):
    try:
        (
            ws,
            rpc,
            sql,
            asset,
            currency,
            resource,
            first_choice,
            use_types,
            base_asset,
        ) = args
        data = list_assets_sql(sql, currency, use_types)
        # stringify all items in data, list(set(data)), and load it again
        data = [json.loads(i) for i in {json.dumps(j) for j in data}]
        data = await json_to_html(
            ws,
            rpc,
            resource,
            data,
            asset,
            currency,
            first_choice,
            base_asset,
            {},  # this doesn't matter
        )
        await ws.send_media({"resource": "list_assets", "payload": data})
    except Exception as error:
        print(it("red", error))


class SocketResource:
    """
    Serve a websocket
    """

    def parse_req_params(self, req, userid, sql):
        """
        receive request params and parse them for either socketify or uvicorn backends
        """
        # strip quotes, ampersands and other socketify artifacts
        req_params = {k.strip("?'\"&"): v.strip("?'\"&") for k, v in req.params.items()}
        # figure out if the user sent us a pair or just a asset, defaults to BTS:HONEST.MONEY
        try:
            pair = req_params["pair"].replace("_", ":").upper()
            asset, currency = pair.split(":", 1)
        except (
            IndexError,
            KeyError,
        ):
            try:
                asset = req_params.get("asset", "BTS").upper()
                currency = req_params["token"].upper()
                pair = f"{asset}:{currency}".upper()
            except KeyError:
                pair = "BTS:HONEST.MONEY"
                asset, currency = pair.split(":")
        print(userid, req_params)
        first_choice = req_params.get("firstChoice", "false") == "true"
        pool_data = {}
        if "contract" not in req_params:
            req_params["contract"] = "1.0.0"
        if req_params["contract"].startswith("1.19."):
            query = [
                {
                    "query": (
                        "SELECT * FROM pools WHERE asset_a_name=? AND asset_b_name=?"
                        " AND id=?"
                    ),
                    "values": (asset, currency, req_params["contract"]),
                }
            ]
            pool_data = sql.execute(query)[0]

        # FIXME does this matter? where does it carry? is None ok? IS THIS EVEN NEEDED?
        base_asset = asset if first_choice else "BTS"

        use_types = {
            "mpa": req_params.get("useMPA", "true") == "true",
            "uia": req_params.get("useUIA", "true") == "true",
            "k_token": req_params.get("useLPT", "true") == "true",
            "pool": req_params.get("usePool", "true") == "true",
            "bts": req_params.get("useBTS", "true") == "true",
        }
        return (
            asset,
            currency,
            first_choice,
            use_types,
            base_asset,
            req_params,
            pool_data,
            pair,
        )

    async def gather_orderbook(self, pool_data, rpc, pair, req_params, ws):
        """
        Gather orderbook information either from the pool data or via RPC request
        Parameters:
            pool_data (dict): The data of the pool
            rpc (object): The rpc instance to be used to make the request
            pair (str): The asset pair being queried
            req_params (dict): The request parameters used gather the orderbook

        Returns:
            data (dict): A dictionary containing the bid and ask orderbook information
        """
        try:
            asset, currency = pair.split(":")
            if pool_data:

                def pool(x_start, y_start, delta_x):
                    """
                    x_start*y_start = k
                    x1 = x_start+delta_x
                    k / x1 = y1
                    y1-y_start = delta_y
                    """
                    return y_start - (x_start * y_start) / (x_start + delta_x)

                asset = pool_data["asset_a_name"]
                currency = pool_data["asset_b_name"]
                balance_a = pool_data["balance_a"]
                balance_b = pool_data["balance_b"]
                konstant = balance_a * balance_b

                # List to store the order book
                bids, asks = [], []
                step = 0.01 * balance_a

                for i in range(1, 99):
                    delta_a = i * step
                    balance_a2 = balance_a + delta_a
                    balance_b2 = konstant / balance_a2
                    delta_b = abs(balance_b - balance_b2)
                    price = delta_a / delta_b
                    # gain = step * price
                    asks.append((price, step, step / price))

                for i in range(1, 99):
                    delta_a = i * 0.01 * balance_a
                    balance_a2 = balance_a - delta_a
                    balance_b2 = konstant / balance_a2
                    delta_b = abs(balance_b - balance_b2)
                    price = delta_a / delta_b
                    # gain = step * price
                    bids.append((price, step, step / price))

                # Sort the order book by price
                asks.sort(key=lambda x: x[0], reverse=False)
                bids.sort(key=lambda x: x[0], reverse=True)

                # Print the order book
                # for order in order_book:
                #     print(f"Price: {order[0]:.8f}   Amount: {math.copysign(order[1], 1):.2f}")
                data = {
                    "bids": bids,
                    "asks": asks,
                }
            else:
                data = await rpc_book(rpc, pair, int(req_params.get("depth", 50)))
            data = await json_to_html(
                ws,
                rpc,
                "book",
                data,
                asset,
                currency,
                False,  # This
                "BTS",  # and this don't matter
                pool_data,
            )
        except Exception as error:
            await error_handler("", rpc)
        await ws.send_media({"resource": "book", "payload": data})

    async def fast_candles(self, ws, sql, pair, userid, req_params, params, contract):
        """
        make call to database and immediately do a ws.send_media()
        stale is ok, bad ux is not
        """
        query = [
            {
                "query": "SELECT * FROM klines WHERE pair=?",
                "values": (":".join([id_name_lookup(sql, i) for i in pair.split(":")]),)
                if contract == "1.0.0"
                else (contract,),
            }
        ]
        # the market is asset_id:currency_id for this kline trading pair
        market = ":".join([id_name_lookup(sql, i) for i in pair.split(":")])
        # in the database the klines are stored the oldest token first, regardless of the user request
        sql_market = ":".join(
            [
                f"1.3.{x}"
                for x in sorted(
                    [int(i[4:]) for i in market.split(":")]
                )
            ]
        )
        if result := sql.execute(query):
            if result[0]["c86400"]:
                print(
                    userid,
                    it(
                        "green",
                        "Sending candle data directly from database for"
                        f" {params['chart_type']} {params['candle_size']} chart...",
                    ),
                )
                result = result[0][params["candle_size"]]
                # print(result)
                if params["candle_size"] != "discrete":
                    result = format_chart_type(params["chart_type"], result)
                # print(result)
                result = [
                    params["chart_type"],
                    result,
                    params["candle_size"],
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
                    # for discrete we just invert the price; idx=1
                    result[1]=(
                        [
                        list(i)
                        for i in list(
                            zip(
                                [
                                    [j if idx != 1 else 1 / j for idx, j in enumerate(i)]
                                    for i in list(zip(result[1]))
                                ]
                            )
                        )
                    ]
                    if params["candle_size"] == "discrete"
                    # for non-discrete we invert everything except time and volume
                    else [
                            {
                                k: (1 / v if (("time" not in k) and ("volume" not in k)) else v)
                                for k, v in i.items()
                            }
                            for i in result[1]
                        ]
                    )

                await ws.send_media({"resource": "candles", "payload": result})

    async def on_websocket(self, req, ws):
        """
        WebSocket server that serves as an interface to a BitShares public API node. When a client connects to the
        server using a WebSocket connection, the server will establish a connection to the API node and start processing
        the client's requests.

        The code uses the async/await syntax to allow for asynchronous processing, which means that the server can
        handle multiple client requests simultaneously without blocking. The on_websocket() function is the main entry
        point for handling the WebSocket connection, and it accepts two parameters: a request object (req) and a
        WebSocket object (ws).

        The function first accepts the WebSocket connection by calling the accept() method on the WebSocket object.
        It then generates a unique user ID based on the current time and initializes a WebSocket Secure (WSS) connection
        to a list of BitShares public API nodes. If the connection fails, the function will keep trying until success.

        The function then parses the client's request parameters and determines the type of resource that the client
        is requesting. If the resource is a block number, the function will start a task to send updated block numbers
        to the client every two seconds. If the resource is an order book, the function will start a task to fetch
        and send the order book data to the client. If the resource is a ticker, the function will start a task to fetch
        and send the ticker data to the client.

        The function uses a dictionary called running_tasks to keep track of the tasks that are currently running for
        each resource. It makes sure that only the latest task is running and cancels any outdated tasks to avoid
        sending duplicate data to the client. The function also limits the number of running tasks to a maximum of 5 to
        avoid overloading the server.

        The function then waits for the client to send a new request by calling the receive_media() method on the
        WebSocket object. It parses the new request parameters and determines the type of resource that the client is
        requesting. If the resource is an order book, the function checks if the contract has changed and fetches new
        pool data if necessary. If the resource is a candlestick chart, the function calls the fast_candles() method
        to fetch and send the candlestick data to the client. If the resource is a list of assets, the function updates
        the use_types, first_choice, and base_asset variables based on the client's request.

        The function keeps running indefinitely until the WebSocket connection is closed by the client. It also catches
        any exceptions that occur during the processing of the requests and handles them appropriately. Overall, this
        code provides a robust and scalable WebSocket server that allows clients to interact with a BitShares public API
        node in real-time.
        """

        # accept the request
        await ws.accept()

        userid = int(time.time() * 1000000000)
        print(userid, "[NODE] Initalizing WSS connection...")
        # Connection to a list of BitShares public API nodes and keep it alive
        # rpc = await wss_handshake()
        while True:
            try:
                rpc = await wss_handshake()
                break
            except Exception as e:
                print(e.args, traceback.format_exc())
        ping_task = asyncio.create_task(ping_node(rpc))
        print(userid, "[NODE] WSS connection initialized.")
        sql = Sql()
        try:
            (
                asset,
                currency,
                first_choice,
                use_types,
                base_asset,
                req_params,
                pool_data,
                pair,
            ) = self.parse_req_params(req, userid, sql)
            resource = req_params["resource"]
            params = {
                "chart_type": req_params.get("chart_type", "line"),
                "candle_size": "c86400",
            }
            if resource == "candles":
                await self.fast_candles(
                    ws, sql, pair, userid, req_params, params, req_params["contract"]
                )
        except Exception:
            rpc = await error_handler(userid, rpc)
        contract = req_params["contract"]
        running_tasks = {
            "book": [],
            "candles": [],
            "ticker": [],
            "list_assets": [],
            "blocknum": [],
        }
        num_errors = 0
        while True:
            try:
                # query the appropriate resource
                if resource == "blocknum":
                    # FIXME: does blocknum _need_ to be in the running_tasks dict?
                    #        Nothing ever changes for it.
                    asyncio.create_task(serve_blocknum(ws, rpc))
                elif resource == "book":
                    args = [pool_data, rpc, pair, req_params, ws]
                    running_tasks[resource].append(
                        [args, asyncio.create_task(self.gather_orderbook(*args))]
                    )
                elif resource == "candles":
                    args = [
                        ws,
                        rpc,
                        contract if contract != "1.0.0" else pair,
                        params["chart_type"],
                        params["candle_size"],
                    ]
                    running_tasks[resource].append(
                        [args, asyncio.create_task(fetch_candles(*args))]
                    )
                elif resource == "list_assets":
                    args = [
                        ws,
                        rpc,
                        sql,
                        asset,
                        currency,
                        resource,
                        first_choice,
                        use_types,
                        base_asset,
                    ]
                    running_tasks[resource].append(
                        [args, asyncio.create_task(serve_picker(args))]
                    )

                elif resource == "ticker":
                    args = [ws, rpc, contract, pair]
                    running_tasks[resource].append(
                        [args, asyncio.create_task(serve_ticker(*args))]
                    )
                # print(
                #     "\n".join(
                #         [
                #             f"{k}:{[str(i[0]) for i in v]}"
                #             for k, v in running_tasks.items()
                #         ]
                #     )
                # )

                # if there are multiple tasks and the last task
                # is outdated in terms of data
                if (
                    len(running_tasks[resource]) > 1
                    and running_tasks[resource][-2][0] != running_tasks[resource][-1][0]
                ):
                    # remove all but the latest task
                    latest_task = running_tasks[resource][-1]
                    running_tasks[resource] = [
                        i for i in running_tasks[resource] if i != latest_task
                    ]
                    for _, task in running_tasks[resource]:
                        task.cancel()
                    running_tasks[resource] = [latest_task]
                # never have more than 5 tasks
                while len(running_tasks[resource]) > 5:
                    # cancel the oldest task
                    running_tasks[resource][0][1].cancel()
                    # remove it and its args from the list
                    running_tasks[resource] = running_tasks[resource][1::]
                # print(
                #     "\n".join(
                #         [
                #             f"{k}:{[str(i[0]) for i in v]}"
                #             for k, v in running_tasks.items()
                #         ]
                #     )
                # )

                recv = await ws.receive_media()
                resource = recv["resource"]
                contract = recv.get("contract", "1.0.0")
                print(resource, userid, it("green", "@@@ receiving @@@"), recv)
                if "pair" in recv:
                    pair = recv["pair"].replace("_", ":").upper()
                    asset, currency = pair.split(":")
                    req_params["pair"] = pair
                req_params["contract"] = contract

                if resource == "book":
                    pool_data = {}
                    if recv["contract"].startswith("1.19."):
                        query = [
                            {
                                "query": (
                                    "SELECT * FROM pools WHERE asset_a_name=? AND"
                                    " asset_b_name=? AND id=?"
                                ),
                                "values": (asset, currency, recv["contract"]),
                            }
                        ]
                        pool_data = sql.execute(query)[0]
                elif resource == "candles":
                    # recv contains the candle req data plus some other things
                    # but for these purposes, those other things are ok
                    params = recv
                    await self.fast_candles(
                        ws, sql, pair, userid, req_params, params, contract
                    )
                elif resource == "list_assets":
                    use_types = {
                        "mpa": recv["useMPA"],
                        "uia": recv["useUIA"],
                        "k_token": recv["useLPT"],
                        "pool": recv["usePool"],
                        "bts": recv["useBTS"],
                    }
                    first_choice = recv["firstChoice"]
                    base_asset = recv["assetA"].upper()
                    currency = recv["search"].upper()
                elif resource not in ["ticker", "blocknum"]:
                    print(it("red", "unknown resource"), resource)

                # don't need to do anything special for ticker or blocknum

                # if the ping_task found a bad node, use the new node it returned
                if ping_task.done():
                    rpc = await ping_task
                    ping_task = asyncio.create_task(ping_node(rpc))
            except falcon.WebSocketDisconnected:
                print(userid, "[NODE] Closing WSS connection...")
                ping_task.cancel()
                with contextlib.suppress(Exception):
                    await rpc.close()
                print(userid, "[NODE] WSS connection closed.")
                print(userid, "Ending all asyncio.Tasks()...")
                for tasks in running_tasks.values():
                    for task in tasks:
                        try:
                            task[1].cancel()
                        except Exception as error:
                            (await error_handler(userid, "")).close()

                print(userid, "Finished ending all asyncio.Tasks()")
                break
            except Exception:
                num_errors += 1
                # show the error and switch nodes
                try:
                    rpc = await error_handler(userid, rpc, num_errors)
                    ping_task.cancel()
                    ping_task = asyncio.create_task(ping_node(rpc))
                except Exception as error:
                    print(error)


async def error_handler(userid, rpc, num_errors):
    """
    Print the error and reconnect to bitshares node
    """
    print(userid, "Websocket loop failed with error:")
    print(it("red", traceback.format_exc()))
    if num_errors % 3 == 0:
        with contextlib.suppress(Exception):
            await rpc.close()
        print(userid, "Handling and trying again in one second...")
        await asyncio.sleep(0.1)
        print(userid, "[NODE] Initalizing WSS connection...")
        rpc = await wss_handshake()
        print(userid, "[NODE] WSS connection initialized.")
    return rpc


async def ping_node(rpc):
    """
    Ping the `handshake` with a keepalive signal (get chain id) every ten seconds
    """
    while True:
        print("[NODE] ping")
        if not (await rpc_get_objects(rpc, ["2.8.0"])):
            print(it("orange", "X" * 10 + "[NODE] no response from node! " + "X" * 10))
            rpc = await wss_handshake()
            break
        await asyncio.sleep(10)
    return rpc


# Add resource endpoints to falcon App
# Run with
# `pypy3.9 -m socketify falcon_website:app`
# or with similar ASGI hosting engine
print("\033c")
app = falcon.asgi.App()
app.add_route("/", SocketResource())
