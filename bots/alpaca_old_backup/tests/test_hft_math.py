import math

def test_math():
    ask_price = 20.00
    bid_price = 19.98
    spread = ask_price - bid_price
    min_clearance = max(spread * 3.0, 0.04)
    
    # LONG
    limit_price_long = math.ceil(ask_price * 1.0005 * 100) / 100
    tp_price_long = round(ask_price + min_clearance, 2)
    sl_price_long = round(ask_price - min_clearance, 2)
    
    assert limit_price_long == 20.01
    assert tp_price_long == 20.06
    assert sl_price_long == 19.94
    print("Math tests passed!")

if __name__ == "__main__":
    test_math()