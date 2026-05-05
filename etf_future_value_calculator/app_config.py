"""Configuration for the ETF Future Value Calculator."""

from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv()

APP_TITLE = "ETF Future Value Calculator"
APP_CAPTION = "Estimate a recurring monthly ETF investment using historical price returns."

DEFAULT_ISIN_PLACEHOLDER = "IE00B4L5Y983"
DEFAULT_MONTHLY_INVESTMENT = 300.0
DEFAULT_INVESTMENT_YEARS = 20
DEFAULT_CURRENCY = "GBP"

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
OPENFIGI_API_KEY = os.getenv("OPENFIGI_API_KEY", "")
YAHOO_FINANCE_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"

MARKET_DATA_API_URL = os.getenv(
    "MARKET_DATA_API_URL",
    "https://api.twelvedata.com/time_series",
)
MARKET_DATA_API_KEY = os.getenv("MARKET_DATA_API_KEY", "")

MOCK_HISTORY_MONTHS = 121
PREFERRED_HISTORY_YEARS = 10
MINIMUM_PREFERRED_HISTORY_YEARS = 5
MAX_INVESTMENT_YEARS = 60
