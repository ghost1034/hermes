
import sxtwl
day = sxtwl.fromSolar(1983, 2, 3)

gz = day.getHourGZ(7) # 7:20 is Chen shi (辰)
yTG = day.getYearGZ()
mTG = day.getMonthGZ()
dTG = day.getDayGZ()
hTG = day.getHourGZ(7)

Gan = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
Zhi = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

print(f"Year: {Gan[yTG.tg]}{Zhi[yTG.dz]}")
print(f"Month: {Gan[mTG.tg]}{Zhi[mTG.dz]}")
print(f"Day: {Gan[dTG.tg]}{Zhi[dTG.dz]}")
print(f"Hour: {Gan[hTG.tg]}{Zhi[hTG.dz]}")
