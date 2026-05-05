import pytest
import subprocess

def run_tests():
    result = subprocess.run(['pytest', 'tests/test_daytrader_logic.py', '--cov=daytrader', '--cov-report=term-missing'], capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)

if __name__ == "__main__":
    run_tests()