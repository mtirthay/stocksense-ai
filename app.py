import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests

# ---------------- Session init ----------------

if "favourites" not in st.session_state:
    st.session_state["favourites"] = []
if "ticker_prefill" not in st.session_state:
    st.session_state["ticker_prefill"] = "AAPL"

# ---------------- US blue‑chip ticker strip ----------------

BLUE_CHIP_US = [
    "AAPL", "AMZN", "BA", "BRK-B", "CAT", "CSCO", "CVX", "DIS", "GOOGL",
    "HD", "HON", "IBM", "INTC", "JNJ", "JPM", "KO", "LIN", "LLY", "MA",
    "META", "MRK", "MS", "MSFT", "NFLX", "NVDA", "ORCL", "PEP", "PG",
    "PYPL", "QCOM", "RTX", "T", "TMO", "TSLA", "UNH", "V", "VZ", "WMT",
    "XOM"
]

def get_us_watchlist_prices(symbols: list[str]) -> pd.DataFrame:
    """
    Fetch latest daily close for a list of US tickers using yfinance.
    """
    if not symbols:
        return pd.DataFrame()

    data = yf.download(
        " ".join(symbols),
        period="5d",
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        progress=False,
    )

    rows = []
    for symbol in symbols:
        try:
            if isinstance(data.columns, pd.MultiIndex):
                df = data[symbol]
            else:
                df = data
            last_row = df.iloc[-1]
            prev_row = df.iloc[-2] if len(df) > 1 else df.iloc[-1]
            last_price = float(last_row["Close"])
            prev_price = float(prev_row["Close"])
            change = last_price - prev_price
            pct = (change / prev_price) * 100 if prev_price != 0 else 0.0
            rows.append(
                {
                    "symbol": symbol,
                    "last": last_price,
                    "change": change,
                    "pct": pct,
                }
            )
        except Exception:
            continue

    df_rows = pd.DataFrame(rows)
    if not df_rows.empty:
        df_rows.sort_values("symbol", inplace=True)
    return df_rows


def render_us_ticker_strip():
    st.subheader("US Blue‑chip Snapshot")
    update = st.button("Update tickers")

    if update:
        df = get_us_watchlist_prices(BLUE_CHIP_US)
        st.session_state["last_ticker_df"] = df
    else:
        df = st.session_state.get("last_ticker_df", pd.DataFrame())
        if df.empty:
            df = get_us_watchlist_prices(BLUE_CHIP_US)
            st.session_state["last_ticker_df"] = df

    if df.empty:
        st.caption("Tickers unavailable right now.")
        return

    cols = st.columns(min(len(df), 10))
    for idx, (_, row) in enumerat
