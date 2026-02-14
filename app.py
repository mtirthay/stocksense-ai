from PIL import Image
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests

# ---------------- Page config with custom icon ----------------

icon = Image.open("SS logo.png")

st.set_page_config(
    page_title="StockSense AI",
    page_icon=icon,
    layout="wide",
)

# ---------------- Constants (put your real NewsAPI key here) ----------------

NEWSAPI_KEY = "YOUR_NEWSAPI_KEY_HERE"  # all users will use this key

# ---------------- Session init ----------------

if "favourites" not in st.session_state:
    st.session_state["favourites"] = []
if "ticker_prefill" not in st.session_state:
    st.session_state["ticker_prefill"] = "AAPL"
if "last_ticker_df" not in st.session_state:
    st.session_state["last_ticker_df"] = pd.DataFrame()

# ---------------- US ticker strip (7 tickers) ----------------

TOP_US_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]


def get_us_watchlist_prices(symbols: list[str]) -> pd.DataFrame:
    """Fetch latest daily close for a list of US tickers using yfinance."""
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
    update = st.button("Update tickers", key="update_tickers")

    if update:
        df = get_us_watchlist_prices(TOP_US_TICKERS)
        st.session_state["last_ticker_df"] = df
    else:
        df = st.session_state["last_ticker_df"]
        if df.empty:
            df = get_us_watchlist_prices(TOP_US_TICKERS)
            st.session_state["last_ticker_df"] = df

    if df.empty:
        st.caption("Tickers unavailable right now.")
        return

    cols = st.columns(len(df))
    for col, (_, row) in zip(cols, df.iterrows()):
        color = "green" if row["change"] >= 0 else "red"
        sym = row["symbol"]
        with col:
            if st.button(sym, key=f"ticker_{sym}"):
                st.session_state["ticker_prefill"] = sym
            st.write(f"{row['last']:,.2f}")
            st.markdown(
                f"<span style='color:{color};'>"
                f"{row['change']:+.2f} ({row['pct']:+.2f}%)"
                f"</span>",
                unsafe_allow_html=True,
            )

# ---------------- Price data helpers ----------------

def fetch_yahoo_data(ticker: str, period: str) -> pd.DataFrame:
    data = yf.download(ticker.strip(), period=period, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = [c[0] for c in data.columns]
    return data


def get_best_price_data(ticker: str, period: str) -> tuple[pd.DataFrame, str]:
    data = fetch_yahoo_data(ticker, period)
    if not data.empty:
        return data, "Yahoo Finance"
    raise RuntimeError("No data from Yahoo Finance.")

# ---------------- News helper (NewsAPI.org, shared key) ----------------

def get_stock_news(ticker: str, max_articles: int = 5) -> list[dict]:
    if not NEWSAPI_KEY:
        st.caption("NewsAPI key is not configured in the app code.")
        return []

    url = "https://newsapi.org/v2/everything"
    params = {
        "q": ticker.strip(),
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": max_articles,
        "apiKey": NEWSAPI_KEY,
    }  # [web:438]
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "ok":
            st.caption(f"NewsAPI error: {data.get('code', '')} {data.get('message', '')}")
            return []

        return data.get("articles", [])
    except Exception as e:
        st.caption(f"News request failed: {e}")
        return []

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
    if st.sidebar.button("Load selected", key="load_fav"):
        st.session_state["ticker_prefill"] = selected_fav
else:
    st.sidebar.caption("No favourites yet. Add from the main view.")

st.write(
    "Enter a stock ticker to see historical data (up to 10 years), an experimental outlook, "
    "and the latest news headlines on that stock."
)

default_ticker = st.session_state.get("ticker_prefill", "AAPL")
ticker = st.text_input("Ticker symbol", value=default_ticker)

period = st.selectbox(
    "History period",
    ["1mo", "3mo", "6mo", "1y", "5y", "10y"],
    index=3,
)

if st.button("Get data", key="get_data"):
    if not ticker.strip():
        st.warning("Please enter a ticker symbol.")
    else:
        try:
            data, source_name = get_best_price_data(ticker, period)

            if data.empty:
                st.error("No data returned. Please check the ticker symbol.")
            else:
                price_col = "Close" if "Close" in data.columns else "Adj Close"
                prices = data[price_col].dropna()
                if prices.empty:
                    st.error("Price data is empty from the provider.")
                else:
                    last_close = prices.iloc[-1]

                    n_rows = len(data)
                    high_series = data["High"] if "High" in data.columns else prices
                    low_series = data["Low"] if "Low" in data.columns else prices

                    if n_rows >= 252:
                        high_52w = high_series.rolling(window=252).max().iloc[-1]
                        low_52w = low_series.rolling(window=252).min().iloc[-1]
                    else:
                        high_52w = high_series.max()
                        low_52w = low_series.min()

                    data["MA20"] = prices.rolling(window=20).mean()
                    data["MA50"] = prices.rolling(window=50).mean()

                    # Favourites
                    current_symbol = ticker.strip().upper()
                    fav_list = st.session_state["favourites"]
                    is_fav = current_symbol in fav_list

                    fav_col1, fav_col2 = st.columns(2)
                    with fav_col1:
                        if not is_fav and st.button("Add to favourites", key="add_fav"):
                            fav_list.append(current_symbol)
                            st.session_state["favourites"] = sorted(set(fav_list))
                            st.session_state["ticker_prefill"] = current_symbol
                    with fav_col2:
                        if is_fav and st.button("Remove from favourites", key="remove_fav"):
                            fav_list = [s for s in fav_list if s != current_symbol]
                            st.session_state["favourites"] = fav_list

                    # Main chart + stats
                    st.subheader(f"Price history for {ticker.upper()} ({period})")
                    st.caption(f"Data source: {source_name}")

                    plot_cols = [c for c in [price_col, "MA20", "MA50"] if c in data.columns]
                    st.line_chart(data[plot_cols])

                    col1, col2, col3 = st.columns(3)
                    col1.metric("Last close", f"{last_close:,.2f}")
                    col2.metric("Approx 52‑week high", f"{high_52w:,.2f}")
                    col3.metric("Approx 52‑week low", f"{low_52w:,.2f}")

                    st.subheader("Recent data")
                    st.dataframe(data.tail(10))

                    # Outlook
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

                    # ---------------- Latest news section ----------------
                    st.subheader(f"Latest news for {current_symbol}")

                    articles = get_stock_news(current_symbol, max_articles=5)
                    if not articles:
                        st.caption("No news articles returned for this query.")
                    else:
                        for art in articles:
                            title = art.get("title", "No title")
                            source = (art.get("source") or {}).get("name", "Unknown source")
                            published = art.get("publishedAt", "")[:19].replace("T", " ")
                            url = art.get("url", "")
                            desc = art.get("description") or ""
                            st.markdown(f"**{title}**")
                            st.caption(f"{source} · {published}")
                            if desc:
                                st.write(desc)
                            if url:
                                st.markdown(f"[Read full article]({url})")
                            st.markdown("---")

        except Exception as e:
            st.error(f"Unable to fetch data: {e}")
