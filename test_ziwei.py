
# Simple logic to find Ming Gong and stars based on lunar birth
# 1982 Lunar month 12, day 21, Chen hour (辰, 5th hour: 子, 丑, 寅, 卯, 辰 -> index 4)

def get_ming_shen_gong(month, hour_index):
    # Month 1 is Yin, Ming Gong starts from Yin (index 2)
    # Ming gong goes counter-clockwise by month, clockwise by hour
    # Month index: 1-12. Hour index: 0-11 (Zhi)
    # Formula: Yin(2) + month_index - 1 - hour_index
    # Wait, tradition is Ming Gong starts at Yin (2), count direct to month, retrograde to hour.
    # Ming Gong = 2 + (month - 1) - hour_index
    ming = (2 + month - 1 - hour_index) % 12
    return ming

# Let's test Ming Gong
print("Ming Gong:", get_ming_shen_gong(12, 4)) # Yin=2, Mao=3, Chen=4, Si=5, Wu=6, Wei=7, Shen=8, You=9, Xu=10, Hai=11, Zi=0, Chou=1

