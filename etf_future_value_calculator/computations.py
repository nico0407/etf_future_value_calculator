"""Financial computations for the ETF Future Value Calculator."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd

from app_config import MINIMUM_PREFERRED_HISTORY_YEARS, PREFERRED_HISTORY_YEARS


def calculate_cagr(start_price: float, end_price: float, years: float) -> float:
    """Calculate compound annual growth rate from start/end prices."""
    if start_price <= 0 or end_price <= 0 or years <= 0:
        raise ValueError("Prices and years must be positive to calculate CAGR.")
    return (end_price / start_price) ** (1 / years) - 1


def annual_return_to_monthly_return(annual_return: float) -> float:
    """Convert an annual return into an equivalent compound monthly return."""
    return (1 + annual_return) ** (1 / 12) - 1


def estimate_annual_return(prices: pd.DataFrame) -> Dict[str, Any]:
    """Estimate annual return using up to the most recent 10 years of prices."""
    if prices.empty:
        raise ValueError("No historical prices are available.")

    clean_prices = (
        prices.loc[:, ["date", "adjusted_close"]]
        .dropna()
        .assign(date=lambda frame: pd.to_datetime(frame["date"]))
        .sort_values("date")
        .reset_index(drop=True)
    )
    clean_prices = clean_prices[clean_prices["adjusted_close"] > 0]
    if len(clean_prices) < 2:
        raise ValueError("At least two historical prices are needed.")

    end_date = clean_prices["date"].iloc[-1]
    preferred_start = end_date - pd.DateOffset(years=PREFERRED_HISTORY_YEARS)
    window = clean_prices[clean_prices["date"] >= preferred_start].copy()
    if len(window) < 2:
        window = clean_prices.copy()

    start_date = window["date"].iloc[0]
    actual_years = (end_date - start_date).days / 365.25
    annual_return = calculate_cagr(
        float(window["adjusted_close"].iloc[0]),
        float(window["adjusted_close"].iloc[-1]),
        actual_years,
    )
    start_price = float(window["adjusted_close"].iloc[0])
    end_price_value = float(window["adjusted_close"].iloc[-1])

    return {
        "annual_return": annual_return,
        "start_date": start_date.date(),
        "end_date": end_date.date(),
        "start_price": start_price,
        "end_price": end_price_value,
        "years_used": actual_years,
        "has_short_history": actual_years < MINIMUM_PREFERRED_HISTORY_YEARS,
        "method": "CAGR from adjusted close prices",
        "target_years": PREFERRED_HISTORY_YEARS,
    }


def calculate_yearly_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Calculate calendar-year returns from year-end adjusted close prices."""
    if prices.empty:
        raise ValueError("No historical prices are available.")

    clean_prices = (
        prices.loc[:, ["date", "adjusted_close"]]
        .dropna()
        .assign(date=lambda frame: pd.to_datetime(frame["date"]))
        .sort_values("date")
        .reset_index(drop=True)
    )
    clean_prices = clean_prices[clean_prices["adjusted_close"] > 0]
    clean_prices["year"] = clean_prices["date"].dt.year

    year_end_prices = (
        clean_prices.groupby("year", as_index=False)
        .tail(1)
        .loc[:, ["year", "date", "adjusted_close"]]
        .rename(columns={"date": "year_end_date", "adjusted_close": "year_end_price"})
        .reset_index(drop=True)
    )
    year_end_prices["previous_year_end_price"] = year_end_prices["year_end_price"].shift(1)
    year_end_prices["yearly_return"] = (
        year_end_prices["year_end_price"] / year_end_prices["previous_year_end_price"] - 1
    )

    return year_end_prices.dropna(subset=["yearly_return"]).reset_index(drop=True)


def simulate_monthly_investment(
    monthly_amount: float,
    years: int,
    annual_return: float,
) -> pd.DataFrame:
    """Simulate monthly contributions and compound investment growth."""
    monthly_return = annual_return_to_monthly_return(annual_return)
    portfolio_value = 0.0
    total_contributed = 0.0
    rows = []

    for month in range(1, years * 12 + 1):
        # Contribution is invested first, then the month-end return is applied.
        total_contributed += monthly_amount
        portfolio_value += monthly_amount
        portfolio_value *= 1 + monthly_return

        rows.append(
            {
                "month": month,
                "year": int(np.ceil(month / 12)),
                "contributed": total_contributed,
                "value": portfolio_value,
                "growth": portfolio_value - total_contributed,
            }
        )

    return pd.DataFrame(rows)


def create_yearly_summary(projection: pd.DataFrame) -> pd.DataFrame:
    """Create a year-by-year table from monthly projection data."""
    return (
        projection.sort_values("month")
        .groupby("year", as_index=False)
        .tail(1)
        .loc[:, ["year", "contributed", "value", "growth"]]
        .rename(
            columns={
                "contributed": "total_contributed",
                "value": "estimated_value",
                "growth": "estimated_growth",
            }
        )
        .reset_index(drop=True)
    )
