import pandas as pd
import alpaca_trade_api as tradeapi

# Test DataFrame groupby
df = pd.DataFrame({'close': [1, 2]}, index=pd.MultiIndex.from_tuples([('AAPL', '2021'), ('AAPL', '2022')], names=['symbol', 'timestamp']))
try:
    for sym, g in df.groupby('symbol'):
         print(sym)
except Exception as e:
    print("Error:", e)
