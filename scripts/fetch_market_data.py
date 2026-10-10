#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

OUT = Path("market-data.json")

ASSETS = [
    {"id": "dax", "name": "DAX", "symbol": "^GDAXI", "kind": "index", "currency": "EUR"},
    {"id": "btc", "name": "Bitcoin", "symbol": "BTC-EUR", "kind": "crypto", "currency": "EUR"},
    {"id": "schaeffler", "name": "Schaeffler", "symbol": "SHA0.DE", "kind": "stock", "currency": "EUR"},
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; KitchenDashboard/1.0)"}

def fmt_de(value, decimals=2):
    s = f"{value:,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")

def format_display(asset, price):
    if asset["kind"] == "index":
        return fmt_de(price, 2)
    if asset["kind"] == "crypto":
        return fmt_de(price, 0) + " €"
    if asset["kind"] == "stock":
        return fmt_de(price, 2) + " €"
    return fmt_de(price, 2)

def get_quote(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{requests.utils.quote(symbol, safe='')}"
    params = {"range":"5d","interval":"5m","includePrePost":"false","events":"div,splits"}

    r = requests.get(url, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    result = r.json().get("chart", {}).get("result")
    if not result:
        raise RuntimeError(f"No data for {symbol}")

    data = result[0]
    meta = data.get("meta", {})
    price = meta.get("regularMarketPrice")
    prev = meta.get("chartPreviousClose")
    if prev is None:
        prev = meta.get("previousClose")

    if price is None:
        closes = data.get("indicators", {}).get("quote", [{}])[0].get("close", [])
        closes = [x for x in closes if x is not None]
        if closes:
            price = closes[-1]

    if price is None:
        raise RuntimeError(f"No current price for {symbol}")

    change_pct = None
    if prev not in (None, 0):
        change_pct = (float(price) - float(prev)) / float(prev) * 100.0

    return float(price), change_pct, meta, (float(prev) if prev else None)

def main():
    items = []

    for asset in ASSETS:
        try:
            price, change_pct, meta, _ = get_quote(asset["symbol"])
            items.append({
                "id": asset["id"],
                "name": asset["name"],
                "symbol": asset["symbol"],
                "price": round(price, 6),
                "display": format_display(asset, price),
                "change_pct": round(change_pct, 4) if change_pct is not None else None,
                "currency": meta.get("currency") or asset["currency"],
                "source": "Yahoo Finance"
            })
        except Exception as exc:
            print(f"ERROR {asset['name']}: {exc}")

    # Gold future in USD per troy ounce converted using current EUR/USD.
    try:
        gold_usd, _, _, gold_prev_usd = get_quote("GC=F")
        eurusd, _, _, eurusd_prev = get_quote("EURUSD=X")

        gold_eur = gold_usd / eurusd
        gold_change_pct = None

        if gold_prev_usd and eurusd_prev:
            gold_prev_eur = gold_prev_usd / eurusd_prev
            gold_change_pct = (gold_eur - gold_prev_eur) / gold_prev_eur * 100.0

        items.append({
            "id": "gold",
            "name": "Gold",
            "symbol": "GC=F / EURUSD=X",
            "price": round(gold_eur, 6),
            "display": fmt_de(gold_eur, 2) + " €/oz",
            "change_pct": round(gold_change_pct, 4) if gold_change_pct is not None else None,
            "currency": "EUR",
            "source": "Yahoo Finance"
        })
    except Exception as exc:
        print(f"ERROR Gold: {exc}")

    if not items:
        raise SystemExit("No market data could be loaded.")

    OUT.write_text(json.dumps({
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "items": items
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
