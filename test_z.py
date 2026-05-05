
def get_stars(ziwei_pos):
    # order: ziwei, tianji, empty, taiyang, wuqu, tiantong, empty, empty, lianzhen
    stars = {}
    stars['Ziwei'] = ziwei_pos
    stars['Tianji'] = (ziwei_pos - 1) % 12
    stars['Taiyang'] = (ziwei_pos - 3) % 12
    stars['Wuqu'] = (ziwei_pos - 4) % 12
    stars['Tiantong'] = (ziwei_pos - 5) % 12
    stars['Lianzhen'] = (ziwei_pos - 8) % 12
    
    # Tianfu position = (16 - ziwei_pos) % 12  # Yin(2)+Shen(8) = 10 or 22? Wait.
    # Zi(0) + Chen(4) = 4. 
    # Formula: tianfu = (4 - ziwei) % 12
    tianfu = (4 - ziwei_pos) % 12
    stars['Tianfu'] = tianfu
    stars['Taiyin'] = (tianfu + 1) % 12
    stars['Tanlang'] = (tianfu + 2) % 12
    stars['Jumen'] = (tianfu + 3) % 12
    stars['Tianxiang'] = (tianfu + 4) % 12
    stars['Tianliang'] = (tianfu + 5) % 12
    stars['Qishao'] = (tianfu + 6) % 12
    stars['Pojun'] = (tianfu + 10) % 12
    return stars

print(get_stars(0)) # Ziwei in Zi
