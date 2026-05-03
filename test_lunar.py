
from lunar_python import Lunar, Solar

solar = Solar.fromYmdHms(1983, 2, 3, 7, 20, 0)
lunar = solar.getLunar()
print('Lunar Year:', lunar.getYearInGanZhi(), lunar.getYearShengXiao())
print('Lunar Month:', lunar.getMonthInGanZhi(), lunar.getMonth())
print('Lunar Day:', lunar.getDayInGanZhi(), lunar.getDay())
print('Lunar Hour:', lunar.getTimeInGanZhi())
print('BaZi:', lunar.getEightChar().getYear(), lunar.getEightChar().getMonth(), lunar.getEightChar().getDay(), lunar.getEightChar().getTime())
