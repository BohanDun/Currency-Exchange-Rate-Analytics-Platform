"""Interactive Streamlit dashboard for exchange-rate analytics."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import Engine

from dashboard.data import get_filter_options, load_dashboard_data
from src.database.connection import create_database_engine
from src.utils.config import load_config

st.set_page_config(
    page_title="FX Analytics",
    page_icon="↗",
    layout="wide",
    initial_sidebar_state="expanded",
)

COLORS = {
    "navy": "#102A43",
    "blue": "#2F80ED",
    "teal": "#00A6A6",
    "orange": "#F2994A",
    "red": "#D64545",
    "muted": "#6B7C93",
}

st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem; padding-bottom: 3rem;}
      [data-testid="stMetric"] {
        background: #F7F9FC;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 16px;
      }
      .dashboard-kicker {
        color: #2F80ED; font-weight: 700; letter-spacing: .08em;
        text-transform: uppercase; font-size: .78rem;
      }
      .dashboard-subtitle {color: #6B7C93; margin-top: -.6rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_engine() -> Engine:
    """Create one pooled database engine for the Streamlit process."""
    load_config()  # Loads the local .env before database settings are read.
    return create_database_engine()


@st.cache_data(ttl=300)
def cached_filter_options() -> tuple[list[str], date, date]:
    return get_filter_options(get_engine())


@st.cache_data(ttl=300)
def cached_dashboard_data(
    currency_pair: str, start_date: date, end_date: date
) -> dict[str, pd.DataFrame]:
    return load_dashboard_data(get_engine(), currency_pair, start_date, end_date)


def percent(value: float | None) -> str:
    return "—" if value is None or pd.isna(value) else f"{value:.3f}%"


def render_dashboard() -> None:
    st.markdown('<div class="dashboard-kicker">Market intelligence</div>', unsafe_allow_html=True)
    st.title("Currency Exchange Rate Analytics")
    st.markdown(
        '<p class="dashboard-subtitle">Daily trends, returns, volatility and explainable anomaly detection.</p>',
        unsafe_allow_html=True,
    )

    try:
        pairs, minimum_date, maximum_date = cached_filter_options()
    except Exception as exc:
        st.error(f"Unable to load dashboard filters: {exc}")
        st.info("Confirm PostgreSQL is running, then execute the historical pipeline.")
        st.stop()

    with st.sidebar:
        st.header("Filters")
        selected_pair = st.selectbox("Currency pair", pairs, index=pairs.index("EUR/USD") if "EUR/USD" in pairs else 0)
        selected_dates = st.date_input(
            "Date range",
            value=(minimum_date, maximum_date),
            min_value=minimum_date,
            max_value=maximum_date,
        )
        st.caption(f"Available data: {minimum_date:%d %b %Y} – {maximum_date:%d %b %Y}")

    if not isinstance(selected_dates, tuple) or len(selected_dates) != 2:
        st.info("Select both a start date and an end date.")
        st.stop()
    start_date, end_date = selected_dates

    try:
        data = cached_dashboard_data(selected_pair, start_date, end_date)
    except Exception as exc:
        st.error(f"Unable to query analytics data: {exc}")
        st.stop()

    trend = data["trend_query"]
    returns = data["returns_query"]
    volatility = data["volatility_query"]
    anomalies = data["anomaly_query"]
    if trend.empty:
        st.warning("No data exists for the selected filters.")
        st.stop()

    for frame in data.values():
        frame["rate_date"] = pd.to_datetime(frame["rate_date"])

    latest_rate = float(trend["rate"].iloc[-1])
    first_rate = float(trend["rate"].iloc[0])
    period_change = (latest_rate / first_rate - 1) * 100 if first_rate else None
    latest_return = returns["daily_pct_change"].iloc[-1]
    anomaly_count = int(anomalies["is_anomaly"].sum())
    last_updated = pd.to_datetime(trend["ingested_at"].max(), utc=True)

    metric_columns = st.columns(4)
    metric_columns[0].metric("Latest rate", f"{latest_rate:,.5f}", percent(period_change))
    metric_columns[1].metric("Latest daily move", percent(latest_return))
    metric_columns[2].metric("Period range", f"{trend['rate'].min():,.4f} – {trend['rate'].max():,.4f}")
    metric_columns[3].metric("Anomalies", f"{anomaly_count}")

    st.subheader("Exchange-rate trend")
    trend_figure = px.line(trend, x="rate_date", y="rate", color_discrete_sequence=[COLORS["blue"]])
    flagged = anomalies[anomalies["is_anomaly"]].merge(
        trend[["rate_date", "rate"]], on="rate_date", how="left"
    )
    if not flagged.empty:
        trend_figure.add_trace(
            go.Scatter(
                x=flagged["rate_date"],
                y=flagged["rate"],
                mode="markers",
                name="Anomaly",
                marker={"color": COLORS["red"], "size": 8, "symbol": "diamond"},
            )
        )
    trend_figure.update_layout(yaxis_title=selected_pair, xaxis_title=None, hovermode="x unified")
    st.plotly_chart(trend_figure, width="stretch")

    left, right = st.columns(2)
    with left:
        st.subheader("Daily return")
        return_colors = [COLORS["teal"] if value >= 0 else COLORS["red"] for value in returns["daily_pct_change"].fillna(0)]
        return_figure = go.Figure(
            go.Bar(
                x=returns["rate_date"],
                y=returns["daily_pct_change"],
                marker_color=return_colors,
                hovertemplate="%{x|%d %b %Y}<br>%{y:.3f}%<extra></extra>",
            )
        )
        return_figure.update_layout(xaxis_title=None, yaxis_title="Daily change (%)")
        st.plotly_chart(return_figure, width="stretch")

    with right:
        st.subheader("Rolling volatility")
        volatility_plot = volatility.rename(
            columns={
                "rolling_volatility_7": "7 observations",
                "rolling_volatility_30": "30 observations",
            }
        )
        volatility_figure = px.line(
            volatility_plot,
            x="rate_date",
            y=["7 observations", "30 observations"],
            color_discrete_sequence=[COLORS["orange"], COLORS["navy"]],
        )
        volatility_figure.update_layout(
            xaxis_title=None,
            yaxis_title="Standard deviation",
            legend_title=None,
            hovermode="x unified",
        )
        st.plotly_chart(volatility_figure, width="stretch")

    st.subheader("Abnormal movements")
    anomaly_figure = go.Figure(
        go.Scatter(
            x=anomalies["rate_date"],
            y=anomalies["anomaly_score"],
            mode="markers",
            marker={
                "color": [
                    COLORS["red"] if is_anomaly else COLORS["muted"]
                    for is_anomaly in anomalies["is_anomaly"]
                ],
                "size": [7 if is_anomaly else 4 for is_anomaly in anomalies["is_anomaly"]],
                "opacity": 0.75,
            },
            hovertemplate="%{x|%d %b %Y}<br>Z-score %{y:.2f}<extra></extra>",
        )
    )
    anomaly_figure.add_hline(y=2, line_dash="dash", line_color=COLORS["red"])
    anomaly_figure.add_hline(y=-2, line_dash="dash", line_color=COLORS["red"])
    anomaly_figure.update_layout(xaxis_title=None, yaxis_title="Prior-30 z-score")
    st.plotly_chart(anomaly_figure, width="stretch")

    anomaly_table = anomalies[anomalies["is_anomaly"]].copy()
    if anomaly_table.empty:
        st.success("No abnormal movements were detected in this period.")
    else:
        anomaly_table["daily_return_pct"] = anomaly_table["daily_return"] * 100
        anomaly_table = anomaly_table[
            ["rate_date", "daily_return_pct", "anomaly_score", "anomaly_reason"]
        ].sort_values("anomaly_score", key=lambda values: values.abs(), ascending=False)
        st.dataframe(
            anomaly_table,
            width="stretch",
            hide_index=True,
            column_config={
                "rate_date": st.column_config.DateColumn("Date", format="DD MMM YYYY"),
                "daily_return_pct": st.column_config.NumberColumn("Daily change", format="%.3f%%"),
                "anomaly_score": st.column_config.NumberColumn("Z-score", format="%.2f"),
                "anomaly_reason": "Reason",
            },
        )

    st.caption(
        f"Source: Frankfurter API · Last ingested {last_updated:%d %b %Y %H:%M UTC} · "
        "Volatility uses complete 7/30-observation windows."
    )


render_dashboard()
