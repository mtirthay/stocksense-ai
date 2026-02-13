import streamlit as st
import yfinance as yf
import pandas as pd

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
            if data.empty:
                st.error("No data returned. Check the ticker symbol.")
            else:
                st.subheader(f"Closing prices for {ticker.upper()} ({period})")
                st.line_chart(data["Close"])
                st.subheader("Raw data")
                st.dataframe(data.tail(10))
        except Exception as e:
            st.error(f"Error fetching data: {e}")
