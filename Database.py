"""
Database to store the readings.

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

import sqlite3
import time

class Database:
    """ Class to store the readings in a SQLite database.
    """

    __connection : sqlite3.Connection

    __COLUMNS_ELECTRICITY_METER = ["+A", "+A T1", "+A T2", "-A", "P", "P L1", "P L2", "P L3"]

    __READINGS_INVERTER_CHANNEL = ["DC V", "DC I", "DC P", "DC E day", "DC E total"]
    __READINGS_INVERTER = ["AC V", "AC I", "AC F", "AC P", "AC Q", "AC PF", "T"]
    __columnsInverter : list[str]

    def __init__(self, fileName : str) -> None:
        """ Creates a new instance of the database object.

        Args:
            fileName (str): The filename of the SQLite database. If the database does not exists a new one will be created.
        """
        self.__columnsInverter = [ f"CH0 {reading}" for reading in Database.__READINGS_INVERTER_CHANNEL ]
        self.__columnsInverter.extend([ f"CH1 {reading}" for reading in Database.__READINGS_INVERTER_CHANNEL ])
        self.__columnsInverter.extend(Database.__READINGS_INVERTER)

        self.__connection = sqlite3.connect(fileName)

        Database.__CreateTablesIfNotExists(self.__connection)

    def Cleanup(self) -> None:
        """ Closes the database.
        """

        if self.__connection:
            self.__connection.close()

    @staticmethod
    def __CreateTablesIfNotExists(connection : sqlite3.Connection) -> None:
        """ Creates all data tables in the database if the table does not already exists.

        Args:
            connection (sqlite3.Connection): The SQLite connection.
        """

        # create inverter data table
        columnsStr = ', '.join([f'"{column}" REAL' for column in Database.__columnsInverter])

        connection.execute('CREATE TABLE IF NOT EXISTS Inverter ("time" INT NOT NULL PRIMARY KEY,'
                           + columnsStr
                           + ') STRICT')
        
        # create electricity meter 1 data table
        columnsStr = ', '.join([f'"{column}" REAL' for column in Database.__COLUMNS_ELECTRICITY_METER])

        connection.execute('CREATE TABLE IF NOT EXISTS ElectricityMeter1 ("time" INT NOT NULL PRIMARY KEY,'
                           + columnsStr
                           + ') STRICT')
        
        # create electricity meter 2 data table
        connection.execute('CREATE TABLE IF NOT EXISTS ElectricityMeter2 ("time" INT NOT NULL PRIMARY KEY,'
                           + columnsStr
                           + ') STRICT')

    def InsertDataElectricityMeter(self, electricityMeterNum : int, readings : dict[str, float]) -> None:
        """ Stores the electricity meter readings into the database.

        Args:
            electricityMeterNum (int): The electricity meter 1 or 2.
            readings (dict[str, float]): The electricity meter readings.
        """

        if electricityMeterNum < 1 or electricityMeterNum > 2:
            raise Exception(f"Invalid electricity meter number {electricityMeterNum}")
        
        columnsStr = ','.join(Database.__COLUMNS_ELECTRICITY_METER)
        valuesStr = ','.join([ str(readings[key]) for key in Database.__COLUMNS_ELECTRICITY_METER ])

        tm = int(time.time())

        sql = f'INSERT INTO ElectricityMeter{electricityMeterNum} ("time",{columnsStr}) VALUES ({tm},{valuesStr})'
        self.__connection.execute(sql)

    def InsertDataInverter(self, readings : dict[str, float | list[dict[str, float]]]) -> None:
        """ Stores the solar inverter readings into the database.

        Args:
            readings (dict[str, float]): The solar inverter readings.
        """

        columnsStr = ','.join(Database.__columnsInverter)

        readingsCh = readings["Channels"]
        if not isinstance(readingsCh, list):
            raise Exception('Data format error: readings are not valid inverter data! missing "Channels"')
        
        values = [ str(readingsCh[0][key]) for key in Database.__READINGS_INVERTER_CHANNEL ]
        values.extend([ str(readingsCh[1][key]) for key in Database.__READINGS_INVERTER_CHANNEL ])
        values.extend([ str(readings[key]) for key in Database.__READINGS_INVERTER ])
        valuesStr = ','.join(values)

        tm = int(time.time())

        sql = f'INSERT INTO Inverter ("time",{columnsStr}) VALUES ({tm},{valuesStr})'
        self.__connection.execute(sql)


