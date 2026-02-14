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

# ---------------- US ticker strip ----------------

def get_us_watchlist_prices(symbols: list[str]) -> pd.DataFrame:
    """
    Fetch latest daily close for a small list of US tickers using yfinance.
    """
    if not symbols:
        return pd.DataFrame()

    tickers_data = yf.download(
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
            if isinstance(tickers_data.columns, pd.MultiIndex):
                df = tickers_data[symbol]
            else:
                df = tickers_data
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

    return pd.DataFrame(rows)


def render_us_ticker_strip():
    us_watchlist = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]
    df = get_us_watchlist_prices(us_watchlist)
    if df.empty:
        return

    cols = st.columns(len(df))
    for col, (_, row) in zip(cols, df.iterrows()):
        color = "green" if row["change"] >= 0 else "red"
        with col:
            st.markdown(f"**{row['symbol']}**")
            st.write(f"{row['last']:,.2f}")
            st.markdown(
                f"<span style='color:{color};'>"
                f"{row['change']:+.2f} ({row['pct']:+.2f}%)"
                f"</span>",
                unsafe_allow_html=True,
            )

# ---------------- Data helpers ----------------

def fetch_yahoo_data(ticker: str, period: str) -> pd.DataFrame:
    """
    Fetch historical data from Yahoo Finance using yfinance.
    period can be '1mo', '3mo', '6mo', '1y', '5y', '10y', etc.
    """
    data = yf.download(ticker.strip(), period=period, progress=False)

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

# ---------------- Layout ----------------

render_us_ticker_strip()

st.title("StockSense AI")

st.caption(
    "Disclaimer: StockSense AI provides informational estimates only. "
    "Nothing on this page constitutes investment, tax, or financial advice. "
    "Always do your own research or consult a professional advisor."
)

# Sidebar favourites
st.sidebar.subheader("Favourites")
if st.session_state["favourites"]:
    selected_fav = st.sidebar.selectbox(
        "Quick load",
        st.session_state["favourites"],
        key="fav_select",
    )
    if st.sidebar.button("Load selected"):
        st.session_state["ticker_prefill"] = selected_fav
else:
    st.sidebar.caption("No favourites yet. Add from the main view.")

st.write("Enter a stock ticker to see historical data (up to 10 years) and an experimental outlook.")

default_ticker = st.session_state.get("ticker_prefill", "AAPL")
ticker = st.text_input("Ticker symbol", value=default_ticker)

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

                    # --- Favourite controls ---
                    current_symbol = ticker.strip().upper()
                    fav_list = st.session_state["favourites"]
                    is_fav = current_symbol in fav_list

                    fav_col1, fav_col2 = st.columns(2)
                    with fav_col1:
                        if not is_fav and st.button("Add to favourites"):
                            fav_list.append(current_symbol)
                            st.session_state["favourites"] = sorted(set(fav_list))
                    with fav_col2:
                        if is_fav and st.button("Remove from favourites"):
                            fav_list = [s for s in fav_list if s != current_symbol]
                            st.session_state["favourites"] = fav_list

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
