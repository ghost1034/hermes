
def calc_ziwei(day, wu_xing_ju):
    # wu_xing_ju: Shui2, Mu3, Jin4, Tu5, Huo6
    remainder = day % wu_xing_ju
    add_num = 0
    if remainder != 0:
        add_num = wu_xing_ju - remainder
    
    quotient = (day + add_num) // wu_xing_ju
    
    if add_num % 2 == 1:
        # odd, forward
        pos = quotient + add_num
    else:
        # even, backward
        pos = quotient - add_num
    
    # 1 based index where Yin=1? Or Yin=3?
    # Usually quotient starts from Yin (index 2). 
    # Let's check pos value.
    return pos

print(calc_ziwei(21, 5)) 
