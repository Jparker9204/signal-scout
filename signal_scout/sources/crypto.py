"""Public CoinGecko market movers (read-only market data; no trading)."""

from __future__ import annotations

from datetime import UTC, datetime

from ..models import Item
from .base import Source

COINGECKO_MARKETS = "https://api.coingecko.com/api/v3/coins/markets"


class CryptoMoversSource(Source):
    """Alerts when a coin's 24h price change or volume crosses configured thresholds."""

    name = "crypto"

    def fetch(self) -> list[Item]:
        cfg = self.config
        params = {
            "vs_currency": cfg.get("vs_currency", "usd"),
            "order": "market_cap_desc",
            "per_page": int(cfg.get("top_n", 100)),
            "page": 1,
            "price_change_percentage": "24h",
        }
        min_change = float(cfg.get("min_abs_change_pct", 10))
        min_volume = float(cfg.get("min_volume_usd", 10_000_000))
        watch = {s.lower() for s in cfg.get("watchlist", [])}
        day = datetime.now(UTC).strftime("%Y-%m-%d")

        items: list[Item] = []
        for coin in self.get_json(COINGECKO_MARKETS, params=params):
            symbol = str(coin.get("symbol", "")).lower()
            if watch and symbol not in watch:
                continue
            change = coin.get("price_change_percentage_24h")
            volume = coin.get("total_volume") or 0
            if change is None or abs(change) < min_change or volume < min_volume:
                continue
            direction = "up" if change > 0 else "down"
            items.append(
                Item(
                    source=self.name,
                    # One alert per coin per direction per UTC day.
                    uid=f"{coin['id']}:{direction}:{day}",
                    title=f"{coin.get('name')} ({symbol.upper()}) {change:+.1f}% in 24h",
                    url=f"https://www.coingecko.com/en/coins/{coin['id']}",
                    summary=f"Price ${coin.get('current_price')} | 24h volume ${volume:,.0f}",
                    extra={"change_pct": change, "volume": volume},
                )
            )
        return items
