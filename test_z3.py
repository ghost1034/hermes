
def get_ziwei_branch(day, bureau):
    # bureau: 2,3,4,5,6
    y = day % bureau
    if y == 0:
        x = 0
    else:
        x = bureau - y
    q = (day + x) // bureau
    # Yin is 2. 
    # Starts at Yin (2).
    # If x is odd, move forward x steps.
    # If x is even, move backward x steps.
    base = 2 + q - 1 # q=1 means Yin (2)
    if x % 2 == 1:
        res = base + x
    else:
        res = base - x
    return res % 12

print("Ziwei pos:", get_ziwei_branch(21, 5))
