
import sxtwl
day = sxtwl.fromSolar(1983, 2, 3)
print("Solar:", day.getSolarYear(), day.getSolarMonth(), day.getSolarDay())
print("Lunar:", day.getLunarYear(), day.getLunarMonth(), day.getLunarDay())
# Is it before LiChun?
print("Has LiChun passed in this lunar year:", day.hasJieQi()) # just exploring api

# Let's write a quick script to find the jieqi for 1983
for i in range(1, 13):
    jq = day.getJieQi()
    # sxtwl has a different way, let's just get the Bazi properly.
