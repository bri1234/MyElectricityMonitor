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

import json
import os.path as path
import astral

class Configuration:

    __config : dict[str, dict[str, str | int]]

    InverterSerialNumber : str
    InverterNumberOfChannels : int
    
    DatabaseFilepath : str

    DataAcquisitionPeriod : float

    Location : astral.LocationInfo

    def Load(self, filePath : str) -> None:

        if not path.isfile(filePath):
            raise Exception(f"Missing configuration file: {filePath}")
        
        with open(filePath) as file:
            config = json.load(file)

        self.InverterSerialNumber = config["Inverter"]["SerialNumber"]
        self.InverterNumberOfChannels = config["Inverter"]["NumberOfChannels"]

        self.DatabaseFilepath = config["Database"]["Filepath"]
        self.DataAcquisitionPeriod = config["Database"]["DataAcquisitionPeriod"]

        configLocation = config["Location"]
        self.Location = astral.LocationInfo(configLocation["City"], configLocation["Region"], configLocation["Timezone"],
                                            configLocation["Latitude"], configLocation["Longitude"])

