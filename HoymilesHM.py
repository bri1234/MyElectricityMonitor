"""
Communication functions for Hoymiles HM-300, HM-600, HM-800, ... inverters.

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

import pyrf24 as nrf

# leading number in packets in answer from inverter
packets_to_receive_dict = {1 : [0x01, 0x82], 2 : [0x01, 0x02, 0x83], 3 : [0x01, 0x02, 0x03, 0x04, 0x85]}


class HoymilesHm:
    """ Class for communication with HM300, HM350, HM400, HM600, HM700, HM800, HM1200 & HM1500 inverter.
    """

    __inverterSerialNumber : str
    __inverterType : int
    __pinCsn : int
    __pinCe : int
    __spiFrequency : int
    
    __radio : nrf.RF24 | None


    def __init__(self, inverterSerialNumber : str,  pinCsn : int = 0, pinCe : int = 24, spiFrequency : int = 1000000) -> None:
        """ Creates a new communication object.

        Args:
            inverterSerialNumber (str): The inverter serial number. (As printed on a sticker on the inverter case.)
            pinCsn (int, optional): The CSN pin as SPI device number (0 or 1). Defaults to 0.
            pinCe (int, optional): The GPIO pin connected to NRF24L01 signal CE. Defaults to 24.
            spiFrequency (int, optional): The SPI frequency in Hz. Defaults to 1000000.
        """
        self.__inverterSerialNumber = inverterSerialNumber
        self.__pinCsn = pinCsn
        self.__pinCe = pinCe
        self.__spiFrequency = spiFrequency

        self.__inverterType = __GetInverterTypeFromSerialNumber(inverterSerialNumber)
        
    def InitializeCommunication(self) -> None:
        """ Initializes the communication.
        """
        self.__radio = nrf.RF24(self.__pinCe, self.__pinCsn, self.__spiFrequency)

        if not self.__radio.begin():
            raise Exception("Can not initialize RF24!")

        self.__radio.set_radiation(nrf.rf24_pa_dbm_e.RF24_PA_HIGH, nrf.rf24_datarate_e.RF24_250KBPS)
        


    
    def PrintInfo(self) -> None:
        """ Prints NRF24L01 module info on standard output.
        """
        if self.__radio is None:
            raise Exception("Not initialized!")
        
        self.__radio.print_pretty_details()

# Inverter types:
# 1: HM300, HM350, HM400
# 2: HM600, HM700, HM800
# 3: HM1200, HM1500
__HM_INVERTER_TYPES_SERIAL_NUMBERS : dict[str, int] = { "1121" : 1, "1141" : 2, "1161" : 3 }

def __GetInverterTypeFromSerialNumber(inverterSerialNumber : str) -> int:
    """ Determines the inverter type from serial number.

    Args:
        inverterSerialNumber (str): The inverter serial number as printed on the sticker on the inverter case.

    Returns:
        int: The inverter type: 1 = HM300, HM350, HM400; 2 = HM600, HM700, HM800; 3 = HM1200, HM1500
    """
    serialStartStr = inverterSerialNumber[:4]
    if serialStartStr not in __HM_INVERTER_TYPES_SERIAL_NUMBERS:
        supportedSerialNumbers = ", ".join(__HM_INVERTER_TYPES_SERIAL_NUMBERS.keys())
        raise Exception(f"Inverter type is not supported. (Serial number must start with: {supportedSerialNumbers})")
    
    return __HM_INVERTER_TYPES_SERIAL_NUMBERS[serialStartStr]
    


if __name__ == "__main__":

    hm = HoymilesHm("114184020874", 0, 24, 1000000)
    hm.InitializeCommunication()
    hm.PrintInfo()

        