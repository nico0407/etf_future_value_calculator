"""Streamlit app runner for the ETF Future Value Calculator."""

from __future__ import annotations

from datetime import date
import os
import sys

import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx

from computations import (
    calculate_yearly_returns,
    create_historical_yearly_summary,
    create_yearly_summary,
    estimate_annual_return,
    simulate_historical_monthly_accumulation,
    simulate_monthly_investment,
)
from layout import (
    configure_page,
    show_data_notices,
    show_header,
    show_historical_accumulation_results,
    show_historical_input_form,
    show_input_errors,
    show_input_form,
    show_price_source_notice,
    show_results,
)
from utilities import clean_isin, get_historical_prices, resolve_isin, validate_isin, validate_monthly_amount, validate_years


def run_with_streamlit_when_needed() -> None:
    """Relaunch the file with Streamlit when VS Code runs it as plain Python."""
    if get_script_run_ctx() is not None:
        return

    os.execv(
        sys.executable,
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            os.path.abspath(__file__),
        ],
    )


def main() -> None:
    configure_page()
    show_header()

    projection_tab, historical_tab = st.tabs(["Future value estimate", "Historical accumulation"])

    with projection_tab:
        run_future_value_estimate()

    with historical_tab:
        run_historical_accumulation()


def run_future_value_estimate() -> None:
    submitted, isin, monthly_amount, years = show_input_form()
    if not submitted:
        return

    cleaned_isin = clean_isin(isin)
    errors = validate_inputs(cleaned_isin, monthly_amount, years)
    if errors:
        show_input_errors(errors)
        return

    with st.spinner("Resolving ETF and estimating historical return..."):
        metadata = resolve_isin(cleaned_isin)
        prices = get_historical_prices(metadata.get("ticker", ""), metadata.get("exchange"))
        return_estimate = estimate_annual_return(prices)
        yearly_returns = calculate_yearly_returns(prices)
        projection = simulate_monthly_investment(
            monthly_amount=monthly_amount,
            years=years,
            annual_return=return_estimate["annual_return"],
        )
        yearly_summary = create_yearly_summary(projection)

    show_data_notices(metadata, prices, return_estimate)
    show_results(metadata, return_estimate, projection, yearly_summary, yearly_returns, monthly_amount)


def run_historical_accumulation() -> None:
    submitted, isin, start_date, monthly_amount = show_historical_input_form()
    if not submitted:
        return

    cleaned_isin = clean_isin(isin)
    errors = validate_historical_inputs(cleaned_isin, start_date, monthly_amount)
    if errors:
        show_input_errors(errors)
        return

    with st.spinner("Resolving security and calculating historical accumulation..."):
        metadata = resolve_isin(cleaned_isin)
        prices = get_historical_prices(metadata.get("ticker", ""), metadata.get("exchange"))
        accumulation = simulate_historical_monthly_accumulation(
            prices=prices,
            monthly_amount=monthly_amount,
            start_date=start_date,
        )
        yearly_summary = create_historical_yearly_summary(accumulation)

    show_price_source_notice(metadata, prices)
    show_historical_accumulation_results(metadata, accumulation, yearly_summary, monthly_amount, start_date)


def validate_inputs(isin: str, monthly_amount: float, years: int) -> list[str]:
    errors = []
    if not validate_isin(isin):
        errors.append("Enter a valid ISIN, for example IE00B4L5Y983.")
    if not validate_monthly_amount(monthly_amount):
        errors.append("Monthly investment must be greater than zero.")
    if not validate_years(years):
        errors.append("Investment horizon must be between 1 and 60 years.")
    return errors


def validate_historical_inputs(isin: str, start_date: date, monthly_amount: float) -> list[str]:
    errors = []
    if not validate_isin(isin):
        errors.append("Enter a valid ISIN, for example IE00B4L5Y983.")
    if start_date > date.today():
        errors.append("Plan start date cannot be in the future.")
    if not validate_monthly_amount(monthly_amount):
        errors.append("Monthly investment must be greater than zero.")
    return errors


if __name__ == "__main__":
    run_with_streamlit_when_needed()
    main()
