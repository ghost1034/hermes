import math

def calc_short(bid_price, spread):
    min_clearance = max(spread * 3.0, 0.04)
    limit_price = math.floor(bid_price * 0.9995 * 100) / 100
    tp_price = round(bid_price - min_clearance, 2)
    sl_price = round(bid_price + min_clearance, 2)
    return limit_price, tp_price, sl_price

print(calc_short(100.00, 0.01))
print(calc_short(200.00, 0.01))
