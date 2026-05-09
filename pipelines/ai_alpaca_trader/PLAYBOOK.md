# AI Swing Trader Playbook

## Strategy: Fundamental Swing Trading
1. **Analyze:** Run `python3 ~/pipelines/ai_alpaca_trader/fundamental_scanner.py` to find stocks with strong fundamentals (e.g., low PEG ratio, reasonable P/E) that present good value.
2. **Contextualize:** Use web search to read recent earnings call summaries, analyst upgrades, and macro news for the top candidate tickers.
3. **Execute:** Buy using `execute_trade.py`. Hold duration is typically days to weeks.
4. **Risk Management:** Use GTC (Good 'Til Canceled) OCO brackets. Because this is swing trading, use wider targets: Take Profit at +10% to +15%, Stop Loss at -5% to -8%. Maximum 5 open positions concurrently. Only trade stocks priced at $10.00 or above.
5. **Monitoring:** Review positions daily. Do NOT flatten at the end of the day. Allow the bracket orders to manage exits, OR manually intervene if your news research shows fundamentals have drastically degraded. To manually exit a trade before it hits its bracket targets, run `python3 ~/pipelines/ai_alpaca_trader/close_position.py --symbol <TICKER>`.