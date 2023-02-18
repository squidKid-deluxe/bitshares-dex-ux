# pylint: disable=broad-except, unspecified-encoding, too-many-branches, no-self-use
"""
 ╔╗ ┬┌┬┐┌─┐┬ ┬┌─┐┬─┐┌─┐┌─┐  ╔╦╗┌─┐─┐ ┬  ╦ ╦─┐ ┬
 ╠╩╗│ │ └─┐├─┤├─┤├┬┘├┤ └─┐   ║║├┤ ┌┴┬┘  ║ ║┌┴┬┘
 ╚═╝┴ ┴ └─┘┴ ┴┴ ┴┴└─└─┘└─┘  ═╩╝└─┘┴ └─  ╚═╝┴ └─
Bitshares Decentralized Exchange User Experience

Initalize database and provide simple interface for accessing database
"""
# STANDARD MOUDLES
import json
import os
import time
from sqlite3 import Row, connect

# GLOBAL CONSTANTS
DEV = False
PATH = os.path.dirname(os.path.abspath(__file__)) + "/database"
CREATES = [
    """
    CREATE TABLE nodes (
    url TEXT PRIMARY KEY,
    ping REAL,
    handshake REAL,
    blocktime INT,
    code INT,
    status TEXT
    )
    """,
    """
    CREATE TABLE klines (
    pair TEXT PRIMARY KEY,
    end_unix INT,
    c86400 TEXT,
    c43200 TEXT,
    c14400 TEXT,
    c7200 TEXT,
    c3600 TEXT,
    c1800 TEXT,
    c900 TEXT,
    discrete TEXT
    )
    """,
    """
    CREATE TABLE assets (
    id TEXT PRIMARY KEY,
    dynamic_id TEXT,
    pool_id TEXT,
    bitasset_id TEXT,
    symbol TEXT NOT NULL UNIQUE,
    precision INT,
    maker_fee DECIMAL,
    taker_fee DECIMAL,
    description TEXT
    )
    """,
    """
    CREATE TABLE pools (
    id TEXT PRIMARY KEY,
    asset_a TEXT,
    asset_b TEXT,
    asset_a_name TEXT,
    asset_b_name TEXT,
    balance_a DECIMAL,
    balance_b DECIMAL,
    share_asset TEXT,
    share_asset_name TEXT,
    taker_fee_percent DECIMAL,
    withdrawal_fee_percent DECIMAL,
    virtual_value DECIMAL,
    pair TEXT,
    xyk TEXT
    )
    """,
    """
    CREATE TABLE accounts (
        account_id TEXT PRIMARY KEY,
        account_name TEXT,
        is_ltm BOOL
    )
    """,
]
SELECTS = [
    """
    SELECT * FROM nodes
    """,
    """
    SELECT * FROM assets
    """,
    """
    SELECT * FROM pools
    """,
    # """
    # SELECT * FROM bitassets
    # """,
    """
    SELECT * FROM accounts
    """,
]
UPDATES = [
    (
        """
        UPDATE nodes SET ping=?, code=?, status=?
        """,
        ("999.9", "1000", "INITIALIZING"),
    ),
]
DATABASE = PATH + "/test"
ASSETS = ["HONEST.USD", "BTS"]
NODES = ["wss://api.bts.mobi/wss"]
PAIRS = ["HONEST.USD:BTS"]


class Sql:
    """
    creation of graphene database and execution of queries
    """

    def restart(self):
        """
        delete any existing db and initialize new SQL db
        """
        # create database folder
        os.makedirs(PATH, exist_ok=True)
        # user input w/ warning
        print("\033c")
        print("WARNING THIS SCRIPT WILL RESTART DATABASE AND ERASE ALL DATA\n")
        # erase the database
        command = f"rm {DATABASE}"
        print("\033c", command, "\n")
        os.system(command)
        print("creating sqlite3:", DATABASE, "\n")
        # initialize insert operations with chain specific configuration
        inserts = []
        for node in NODES:
            inserts.append(
                (
                    """
                    INSERT INTO nodes (url) VALUES (?)
                    """,
                    (node,),
                )
            )
        # new table creation
        queries = []
        for query in CREATES:
            dml = {"query": query, "values": tuple()}
            queries.append(dml)
        self.execute(queries)
        # row creation in each table
        queries = []
        for insert in inserts:
            dml = {"query": insert[0], "values": insert[1]}
            queries.append(dml)
        self.execute(queries)
        # default column data in each row
        queries = []
        for update in UPDATES:
            dml = {"query": update[0], "values": update[1]}
            queries.append(dml)
        self.execute(queries)
        # print
        for query in SELECTS:
            print(query, self.execute(query))

    def execute(self, query, values=()):
        """
        execute discrete sql queries, handle race condition gracefully
        if query is a string, assume values is a
        else, query can be a list of dicts with keys ["query","values"]
        While True:
            Try:
                con = connect(DB)
                cur = con.cursor()
                cur.execute(query, values)
                ret = cur.fetchall()
                con.commit()
                con.close()
                break
            Except:
                continue
        :return ret:
        """
        queries = []
        # handle both single query and multiple queries
        if isinstance(query, str):
            queries.append({"query": query, "values": values})
        else:
            queries = query
        # strip double spaces and new lines in each query
        for idx, dml in enumerate(queries):
            queries[idx]["query"] = " ".join(dml["query"].replace("\n", " ").split())
        # print sql except when...
        for dml in queries:
            if DEV:
                print(f"'query': {dml['query']}")
                print(f"'values': {dml['values']}\n")
        # attempt to update database until satisfied
        pause = -1
        curfetchall = None
        data = None
        while True:
            try:
                pause += 1
                # only allow batched write queries
                if len(queries) > 1:
                    for dml in queries:
                        if "SELECT" in dml["query"]:
                            raise ValueError("batch queries must be write only")
                # ======================================================================
                # SQL CONNECT
                # ======================================================================
                con = connect(DATABASE)
                for dml in queries:
                    con.row_factory = Row
                    cur = con.cursor()
                    cur.execute(dml["query"], dml["values"])
                    curfetchall = cur.fetchall()
                # print(curfetchall)
                con.commit()
                con.close()
                # ======================================================================
                # SQL CLOSE
                # ======================================================================
                # print(curfetchall)
                data = [dict(i) for i in curfetchall]
                for idx, row in enumerate(data):
                    for key, val in row.items():
                        # attempt to load as JSON
                        try:
                            data[idx][key] = json.loads(val)
                        # otherwise give raw
                        except Exception:
                            data[idx][key] = val
                return data
            except Exception as error:
                print(error)
                print("Race condition at", int(time.time()))
                try:
                    print(dml)
                except Exception:
                    pass
                # raise
                # ascending pause here prevents excess cpu on corruption of database
                # and allows for decreased load during race condition
                time.sleep(min(5, 0.01))
                continue
        return data


def unit_test():
    """
    initialize the database
    """
    print("\033c")
    sql = Sql()
    sql.restart()


if __name__ == "__main__":
    unit_test()
