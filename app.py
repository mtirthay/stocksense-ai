import streamlit as st
import yfinance as yf
import pandas as pd

def login_screen():
    st.title("StockSense AI")
    st.write("Please log in with Google to continue.")
    st.button("Log in with Google", on_click=st.login)

def main_app():
    st.title("StockSense AI")

    st.write("Enter a stock ticker to see recent price data.")

    ticker = st.text_input("Ticker symbol", value="AAPL")
    period = st.selectbox("History period", ["1mo", "3mo", "6mo", "1y"], index=1)

    if st.button("Get data"):
        if ticker.strip() == "":
            st.warning("Please enter a ticker symbol.")
        else:
            try:
                data = yf.download(ticker.strip(), period=period)

                # If yfinance returns multi-level columns, flatten them
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = [c[0] for c in data.columns]

                if data.empty:
                    st.error("No data returned. Check the ticker symbol.")
                else:
                    # Basic stats
                    last_close = data["Close"].iloc[-1]
                    high_52w = data["High"].rolling(window=252).max().iloc[-1]
                    low_52w = data["Low"].rolling(window=252).min().iloc[-1]

                    # Moving averages
                    data["MA20"] = data["Close"].rolling(window=20).mean()
                    data["MA50"] = data["Close"].rolling(window=50).mean()

                    st.subheader(f"Closing prices for {ticker.upper()} ({period})")
                    plot_cols = [col for col in ["Close", "MA20", "MA50"] if col in data.columns]
                    st.line_chart(data[plot_cols])

                    col1, col2, col3 = st.columns(3)
                    col1.metric("Last close", f"{last_close:,.2f}")
                    col2.metric("Approx 52‑week high", f"{high_52w:,.2f}")
                    col3.metric("Approx 52‑week low", f"{low_52w:,.2f}")

                    st.subheader("Recent data")
                    st.dataframe(data.tail(10))
            except Exception as e:
                st.error(f"Error fetching data: {e}")

# Authentication entry point
if not st.user.is_logged_in:
    login_screen()
else:
    st.sidebar.write(f"Logged in as {st.user.name}")
    main_app()
