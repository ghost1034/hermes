import subprocess
try:
    print(subprocess.check_output(["python3", "/home/ianstewart/bots/alpaca/replay_backtest.py", "/home/ianstewart/bots/alpaca/dummy.csv"], text=True))
except subprocess.CalledProcessError as e:
    print("ERROR:")
    print(e.output)
