import yfinance as yf
for ticker in ['MU', 'NVDA', 'QCOM']:
    data = yf.download(ticker, period='1d', interval='5m')
    print(f"--- {ticker} ---")
    print(data[['Low', 'High']].tail(3))
