# Validation

## Unit Tests

Run the pure-logic safety tests without live Alpaca credentials or network access:

```bash
python3 -m unittest discover -s tests
```

The tests install lightweight fake Alpaca modules before importing `daytrader.py`, then validate the risk gates and signal filters directly.

## Replay Harness

Replay historical 1-minute bars through the same core signal filters:

```bash
python3 replay_backtest.py path/to/bars.csv --output backtest_reports/report.json
```

Expected CSV columns:

```text
symbol,timestamp,open,high,low,close,volume
```

The replay harness is intentionally read-only. It does not submit orders, call Alpaca, or simulate fills. It reports detected signals, rejected signals by reason, and candidate entries that pass the Phase 1-3 filters.

Use `--assumed-spread-pct` to stress the spread filter when quote data is not present in the CSV:

```bash
python3 replay_backtest.py path/to/bars.csv --assumed-spread-pct 0.003
```
