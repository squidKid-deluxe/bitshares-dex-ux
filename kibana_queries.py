"""
 ╔╗ ┬┌┬┐┌─┐┬ ┬┌─┐┬─┐┌─┐┌─┐  ╔╦╗┌─┐─┐ ┬  ╦ ╦─┐ ┬
 ╠╩╗│ │ └─┐├─┤├─┤├┬┘├┤ └─┐   ║║├┤ ┌┴┬┘  ║ ║┌┴┬┘
 ╚═╝┴ ┴ └─┘┴ ┴┴ ┴┴└─└─┘└─┘  ═╩╝└─┘┴ └─  ╚═╝┴ └─
Bitshares Decentralized Exchange User Experience
"""
from utilities import to_iso_date


def kibana_swaps(market, start, stop):
    """
    formatted liquidity pool swap history elastic search query
    """
    return {
        "track_total_hits": False,
        "sort": [
            {
                "block_data.block_time": {
                    "order": "desc",
                    "unmapped_type": "boolean",
                }
            }
        ],
        "fields": [
            {
                "field": "operation_history.operation_result.keyword",
                "include_unmapped": "false",
            },
            {
                "field": "account_history.account.keyword",
                "include_unmapped": "false",
            },
            {
                "field": "account_history.operation_id",
                "include_unmapped": "false",
            },
            {
                "field": "block_data.block_num",
                "include_unmapped": "false",
            },
        ],
        "size": 10000,
        "version": True,
        "script_fields": {},
        "stored_fields": ["*"],
        "runtime_mappings": {},
        "_source": False,
        "query": {
            "bool": {
                "must": [],
                "filter": [
                    {
                        "bool": {
                            "filter": [
                                {
                                    "multi_match": {
                                        "type": "best_fields",
                                        "query": market,
                                        "lenient": True,
                                    }
                                },
                                {
                                    "bool": {
                                        "should": [{"match": {"operation_type": "63"}}],
                                        "minimum_should_match": 1,
                                    }
                                },
                            ]
                        }
                    },
                    {
                        "range": {
                            "block_data.block_time": {
                                "format": "strict_date_optional_time",
                                "gte": to_iso_date(
                                    start
                                ),  # "2022-12-15T05:00:00.000Z",
                                "lte": to_iso_date(stop),  # "2023-01-15T19:29:55.361Z",
                            }
                        }
                    },
                    {"exists": {"field": "operation_history.operation_result"}},
                ],
                "should": [],
                "must_not": [],
            }
        },
        "highlight": {"fragment_size": 2147483647},
    }


def kibana_fills(market, start, stop):
    """
    formatted order book fill history elastic search query
    """
    return {
        "track_total_hits": False,
        "sort": [
            {
                "block_data.block_time": {
                    "order": "desc",
                    "unmapped_type": "boolean",
                }
            }
        ],
        "fields": [
            {"field": "account_history.account.keyword"},
            {"field": "operation_history.op"},
            {"field": "account_history.operation_id"},
            {"field": "block_data.block_num"},
        ],
        "size": 10000,
        "version": True,
        "script_fields": {},
        "stored_fields": ["*"],
        "runtime_mappings": {},
        "_source": False,
        "query": {
            "bool": {
                "must": [],
                "filter": [
                    {
                        "bool": {
                            "filter": [
                                {
                                    "multi_match": {
                                        "type": "best_fields",
                                        "query": market.split(":")[0],
                                        "lenient": True,
                                    }
                                },
                                {
                                    "multi_match": {
                                        "type": "best_fields",
                                        "query": market.split(":")[1],
                                        "lenient": True,
                                    }
                                },
                                # operation_history.op_object.is_maker : false
                                {
                                    "multi_match": {
                                        "type": "best_fields",
                                        "query": (
                                            "operation_history.op_object.is_maker :"
                                            " false"
                                        ),
                                        "lenient": True,
                                    }
                                },
                                {
                                    "bool": {
                                        "should": [{"match": {"operation_type": "4"}}],
                                        "minimum_should_match": 1,
                                    }
                                },
                            ]
                        }
                    },
                    {
                        "range": {
                            "block_data.block_time": {
                                "format": "strict_date_optional_time",
                                "gte": to_iso_date(
                                    start
                                ),  # "2022-12-15T05:00:00.000Z",
                                "lte": to_iso_date(stop),  # "2023-01-15T19:29:55.361Z",
                            }
                        }
                    },
                ],
                "should": [],
                "must_not": [],
            }
        },
        "highlight": {"fragment_size": 2147483647},
    }
