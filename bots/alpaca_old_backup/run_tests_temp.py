import subprocess

result = subprocess.run(['python', '-m', 'unittest', 'tests/test_daytrader_logic.py', '-v'], capture_output=True, text=True)
print(result.stdout)
print(result.stderr)
