
def get_ming_shen(month, hour):
    # Yin is 2.
    # Month step: clockwise. Month 1 = +0. Month 12 = +11.
    m_pos = (2 + month - 1) % 12
    # Hour step: counter-clockwise. Zi = -0. Chen (4) = -4.
    ming = (m_pos - hour) % 12
    return ming

print("Ming Gong:", get_ming_shen(12, 4))
