# Technical-Trading-Bot
Trading Bot built using the Alpaca API in Python. Indicators used for Signal Generation: EMA, StochRSI, and Stochastic Oscillator

## AUTH

1. configFile.txt: To enable/disable the indicators for which the bot will check and generate buy/sell signals. Other parameters such as:
- Trade Params: % Capital to be used / trade, Stop Loss, Trailing Stop, Limit Price, etc can be changed.
- Data Params: Timeframe, Start Date, End Date
- Indicator Params: Indicator parameters can also be changed in the ConfigFile.txt. 
    1. StochRSI: Lower Band, Upper Band, K, D, RSI Length, etc)
    2. Stoch: Lower Band, Upper Band, K Smoothing, D Smoothing
    3. EMA: Period, Smoothing

2. Tickers.txt: Add ticker symbols (seperated by space) to check the critera for
3. authAlpaca.txt: Add Alpaca API Key and Secret Key for the bot to start trading. Change *"BASE-URL"* to *"api.alpaca.markets"* to trade in real-time markets.

## Root Dir

Install dependencies with `python3 -m pip install -r requirements.txt` before running the bot.

1. config_params.py: Initializes all the params set by the user in ConfigFile.txt
2. indicator.py: Calculates values and generates signals for all the indicators enabled 
3. main.py: Signal generation, decision-making, trade execution, trade monitoring, email alerts

The bot stores local audit and cooldown state in the *ORDERS* folder. Alpaca positions and open orders are treated as the source of truth, and these CSVs are reconciled against Alpaca while the bot runs.
1. Orders.csv: CSV file with all the trades (buy and sell both) placed by the bot
2. Open Orders.csv: CSV file with all the open positions held by the bot. The bot will check for returns using this file and sell once the sell criteria (Stop Loss/Limit Price/Trailing Stop) has been met. The bot will remove the position from _Open Orders.csv_ once it's closed.
3. Time and Coins.csv: Using this file, the bot will ensure that no 2 (or more) trades are placed for the same ticker in the _sleep_time_between_trades_ (parameter in ConfigFile.txt) time period. 
Example: If _sleep_time_between_trades_ is 100 seconds and the bot places a buy trade for AAPL, the bot won't check the criteria for AAPL for another 100 seconds. The bot also skips symbols that already have an Alpaca position or pending buy order.

The `end_date` config supports `"now"`/`"today"` for live trading or a parseable historical date for historical data pulls.

Feel free to contact me at tejas.linge101@gmail.com for **ANY** doubts, suggestions, reviews, or to just connect and talk about Algo Trading Projects. Thanks!
