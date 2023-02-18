# pylint: disable=broad-except, unspecified-encoding
"""
 ╔╗ ┬┌┬┐┌─┐┬ ┬┌─┐┬─┐┌─┐┌─┐  ╔╦╗┌─┐─┐ ┬  ╦ ╦─┐ ┬
 ╠╩╗│ │ └─┐├─┤├─┤├┬┘├┤ └─┐   ║║├┤ ┌┴┬┘  ║ ║┌┴┬┘
 ╚═╝┴ ┴ └─┘┴ ┴┴ ┴┴└─└─┘└─┘  ═╩╝└─┘┴ └─  ╚═╝┴ └─
Bitshares Decentralized Exchange User Experience
"""

# BITSHARES DEX UX MODULES
from database import Sql
from utilities import is_whitelisted


def list_assets_sql(sql, asset, use_types):
    """
    list all assets in database which match user query and type
    """
    if asset.startswith("1.3."):
        query = [{"query": "SELECT symbol FROM assets WHERE id=?", "values": (asset,)}]
        data = sql.execute(query)
    elif asset.startswith("1.19."):
        query = [
            {
                "query": "SELECT xyk, share_asset_name FROM pools WHERE id=?",
                "values": (asset,),
            }
        ]
        data = sql.execute(query)[0]
        data = [{"symbol": ":".join(data["xyk"].split(":"))[:-1], **data}]
    else:
        data = query_by_asset_type(use_types, sql, asset)
    data = [{**i, "greyscale": is_whitelisted(i["symbol"])} for i in data]
    # data = data[:depth]
    data.sort(key=lambda x: x["symbol"])
    return data


def query_by_asset_type(use_types, sql, asset):
    """
    each asset type will have a different query format
    """
    mpa_data = []
    uia_data = []
    lp_data = []
    pool_data = []
    # Make SQL queries by user selected asset type
    if use_types["mpa"]:
        mpa_data = query_template('bitasset_id <> ""', sql, asset)
    if use_types["uia"]:
        uia_data = query_template('bitasset_id = "" AND pool_id = ""', sql, asset)
    if use_types["k_token"]:
        lp_data = query_template('pool_id <> ""', sql, asset)
    if use_types["pool"]:
        pool_data = sql.execute("SELECT xyk, share_asset_name, id FROM pools")
        # sort by those that contiain the search string
        # and rename xyk to symbol for easier processing
        # but keep xyk availible for checking if it came from a pool search
        pool_data = [
            {
                "symbol": (
                    i["id"].ljust(17, "*")
                    + "".join([j.ljust(17, "*") for j in i["xyk"].split(":")[:-1:]])
                ).replace("*", "&nbsp;"),
                **i,
            }
            for i in pool_data
            if asset in i["xyk"]
        ]
    result = mpa_data + uia_data + lp_data + pool_data
    if use_types["bts"]:
        result.append({"symbol": "BTS"})
    return result


def query_template(condition, sql, asset):
    """
    build a SELECT sql asset symbol query for a condition
    SQL SECURITY: condition is hard coded in query_by_asset_type
    """
    query = f"SELECT symbol, id FROM assets WHERE {condition}"
    return [i for i in sql.execute(query) if asset in i["symbol"]]


def precision(sql, asset):
    """
    Get the precision of an asset from the SQL database
    """
    if not sql:
        sql = Sql()
    query = [{"query": "SELECT precision FROM assets WHERE id=?", "values": (asset,)}]
    return sql.execute(query)[0]["precision"]


def name_id_lookup(sql, asset):
    """
    Get the name of an asset from its ID from the SQL database
    """
    query = [{"query": "SELECT symbol FROM assets WHERE id=?", "values": (asset,)}]
    return sql.execute(query)[0]["symbol"]


def id_name_lookup(sql, asset):
    """
    Get the ID of an asset from its name from the SQL database
    """
    query = [{"query": "SELECT id FROM assets WHERE symbol=?", "values": (asset,)}]
    return sql.execute(query)[0]["id"]
