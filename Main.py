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
from datetime import date, datetime
from pathlib import Path
import os
import time
import astral
import astral.sun
import syslog

# the SPI pins
HM_CSN = 0
HM_CE = 24

HM_SERIAL_NUMBER = "114184020874"

# the geo coordinates to calculate the time for dawn and dusk
LATITUDE = 50.92
LONGITUDE = 13.33

LOCATION = astral.LocationInfo("Freiberg", "Germany", "Europe/Berlin", LATITUDE, LONGITUDE)

# database
DATABASE_FILEPATH = "/home/torsten/Database/electricity_monitor_readings.db"
DATABASE_NUMBER_OF_INVERTER_CHANNELS = 2

# general
DATA_ACQUISITION_PERIOD_S = 30
APP_LOG_NAME = "Electricity and inverter monitor"

#--------------------------------------------------------------------------------------------------

def MainLoop() -> None:
    """ The application main loop.
    """

    # create database directory if it does not exists
    databaseDirectory = os.path.dirname(DATABASE_FILEPATH)
    Path(databaseDirectory).mkdir(parents=True, exist_ok=True)

    db = Database(DATABASE_FILEPATH, DATABASE_NUMBER_OF_INVERTER_CHANNELS)
    em = EbzDD3("/dev/ttyAMA0")
    hm = HoymilesHmDtu(HM_SERIAL_NUMBER, HM_CSN, HM_CE)

    hm.InitializeCommunication()
    
    while True:
        st = time.time()

        CollectData(db, em, hm)
        db.Commit()

        et = time.time()

        delayTime = DATA_ACQUISITION_PERIOD_S - (et - st)
        if delayTime < 5:
            delayTime = 5

        time.sleep(delayTime)

def CollectData(database : Database, electricityMeter : EbzDD3, inverter : HoymilesHmDtu) -> None:
    """ Collects the data from the electricity meter and inverter and stores it in the database.

    Args:
        database (Database): The database to store the collected data.
        electricityMeter (EbzDD3): The electricity meter.
        inverter (HoymilesHmDtu): The inverter.
    """
    success, infoEm0 = electricityMeter.ReceiveInfo(0)
    if success:
        # EbzDD3.PrintInfo(infoEm0)
        database.InsertReadingsElectricityMeter(0, infoEm0)

    success, infoEm1 = electricityMeter.ReceiveInfo(1)
    if success:
        # EbzDD3.PrintInfo(infoEm1)
        database.InsertReadingsElectricityMeter(1, infoEm1)

    # collect the inverter data only when the sun shines
    dawn, dusk = __GetDawnAndDuskTime()
    now = datetime.now(dawn.tzinfo)
    if dawn < now < dusk:
        success, infoHm = inverter.QueryInverterInfo()
        if success:
            # HoymilesHmDtu.PrintInverterInfo(infoHm)
            database.InsertReadingsInverter(infoHm)

__currentDate : date | None = None
__dawn : datetime
__dusk : datetime

def __GetDawnAndDuskTime() -> tuple[datetime, datetime]:
    """ Determines the dawn and dusk time for today.
    """
    global __currentDate, __dawn, __dusk

    currentDate = date.today()
    if (__currentDate is not None) and (currentDate == __currentDate):
        return __dawn, __dusk
    
    __currentDate = currentDate

    theSun = astral.sun.sun(LOCATION.observer, __currentDate)
    __dawn = theSun["dawn"]
    __dusk = theSun["dusk"]

    return __dawn, __dusk

# main entry point
if __name__ == "__main__":

    syslog.syslog(syslog.LOG_INFO, f"{APP_LOG_NAME} started")

    try:
        MainLoop()
    except Exception as err:
        syslog.syslog(syslog.LOG_ERR, f"{APP_LOG_NAME} error: {err}")
    finally:
        syslog.syslog(syslog.LOG_INFO, f"{APP_LOG_NAME} stopped")
    
