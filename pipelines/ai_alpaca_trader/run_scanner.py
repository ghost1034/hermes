import subprocess
with open("/home/ianstewart/pipelines/ai_alpaca_trader/out.txt", "w") as f:
    result = subprocess.run(['python', '/home/ianstewart/pipelines/ai_alpaca_trader/fundamental_scanner.py'], capture_output=True, text=True)
    f.write("STDOUT:\n" + result.stdout + "\n")
    f.write("STDERR:\n" + result.stderr + "\n")
