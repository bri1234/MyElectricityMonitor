
from HoymilesHmDtu import HoymilesHmDtu

CSn = 0
CE = 24

hm = HoymilesHmDtu("114184020874", CSn, CE)

hm.InitializeCommunication()
success, info = hm.QueryInverterInfo()

print(f"success: {success}")
HoymilesHmDtu.PrintInverterInfo(info)

