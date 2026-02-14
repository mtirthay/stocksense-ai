import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests

# ---------------- Helper functions ----------------

def fetch_yahoo_data(ticker: str, period: str) -> pd.DataFrame:
    """
    Fetch historical data from Yahoo Finance using yfinance.
    period can be '1mo', '3mo', '6mo', '1y', '5y', '10y', etc.
    """
    data = yf.download(ticker.strip(), period=period)

    # Flatten multi-index columns if needed
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = [c[0] for c in data.columns]

    return data


def fetch_alpha_vantage_data(ticker: str, period: str, api_key: str) -> pd.DataFrame:
    """
    Fetch daily prices from Alpha Vantage and roughly map your period options
    up to 10 years.
    """
    # Map period to approximate trading days
    period_to_days = {
        "1mo": 22,
        "3mo": 66,
        "6mo": 132,
        "1y": 252,
        "5y": 252 * 5,
        "10y": 252 * 10,
    }
    days = period_to_days.get(period, 252)

    # For <= 1y use compact, for longer use full
    outputsize = "compact" if days <= 252 else "full"

    url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": ticker.strip(),
        "apikey": api_key,
        "outputsize": outputsize,
        "datatype": "json",
    }

    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    raw = resp.json()

    if "Time Series (Daily)" not in raw:
        raise ValueError(
            f"Alpha Vantage error or limit hit: "
            f"{raw.get('Note') or raw.get('Error Message') or 'unknown error'}"
        )

    ts = raw["Time Series (Daily)"]

    df = pd.DataFrame.from_dict(ts, orient="index", dtype=float)
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)

    # Standardize column names
    df.rename(
        columns={
            "1. open": "Open",
            "2. high": "High",
            "3. low": "Low",
            "4. close": "Close",
            "5. adjusted close": "Adj Close",
            "6. volume": "Volume",
        },
        inplace=True,
    )

    # Only keep the needed number of days from the end
    return df.tail(days)


def get_best_price_data(ticker: str, period: str) -> tuple[pd.DataFrame, str]:
    """
    Try multiple providers and return (data, source_name).
    Current order: Yahoo Finance -> Alpha Vantage.
    """
    errors = []

    # 1. Yahoo Finance
    try:
        data = fetch_yahoo_data(ticker, period)
        if not data.empty:
            return data, "Yahoo Finance"
    except Exception as e:
        errors.append(f"Yahoo: {e}")

    # 2. Alpha Vantage
    try:
        api_key = st.secrets["alphavantage"]["api_key"]
        data = fetch_alpha_vantage_data(ticker, period, api_key)
        if not data.empty:
            return data, "Alpha Vantage"
    except Exception as e:
        errors.append(f"Alpha Vantage: {e}")

    raise RuntimeError("All data providers failed: " + " | ".join(errors))


# ---------------- Main app ----------------

st.title("StockSense AI")

st.caption(
    "Disclaimer: StockSense AI provides informational estimates only. "
    "Nothing on this page constitutes investment, tax, or financial advice. "
    "Always do your own research or consult a professional advisor."
)

st.write("Enter a stock ticker to see historical data (up to 10 years) and an experimental outlook.")

ticker = st.text_input("Ticker symbol", value="AAPL")

period = st.selectbox(
    "History period",
    ["1mo", "3mo", "6mo", "1y", "5y", "10y"],
    index=3,  # default to 1y
)

if st.button("Get data"):
    if not ticker.strip():
        st.warning("Please enter a ticker symbol.")
    else:
        try:
            data, source_name = get_best_price_data(ticker, period)

            if data.empty:
                st.error("No data returned. Please check the ticker symbol.")
            else:
                # Decide which price column to use
                price_col = "Close" if "Close" in data.columns else "Adj Close"

                prices = data[price_col].dropna()
                if prices.empty:
                    st.error("Price data is empty from all providers.")
                else:
                    last_close = prices.iloc[-1]

                    # --- 52-week high/low with fallback ---
                    n_rows = len(data)

                    if "High" in data.columns:
                        high_series = data["High"]
                    else:
                        high_series = prices

                    if "Low" in data.columns:
                        low_series = data["Low"]
                    else:
                        low_series = prices

                    if n_rows >= 252:
                        high_52w = high_series.rolling(window=252).max().iloc[-1]
                        low_52w = low_series.rolling(window=252).min().iloc[-1]
                    else:
                        # Not enough data for 52 weeks: use max/min of available history
                        high_52w = high_series.max()
                        low_52w = low_series.min()

                    # Moving averages
                    data["MA20"] = prices.rolling(window=20).mean()
                    data["MA50"] = prices.rolling(window=50).mean()

                    # --- Chart and stats ---
                    st.subheader(f"Price history for {ticker.upper()} ({period})")
                    st.caption(f"Data source selected automatically: {source_name}")

                    plot_cols = [c for c in [price_col, "MA20", "MA50"] if c in data.columns]
                    st.line_chart(data[plot_cols])

                    col1, col2, col3 = st.columns(3)
                    col1.metric("Last close", f"{last_close:,.2f}")
                    col2.metric("Approx 52‑week high", f"{high_52w:,.2f}")
                    col3.metric("Approx 52‑week low", f"{low_52w:,.2f}")

                    st.subheader("Recent data")
                    st.dataframe(data.tail(10))

                    # -------- Price outlook (very simple model) --------
                    st.subheader("Price outlook (experimental)")
                    st.caption(
                        "This section uses a simple mathematical projection based on recent daily returns. "
                        "It is highly uncertain and for educational purposes only."
                    )

                    if len(prices) > 60:
                        returns = prices.pct_change().dropna()
                        avg_daily = returns.mean()

                        horizons = {
                            "1 week": 5,
                            "1 month": 21,
                            "3 months": 63,
                            "6 months": 126,
                            "12 months": 252,
                        }

                        cols = st.columns(len(horizons))

                        for (label, days), col in zip(horizons.items(), cols):
                            projected = last_close * (1 + avg_daily * days)
                            col.metric(label, f"{projected:,.2f}")
                    else:
                        st.info("Not enough historical data to generate an outlook.")

                    st.warning(
                        "Disclaimer: These projections are simple extrapolations of past returns and "
                        "do not account for news, fundamentals, or market events. They are not "
                        "financial advice and actual future prices can differ significantly."
                    )

        except Exception as e:
            st.error(f"Unable to fetch data from available providers: {e}")
