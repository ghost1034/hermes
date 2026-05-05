import math

def calc_long(ask_price, spread):
    min_clearance = max(spread * 3.0, 0.04)
    limit_price = math.ceil(ask_price * 1.0005 * 100) / 100
    tp_price = round(ask_price + min_clearance, 2)
    sl_price = round(ask_price - min_clearance, 2)
    return limit_price, tp_price, sl_price

print(calc_long(100.00, 0.01))
print(calc_long(200.00, 0.01))
