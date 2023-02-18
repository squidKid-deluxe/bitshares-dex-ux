# pylint: disable=broad-except, unspecified-encoding, too-many-locals
"""
 ╔╗ ┬┌┬┐┌─┐┬ ┬┌─┐┬─┐┌─┐┌─┐  ╔╦╗┌─┐─┐ ┬  ╦ ╦─┐ ┬
 ╠╩╗│ │ └─┐├─┤├─┤├┬┘├┤ └─┐   ║║├┤ ┌┴┬┘  ║ ║┌┴┬┘
 ╚═╝┴ ┴ └─┘┴ ┴┴ ┴┴└─└─┘└─┘  ═╩╝└─┘┴ └─  ╚═╝┴ └─
Bitshares Decentralized Exchange User Experience

Initalize database with rpc queried data
"""
# STANDARD MOUDLES
import contextlib
import json
import time
import asyncio

# BITSHARES DEX UX MODULES
from database import Sql
from rpc import get_max_object, rpc_get_objects, wss_handshake
from sql_utils import name_id_lookup

BATCH = 100


def assets():
    """
    initialize the assets database
    """
    sql = Sql()
    rpc = await wss_handshake()
    max_object = await get_max_object(rpc, "1.3.")
    query = "SELECT id FROM assets;"  #'SELECT * FROM nodes'
    # 'SELECT * FROM 1.3'
    max_object_sql = sql.execute(query)
    # print(max_object_sql)
    max_object_sql = int(
        max(max_object_sql, key=lambda x: int(x["id"][4:]))["id"][4:]
        if max_object_sql
        else -1
    )
    get_objs = {}
    for batch_n in range(max_object_sql + 1, max_object + BATCH, BATCH):
        get_objs = {
            **get_objs,
            **await rpc_get_objects(
                rpc, [f"1.3.{str(n)}" for n in range(batch_n, batch_n + 100)]
            ),
        }
        time.sleep(0.5)
    inserts = []
    for token, get_obj in get_objs.items():
        desc = ""
        with contextlib.suppress(Exception):
            desc = json.loads(get_obj["options"]["description"])["short_name"]
        inserts.append(
            (
                "INSERT INTO assets VALUES (?,?,?,?,?,?,?,?,?) ",
                (
                    token,
                    get_obj["dynamic_asset_data_id"],
                    get_obj.get("for_liquidity_pool", ""),
                    get_obj.get("bitasset_data_id", ""),
                    get_obj["symbol"],
                    get_obj["precision"],
                    get_obj["options"]["market_fee_percent"],
                    get_obj["options"]["extensions"].get(
                        "taker_fee_percent",
                        get_obj["options"]["market_fee_percent"],
                    ),
                    desc,
                ),
            )
        )
    if inserts:
        queries = []
        for update in inserts:
            dml = {"query": update[0], "values": update[1]}
            queries.append(dml)
        sql.execute(queries)


def pools():
    """
    initialize the pools database
    """
    sql = Sql()
    rpc = await wss_handshake()
    max_object = await get_max_object(rpc, "1.19.")
    query = "SELECT id FROM pools;"
    max_object_sql = sql.execute(query)
    # print(max_object_sql)
    max_object_sql = int(
        max(max_object_sql, key=lambda x: int(x["id"][5:]))["id"][5:]
        if max_object_sql
        else -1
    )
    get_objs = {}
    for batch_n in range(max_object_sql + 1, max_object + BATCH, BATCH):
        get_objs = {
            **get_objs,
            **await rpc_get_objects(
                rpc, [f"1.19.{str(n)}" for n in range(batch_n, batch_n + 100)]
            ),
        }
        time.sleep(0.5)
    inserts = []
    for token, get_obj in get_objs.items():
        query = [
            {
                "query": "SELECT symbol, precision FROM assets WHERE id=?",
                "values": (get_obj["asset_a"],),
            }
        ]
        asset_a_data = sql.execute(query)[0]
        query = [
            {
                "query": "SELECT symbol, precision FROM assets WHERE id=?",
                "values": (get_obj["asset_b"],),
            }
        ]
        asset_b_data = sql.execute(query)[0]
        asset_a_name = asset_a_data["symbol"]
        asset_b_name = asset_b_data["symbol"]
        asset_a_prec = asset_a_data["precision"]
        asset_b_prec = asset_b_data["precision"]
        share_asset_name = name_id_lookup(sql, get_obj["share_asset"])
        inserts.append(
            (
                "INSERT INTO pools VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ",
                (
                    token,
                    get_obj["asset_a"],
                    get_obj["asset_b"],
                    asset_a_name,
                    asset_b_name,
                    float(int(get_obj["balance_a"]) / 10**asset_a_prec),
                    float(int(get_obj["balance_b"]) / 10**asset_b_prec),
                    get_obj["share_asset"],
                    share_asset_name,
                    get_obj["taker_fee_percent"],
                    get_obj["withdrawal_fee_percent"],
                    int(get_obj["virtual_value"]) / 10 ** (asset_a_prec + asset_b_prec),
                    f"{asset_a_name}:{asset_b_name}",
                    f"{asset_a_name}:{asset_b_name}:{share_asset_name}",
                ),
            )
        )
    if inserts:
        queries = []
        for update in inserts:
            dml = {"query": update[0], "values": update[1]}
            queries.append(dml)
        sql.execute(queries)


if __name__ == "__main__":
    assets()
    pools()
