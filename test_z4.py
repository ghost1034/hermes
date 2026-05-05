
def get_stars(ziwei_pos):
    stars = {}
    stars['Ziwei'] = ziwei_pos
    stars['Tianji'] = (ziwei_pos - 1) % 12
    stars['Taiyang'] = (ziwei_pos - 3) % 12
    stars['Wuqu'] = (ziwei_pos - 4) % 12
    stars['Tiantong'] = (ziwei_pos - 5) % 12
    stars['Lianzhen'] = (ziwei_pos - 8) % 12
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

ziwei = 2 # Yin
stars = get_stars(ziwei)
branches = ["Zi", "Chou", "Yin", "Mao", "Chen", "Si", "Wu", "Wei", "Shen", "You", "Xu", "Hai"]
for k, v in stars.items():
    print(f"{k}: {branches[v]}")
