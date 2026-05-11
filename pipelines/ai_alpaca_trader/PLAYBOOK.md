# AI Swing Trader Playbook

## Strategy: Fundamental Swing Trading
1. **Analyze:** Run `python3 ~/pipelines/ai_alpaca_trader/fundamental_scanner.py` to find stocks with strong fundamentals (e.g., low PEG ratio, reasonable P/E) that present good value. Review `Open Positions` and `Pending/Open Orders`.
2. **Order Cleanup:** If there are stale "Pending" entry orders from previous days that never filled, cancel them using `python3 ~/pipelines/ai_alpaca_trader/cancel_orders.py --symbol <TICKER>` to free up buying power.
3. **Contextualize:** Use web search to read recent earnings call summaries, analyst upgrades, and macro news for the top candidate tickers.
4. **Execute:** Buy using `python3 ~/pipelines/ai_alpaca_trader/execute_trade.py`. **Important:** To avoid missed fills on fast-moving stocks, calculate your entry Limit Price as a "Marketable Limit" with a slight premium (`Current Price * 1.002`). Hold duration is typically days to weeks.
5. **Risk Management:** Use GTC (Good 'Til Canceled) OCO brackets. Because this is swing trading, use wider targets: Take Profit at +10% to +15%, Stop Loss at -5% to -8%. Maximum 5 open positions concurrently. Only trade stocks priced at $10.00 or above.
6. **Monitoring:** Review positions daily. Do NOT flatten at the end of the day. Allow the bracket orders to manage exits, OR manually intervene if your news research shows fundamentals have drastically degraded. To manually exit a trade before it hits its bracket targets, run `python3 ~/pipelines/ai_alpaca_trader/close_position.py --symbol <TICKER>`.
