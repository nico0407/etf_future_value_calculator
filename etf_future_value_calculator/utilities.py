"""General helpers and data access for the ETF Future Value Calculator."""

from __future__ import annotations

import re
from datetime import date
from hashlib import sha256
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import requests
import yfinance as yf

from app_config import (
    DEFAULT_CURRENCY,
    KNOWN_ETFS,
    MARKET_DATA_API_KEY,
    MARKET_DATA_API_URL,
    MAX_INVESTMENT_YEARS,
    MOCK_HISTORY_MONTHS,
    OPENFIGI_API_KEY,
    OPENFIGI_URL,
)


def validate_isin(isin: str) -> bool:
    """Validate an ISIN using its basic format and official check digit."""
    cleaned = clean_isin(isin)
    if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{10}", cleaned):
        return False

    body = cleaned[:-1]
    check_digit = cleaned[-1]
    if not check_digit.isdigit():
        return False

    expanded = "".join(_isin_character_value(character) for character in body)
    digits = [int(digit) for digit in expanded + check_digit]

    # Luhn-style ISIN check: double every second digit from the right.
    total = 0
    should_double = False
    for digit in reversed(digits):
        value = digit * 2 if should_double else digit
        total += value // 10 + value % 10
        should_double = not should_double

    return total % 10 == 0


def validate_monthly_amount(amount: float) -> bool:
    """Return True when the monthly investment is a positive amount."""
    return amount > 0


def validate_years(years: int) -> bool:
    """Return True when the investment horizon is a practical positive integer."""
    return 1 <= years <= MAX_INVESTMENT_YEARS


def clean_isin(isin: str) -> str:
    """Normalize user-entered ISIN text."""
    return (isin or "").strip().upper().replace(" ", "")


def resolve_isin(isin: str) -> Dict[str, Any]:
    """Resolve an ISIN into ETF/security metadata.

    OpenFIGI is used when OPENFIGI_API_KEY is configured. Without a key, the
    app uses a small curated local mapping for known ETFs.
    """
    cleaned = clean_isin(isin)
    if not validate_isin(cleaned):
        raise ValueError("Please enter a valid 12-character ISIN.")

    if not OPENFIGI_API_KEY and cleaned in KNOWN_ETFS:
        return _known_etf_metadata(cleaned)
    if not OPENFIGI_API_KEY:
        raise ValueError(
            "This ISIN is not in the local ETF mapping. Configure OPENFIGI_API_KEY "
            "to resolve arbitrary ISINs."
        )

    headers = {
        "Content-Type": "application/json",
        "X-OPENFIGI-APIKEY": OPENFIGI_API_KEY,
    }
    payload = [{"idType": "ID_ISIN", "idValue": cleaned}]

    response = requests.post(
        OPENFIGI_URL,
        json=payload,
        headers=headers,
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    matches = data[0].get("data", []) if data else []
    if not matches:
        raise ValueError("OpenFIGI did not return a match for this ISIN.")

    best_match = _pick_best_openfigi_match(matches)
    return {
        "name": best_match.get("name") or "Unknown ETF",
        "ticker": best_match.get("ticker") or "",
        "display_ticker": best_match.get("ticker") or "",
        "exchange": best_match.get("exchCode") or best_match.get("marketSector") or "",
        "currency": best_match.get("currency") or DEFAULT_CURRENCY,
        "figi": best_match.get("figi"),
        "is_mock_data": False,
        "metadata_source": "openfigi",
    }


def get_historical_prices(symbol: str, exchange: Optional[str] = None) -> pd.DataFrame:
    """Return historical monthly adjusted closes for a symbol.

    If MARKET_DATA_API_KEY is configured, a Twelve Data-compatible endpoint is
    queried. Without a key, Yahoo Finance is used via yfinance.
    """
    if not MARKET_DATA_API_KEY:
        return _get_yfinance_historical_prices(symbol)

    api_symbol = _build_market_data_symbol(symbol, exchange)
    params = {
        "symbol": api_symbol,
        "interval": "1month",
        "outputsize": 240,
        "apikey": MARKET_DATA_API_KEY,
    }

    response = requests.get(MARKET_DATA_API_URL, params=params, timeout=20)
    response.raise_for_status()
    prices = _parse_market_data_payload(response.json())
    if prices.empty:
        raise ValueError("Market data response did not include usable prices.")

    prices.attrs["is_mock_data"] = False
    prices.attrs["source"] = "market_data_api"
    return prices


def format_currency(value: float, currency: str = DEFAULT_CURRENCY) -> str:
    """Format money values with a simple currency prefix."""
    symbols = {"GBP": "£", "USD": "$", "EUR": "€"}
    code = (currency or DEFAULT_CURRENCY).upper()
    symbol = symbols.get(code, f"{code} ")
    return f"{symbol}{value:,.2f}"


def format_percentage(value: float) -> str:
    """Format decimal returns as percentages."""
    return f"{value * 100:.2f}%"


def currency_prefix(currency: str) -> str:
    """Return a chart-friendly currency prefix."""
    return {"GBP": "£", "USD": "$", "EUR": "€"}.get((currency or DEFAULT_CURRENCY).upper(), "")


def _isin_character_value(character: str) -> str:
    if character.isdigit():
        return character
    return str(ord(character) - 55)


def _known_etf_metadata(isin: str) -> Dict[str, Any]:
    metadata = KNOWN_ETFS[isin].copy()
    metadata["is_mock_data"] = False
    metadata["metadata_source"] = "local_mapping"
    return metadata


def _pick_best_openfigi_match(matches: list[Dict[str, Any]]) -> Dict[str, Any]:
    def score(match: Dict[str, Any]) -> int:
        text = " ".join(
            str(match.get(key, "")) for key in ("name", "securityType", "securityType2", "marketSector")
        ).upper()
        points = 0
        if "ETF" in text:
            points += 5
        if "FUND" in text:
            points += 2
        if match.get("ticker"):
            points += 1
        if match.get("currency"):
            points += 1
        return points

    return sorted(matches, key=score, reverse=True)[0]


def _build_market_data_symbol(symbol: str, exchange: Optional[str]) -> str:
    cleaned_symbol = (symbol or "").strip().upper()
    cleaned_exchange = (exchange or "").strip().upper()
    if cleaned_exchange and cleaned_exchange not in cleaned_symbol:
        return f"{cleaned_symbol}:{cleaned_exchange}"
    return cleaned_symbol


def _parse_market_data_payload(payload: Dict[str, Any]) -> pd.DataFrame:
    values = payload.get("values", [])
    rows = []
    for item in values:
        close = item.get("adj_close") or item.get("adjusted_close") or item.get("close")
        if close is None:
            continue
        rows.append(
            {
                "date": pd.to_datetime(item["datetime"]).date(),
                "adjusted_close": float(close),
            }
        )

    prices = pd.DataFrame(rows)
    if prices.empty:
        return prices
    return prices.sort_values("date").reset_index(drop=True)


def _get_yfinance_historical_prices(symbol: str) -> pd.DataFrame:
    data = yf.download(
        symbol,
        period="max",
        interval="1mo",
        auto_adjust=True,
        progress=False,
    )
    if data.empty:
        raise ValueError(f"Yahoo Finance did not return historical prices for {symbol}.")

    close_prices = data["Close"]
    if isinstance(close_prices, pd.DataFrame):
        close_prices = close_prices.iloc[:, 0]

    prices = pd.DataFrame(
        {
            "date": pd.to_datetime(close_prices.index).date,
            "adjusted_close": close_prices.astype(float).values,
        }
    )
    prices = prices.dropna().sort_values("date").reset_index(drop=True)
    prices.attrs["is_mock_data"] = False
    prices.attrs["source"] = "yfinance"
    return prices


def _mock_historical_prices(symbol: str) -> pd.DataFrame:
    end = pd.Timestamp(date.today()).to_period("M").to_timestamp("M")
    dates = pd.date_range(end=end, periods=MOCK_HISTORY_MONTHS, freq="ME")
    seed_text = (symbol or "ETF").upper().encode("utf-8")
    seed = int(sha256(seed_text).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)

    monthly_drift = 0.006
    monthly_volatility = 0.035
    returns = rng.normal(monthly_drift, monthly_volatility, len(dates))
    prices = 100 * np.cumprod(1 + returns)

    data = pd.DataFrame(
        {
            "date": dates.date,
            "adjusted_close": prices.round(2),
        }
    )
    data.attrs["is_mock_data"] = True
    data.attrs["source"] = "mock"
    return data
