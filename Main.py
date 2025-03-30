"""
Electricity monitor main loop.

Copyright (C) 2025  Torsten Brischalle
email: torsten@brischalle.de
web: http://www.aaabbb.de

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to
deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
IN THE SOFTWARE.
"""

from EbzDD3 import EbzDD3
from HoymilesHmDtu import HoymilesHmDtu
from Database import Database
import time

HM_CSn = 0
HM_CE = 24

def MainLoop() -> None:

    em = EbzDD3()
    hm = HoymilesHmDtu("114184020874", HM_CSn, HM_CE)
    db = Database("readings.db")

    for _ in range(60):
        success, infoEm = em.ReceiveInfo(0)
        if success:
            db.InsertReadingsElectricityMeter(0, infoEm)

        success, infoEm = em.ReceiveInfo(1)
        if success:
            db.InsertReadingsElectricityMeter(1, infoEm)

        success, infoHm = hm.QueryInverterInfo()
        if success:
            db.InsertReadingsInverter(infoHm)

        time.sleep(30)

if __name__ == "__main__":
    MainLoop()
    
