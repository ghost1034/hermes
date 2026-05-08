# AI Day Trader Playbook

## Strategy: Intraday Momentum & News
1. **Analyze:** Check `market_scanner.py` for portfolio status and current open positions.
2. **Contextualize:** Use web search to scan for intraday breaking news, volatility alerts, and trending tickers over the last 15-30 minutes.
3. **Execute:** If a strong intraday momentum setup is found, buy using `execute_trade.py`. Actively seek out multiple trading opportunities throughout the day.
4. **Risk Management:** Always use OCO brackets (Take Profit at +3%, Stop Loss at -1.5% for tighter day-trade risk). Maximum 5 open positions concurrently. Only trade stocks priced at $10.00 or above.
