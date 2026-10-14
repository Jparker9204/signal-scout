import responses

from signal_scout.sources.crypto import COINGECKO_MARKETS, CryptoMoversSource

COINS = [
    {
        "id": "bitcoin",
        "symbol": "btc",
        "name": "Bitcoin",
        "current_price": 1,
        "total_volume": 5e10,
        "price_change_percentage_24h": 2.0,
    },
    {
        "id": "pumpcoin",
        "symbol": "pump",
        "name": "Pump",
        "current_price": 1,
        "total_volume": 5e7,
        "price_change_percentage_24h": 25.0,
    },
    {
        "id": "tiny",
        "symbol": "tny",
        "name": "Tiny",
        "current_price": 1,
        "total_volume": 1e3,
        "price_change_percentage_24h": -40.0,
    },
    {
        "id": "dump",
        "symbol": "dmp",
        "name": "Dump",
        "current_price": 1,
        "total_volume": 5e7,
        "price_change_percentage_24h": -12.0,
    },
]


@responses.activate
def test_thresholds(session):
    responses.get(COINGECKO_MARKETS, json=COINS)
    src = CryptoMoversSource({"min_abs_change_pct": 10, "min_volume_usd": 1e6}, session)
    items = src.fetch()
    assert [i.extra["change_pct"] for i in items] == [25.0, -12.0]
    assert items[0].uid.startswith("pumpcoin:up:")
    assert items[1].uid.startswith("dump:down:")


@responses.activate
def test_watchlist(session):
    responses.get(COINGECKO_MARKETS, json=COINS)
    src = CryptoMoversSource(
        {"min_abs_change_pct": 1, "min_volume_usd": 0, "watchlist": ["BTC"]}, session
    )
    assert [i.title.split()[0] for i in src.fetch()] == ["Bitcoin"]
