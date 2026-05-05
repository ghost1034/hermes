import sys
import py_compile

def test_syntax():
    try:
        py_compile.compile('/home/ianstewart/bots/alpaca/daytrader.py', doraise=True)
    except Exception as e:
        print(f"Syntax error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_syntax()
