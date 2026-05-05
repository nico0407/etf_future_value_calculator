"""Streamlit layout for the ETF Future Value Calculator."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from app_config import (
    APP_CAPTION,
    APP_TITLE,
    DEFAULT_INVESTMENT_YEARS,
    DEFAULT_ISIN_PLACEHOLDER,
    DEFAULT_MONTHLY_INVESTMENT,
    MAX_INVESTMENT_YEARS,
)
from utilities import currency_prefix, format_currency, format_percentage


def configure_page() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        layout="centered",
    )


def show_header() -> None:
    st.title(APP_TITLE)
    st.caption(APP_CAPTION)


def show_input_form() -> tuple[bool, str, float, int]:
    with st.form("future_value_form"):
        isin = st.text_input("ETF ISIN", placeholder=DEFAULT_ISIN_PLACEHOLDER)
        monthly_amount = st.number_input(
            "Monthly investment",
            min_value=0.0,
            value=DEFAULT_MONTHLY_INVESTMENT,
            step=50.0,
            format="%.2f",
        )
        years = st.number_input(
            "Investment horizon in years",
            min_value=1,
            max_value=MAX_INVESTMENT_YEARS,
            value=DEFAULT_INVESTMENT_YEARS,
            step=1,
        )
        submitted = st.form_submit_button("Calculate future value", type="primary")

    return submitted, isin, float(monthly_amount), int(years)


def show_historical_input_form() -> tuple[bool, str, date, float]:
    with st.form("historical_accumulation_form"):
        isin = st.text_input("ETF ISIN", placeholder=DEFAULT_ISIN_PLACEHOLDER, key="historical_isin")
        start_date = st.date_input(
            "Plan start date",
            value=date(2020, 1, 1),
            min_value=date(1990, 1, 1),
            max_value=date.today(),
        )
        monthly_amount = st.number_input(
            "Monthly investment",
            min_value=0.0,
            value=DEFAULT_MONTHLY_INVESTMENT,
            step=50.0,
            format="%.2f",
            key="historical_monthly_amount",
        )
        submitted = st.form_submit_button("Calculate historical accumulation", type="primary")

    return submitted, isin, start_date, float(monthly_amount)


def show_input_errors(errors: list[str]) -> None:
    for error in errors:
        st.error(error)


def show_data_notices(metadata: dict, prices: pd.DataFrame, return_estimate: dict) -> None:
    if metadata.get("is_mock_data") or prices.attrs.get("is_mock_data"):
        st.warning(
            "This result is using mock ETF metadata or mock historical prices because API data is not configured. "
            "The estimated annual return is illustrative, not the real return for this ETF."
        )
    elif prices.attrs.get("source") == "yfinance":
        st.info("Historical prices are from Yahoo Finance via yfinance.")
    if return_estimate["has_short_history"]:
        st.warning("Less than 5 years of historical prices were available, so the return estimate may be less reliable.")


def show_price_source_notice(metadata: dict, prices: pd.DataFrame) -> None:
    if metadata.get("is_mock_data") or prices.attrs.get("is_mock_data"):
        st.warning("This result is using mock ETF metadata or mock historical prices.")
    elif prices.attrs.get("source") == "yfinance":
        st.info("Historical prices are from Yahoo Finance via yfinance.")


def show_results(
    metadata: dict,
    return_estimate: dict,
    projection: pd.DataFrame,
    yearly_summary: pd.DataFrame,
    yearly_returns: pd.DataFrame,
    monthly_amount: float,
) -> None:
    currency = metadata.get("currency") or "GBP"
    final_row = projection.iloc[-1]
    total_contributed = float(final_row["contributed"])
    future_value = float(final_row["value"])
    growth = float(final_row["growth"])

    st.divider()
    st.subheader(metadata.get("name") or "Resolved ETF")
    st.write(
        f"Ticker: **{metadata.get('display_ticker') or metadata.get('ticker') or 'Not available'}**  |  "
        f"Exchange: **{metadata.get('exchange') or 'Not available'}**"
    )
    st.write(
        "Historical period used: "
        f"**{return_estimate['start_date']} to {return_estimate['end_date']}** "
        f"({return_estimate['years_used']:.1f} years)"
    )
    st.write(f"Return method: **{return_estimate['method']}**")
    st.write(f"Metadata source: **{metadata.get('metadata_source') or 'not available'}**")

    metric_columns = st.columns(3)
    metric_columns[0].metric("Estimated annual return", format_percentage(return_estimate["annual_return"]))
    metric_columns[1].metric("Monthly investment", format_currency(monthly_amount, currency))
    metric_columns[2].metric("Estimated future value", format_currency(future_value, currency))

    metric_columns = st.columns(2)
    metric_columns[0].metric("Total amount contributed", format_currency(total_contributed, currency))
    metric_columns[1].metric("Estimated investment growth", format_currency(growth, currency))

    st.plotly_chart(_build_projection_chart(yearly_summary, currency), use_container_width=True)
    show_yearly_projection_table(yearly_summary, currency)
    show_return_calculation_details(return_estimate, yearly_returns, currency)


def show_historical_accumulation_results(
    metadata: dict,
    accumulation: pd.DataFrame,
    yearly_summary: pd.DataFrame,
    monthly_amount: float,
    requested_start_date: date,
) -> None:
    currency = metadata.get("currency") or "GBP"
    final_row = accumulation.iloc[-1]
    first_row = accumulation.iloc[0]
    total_contributed = float(final_row["contributed"])
    current_value = float(final_row["value"])
    growth = float(final_row["growth"])
    percentage_gain = growth / total_contributed if total_contributed else 0.0

    st.divider()
    st.subheader(metadata.get("name") or "Resolved ETF")
    st.write(
        f"Ticker: **{metadata.get('display_ticker') or metadata.get('ticker') or 'Not available'}**  |  "
        f"Exchange: **{metadata.get('exchange') or 'Not available'}**"
    )
    st.write(
        f"Actual accumulation period: **{first_row['date']} to {final_row['date']}** "
        f"({len(accumulation)} monthly purchases)"
    )
    if pd.Timestamp(requested_start_date).date() < first_row["date"]:
        st.warning(
            f"You selected **{requested_start_date}**, but the first available historical price "
            f"for this ticker is **{first_row['date']}**. The computation starts from "
            f"**{first_row['date']}**."
        )
    st.write(f"Metadata source: **{metadata.get('metadata_source') or 'not available'}**")

    metric_columns = st.columns(3)
    metric_columns[0].metric("Monthly investment", format_currency(monthly_amount, currency))
    metric_columns[1].metric("Total amount contributed", format_currency(total_contributed, currency))
    metric_columns[2].metric("Current estimated value", format_currency(current_value, currency))

    metric_columns = st.columns(2)
    metric_columns[0].metric("Estimated investment growth", format_currency(growth, currency))
    metric_columns[1].metric("Percentage gain", format_percentage(percentage_gain))

    st.metric("Total units accumulated", f"{float(final_row['total_units']):,.4f}")

    st.plotly_chart(_build_historical_accumulation_chart(yearly_summary, currency), use_container_width=True)
    show_historical_yearly_table(yearly_summary, currency)
    show_historical_monthly_table(accumulation, currency)


def show_historical_yearly_table(yearly_summary: pd.DataFrame, currency: str) -> None:
    display_table = yearly_summary.copy()
    display_table["year"] = display_table["year"].astype(str)
    display_table["period_end_date"] = display_table["period_end_date"].astype(str)
    display_table["total_contributed"] = display_table["total_contributed"].map(
        lambda value: format_currency(value, currency)
    )
    display_table["current_value_at_period_end"] = display_table["current_value_at_period_end"].map(
        lambda value: format_currency(value, currency)
    )
    display_table["investment_growth"] = display_table["investment_growth"].map(
        lambda value: format_currency(value, currency)
    )
    display_table["total_units"] = display_table["total_units"].map(lambda value: f"{value:,.4f}")
    display_table = display_table.rename(
        columns={
            "year": "Year",
            "period_end_date": "Period-end date",
            "total_contributed": "Total contributed",
            "current_value_at_period_end": "Value at period end",
            "investment_growth": "Investment growth",
            "total_units": "Total units",
        }
    )
    st.subheader("Historical accumulation by year")
    st.dataframe(display_table, use_container_width=True, hide_index=True)


def show_historical_monthly_table(accumulation: pd.DataFrame, currency: str) -> None:
    display_table = accumulation.copy()
    display_table["date"] = display_table["date"].astype(str)
    display_table["year"] = display_table["year"].astype(str)
    display_table["price"] = display_table["price"].map(lambda value: format_currency(value, currency))
    display_table["monthly_contribution"] = display_table["monthly_contribution"].map(
        lambda value: format_currency(value, currency)
    )
    display_table["units_bought"] = display_table["units_bought"].map(lambda value: f"{value:,.4f}")
    display_table["total_units"] = display_table["total_units"].map(lambda value: f"{value:,.4f}")
    display_table["contributed"] = display_table["contributed"].map(lambda value: format_currency(value, currency))
    display_table["value"] = display_table["value"].map(lambda value: format_currency(value, currency))
    display_table["growth"] = display_table["growth"].map(lambda value: format_currency(value, currency))
    display_table = display_table.rename(
        columns={
            "date": "Purchase date",
            "year": "Year",
            "price": "Adjusted close",
            "monthly_contribution": "Monthly contribution",
            "units_bought": "Units bought",
            "total_units": "Total units",
            "contributed": "Total contributed",
            "value": "Value at that date",
            "growth": "Growth",
        }
    )
    with st.expander("Monthly purchase details"):
        st.dataframe(display_table, use_container_width=True, hide_index=True)


def show_yearly_projection_table(yearly_summary: pd.DataFrame, currency: str) -> None:
    display_table = yearly_summary.copy()
    display_table["total_contributed"] = display_table["total_contributed"].map(
        lambda value: format_currency(value, currency)
    )
    display_table["estimated_value"] = display_table["estimated_value"].map(
        lambda value: format_currency(value, currency)
    )
    display_table["estimated_growth"] = display_table["estimated_growth"].map(
        lambda value: format_currency(value, currency)
    )
    display_table = display_table.rename(
        columns={
            "year": "Year",
            "total_contributed": "Total contributed",
            "estimated_value": "Estimated value",
            "estimated_growth": "Estimated growth",
        }
    )
    st.subheader("Year-by-year projection")
    st.dataframe(display_table, use_container_width=True, hide_index=True)


def show_return_calculation_details(
    return_estimate: dict,
    yearly_returns: pd.DataFrame,
    currency: str,
) -> None:
    st.divider()
    st.subheader("Return calculation")
    st.write(
        "The app uses CAGR, which means compound annual growth rate. CAGR answers this question: "
        "what steady yearly return would turn the start price into the end price over the selected "
        "historical period?"
    )
    st.write(
        "This is different from a simple average of yearly returns because it includes compounding. "
        "That makes it a better fit for projecting an investment that grows month after month."
    )
    st.code(
        "CAGR = (end_price / start_price) ** (1 / years) - 1\n"
        f"CAGR = ({return_estimate['end_price']:.4f} / {return_estimate['start_price']:.4f}) "
        f"** (1 / {return_estimate['years_used']:.4f}) - 1\n"
        f"CAGR = {format_percentage(return_estimate['annual_return'])}",
        language="text",
    )
    st.write(
        f"Price window: **{return_estimate['start_date']}** to **{return_estimate['end_date']}**. "
        f"Target history: **{return_estimate['target_years']} years**. "
        f"Actual history used: **{return_estimate['years_used']:.2f} years**."
    )

    display_returns = yearly_returns.copy()
    display_returns["year"] = display_returns["year"].astype(str)
    display_returns["year_end_price"] = display_returns["year_end_price"].map(
        lambda value: format_currency(value, currency)
    )
    display_returns["previous_year_end_price"] = display_returns["previous_year_end_price"].map(
        lambda value: format_currency(value, currency)
    )
    display_returns["yearly_return"] = display_returns["yearly_return"].map(format_percentage)
    display_returns["year_end_date"] = display_returns["year_end_date"].astype(str)
    display_returns = display_returns.rename(
        columns={
            "year": "Year",
            "year_end_date": "Year-end date",
            "previous_year_end_price": "Previous year-end price",
            "year_end_price": "Year-end price",
            "yearly_return": "Yearly return",
        }
    )
    st.subheader("Historical yearly returns")
    st.dataframe(display_returns, use_container_width=True, hide_index=True)


def _build_projection_chart(yearly_summary: pd.DataFrame, currency: str):
    chart_data = yearly_summary.rename(
        columns={
            "year": "Year",
            "estimated_value": "Estimated value",
            "total_contributed": "Total contributed",
        }
    )
    fig = px.line(
        chart_data,
        x="Year",
        y=["Estimated value", "Total contributed"],
        markers=True,
        labels={"value": "Amount", "variable": ""},
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=20, b=0),
        hovermode="x unified",
        yaxis_tickprefix=currency_prefix(currency),
        legend_title_text="",
    )
    return fig


def _build_historical_accumulation_chart(yearly_summary: pd.DataFrame, currency: str):
    chart_data = yearly_summary.rename(
        columns={
            "year": "Year",
            "current_value_at_period_end": "Value",
            "total_contributed": "Total contributed",
        }
    )
    fig = px.line(
        chart_data,
        x="Year",
        y=["Value", "Total contributed"],
        markers=True,
        labels={"value": "Amount", "variable": ""},
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=20, b=0),
        hovermode="x unified",
        yaxis_tickprefix=currency_prefix(currency),
        legend_title_text="",
    )
    return fig
