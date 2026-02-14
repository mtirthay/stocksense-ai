import streamlit as st
import yfinance as yf
import pandas as pd
import requests

# ---------- Data source helpers ----------

def fetch_yahoo_data(ticker: str, period: str) -> pd.DataFrame:
    data = yf.download(ticker.strip(), period=period)

    # Flatten multi-index columns if needed
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = [c for c in data.columns]

    return data


def fetch_alpha_vantage_data(ticker: str, period: str, api_key: str) -> pd.DataFrame:
    """
    Fetch daily prices from Alpha Vantage and roughly map your period options.
    Alpha Vantage free tier: 5 calls/minute, 500/day.
    """

    url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": ticker.strip(),
        "apikey": api_key,
        "outputsize": "compact",
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

    # Convert to DataFrame
    df = pd.DataFrame.from_dict(ts, orient="index", dtype=float)
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)

    # Standardize column names to match Yahoo-like structure
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

    # Map your period to approximate trading days
    period_to_days = {
        "1mo": 22,
        "3mo": 66,
        "6mo": 132,
        "1y": 252,
    }
    days = period_to_days.get(period, 66)

    return df.tail(days)


# ---------- Main app ----------

st.title("StockSense AI")

st.write("Enter a stock ticker to see recent price data from multiple sources.")

ticker = st.text_input("Ticker symbol", value="AAPL")

period = st.selectbox("History period", ["1mo", "3mo", "6mo", "1y"], index=1)

data_source = st.selectbox(
    "Data source",
    ["Yahoo Finance", "Alpha Vantage"],
    index=0,
)

if st.button("Get data"):
    if ticker.strip() == "":
        st.warning("Please enter a ticker symbol.")
    else:
        try:
            # Select source
            if data_source == "Yahoo Finance":
                data = fetch_yahoo_data(ticker, period)
            else:
                api_key = st.secrets["alphavantage"]["api_key"]
                data = fetch_alpha_vantage_data(ticker, period, api_key)

            if data.empty:
                st.error("No data returned. Check the ticker symbol or try another source.")
            else:
                # Basic stats
                last_close = data["Close"].iloc[-1]
                high_52w = data["High"].rolling(window=252).max().iloc[-1]
                low_52w = data["Low"].rolling(window=252).min().iloc[-1]

                # Moving averages
                data["MA20"] = data["Close"].rolling(window=20).mean()
                data["MA50"] = data["Close"].rolling(window=50).mean()

                st.subheader(f"{data_source} closing prices for {ticker.upper()} ({period})")
                plot_cols = [col for col in ["Close", "MA20", "MA50"] if col in data.columns]
                st.line_chart(data[plot_cols])

                col1, col2, col3 = st.columns(3)
                col1.metric("Last close", f"{last_close:,.2f}")
                col2.metric("Approx 52‑week high", f"{high_52w:,.2f}")
                col3.metric("Approx 52‑week low", f"{low_52w:,.2f}")

                st.subheader("Recent data")
                st.dataframe(data.tail(10))
        except Exception as e:
            st.error(f"Error fetching data from {data_source}: {e}")
