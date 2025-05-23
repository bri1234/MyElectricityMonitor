"""
Communication functions for eBZ DD3 electricity meter.

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

import SmlDecoder as sml
import gpiozero # type: ignore
import serial
import time
import gc
from typing import Any

# Units for the meter readings
# "+A"      = meter reading +A, tariff-free in kWh
# "+A T1"   = meter reading +A, tariff 1 in kWh
# "+A T2"   = meter reading +A, tariff 2 in kWh
# "-A"      = meter reading -A, tariff-free in kWh
# "P"       = Sum of instantaneous power in all phases in W
# "P L1"    = Instantaneous power phase L1 in W
# "P L2"    = Instantaneous power phase L2 in W
# "P L3"    = Instantaneous power phase L3 in W
# +A: Active energy, grid supplies to customer.
# -A: Active energy, customer supplies to grid

Units = {
    "+A": "kWh",
    "+A T1": "kWh",
    "+A T2": "kWh",
    "-A": "kWh",
    "P": "W",
    "P L1": "W",
    "P L2": "W",
    "P L3": "W"
}

class EbzDD3:
    """ Class to query information from eBZ DD3 electricity meters.
    """

    __serialPort : str
    __GPIO_SWITCH = 17

    __channelSwitch : gpiozero.DigitalOutputDevice
    __serial : serial.Serial

    def __init__(self, serialPort : str = "/dev/ttyAMA0") -> None:
        """ Creates a new instance of the electricity meter reader.
        """
        self.__serialPort = serialPort
        self.__channelSwitch = gpiozero.DigitalOutputDevice(EbzDD3.__GPIO_SWITCH)
        self.__selectChannel(0)

        self.__serial = serial.Serial(self.__serialPort, 9600, timeout=0.1)

    def __selectChannel(self, channelNum : int) -> None:
        """ Selects the channel (= the electricity meter) to read from.

        Args:
            channelNum (int): The channel 0 or 1.
        """
        if channelNum == 0:
            self.__channelSwitch.off()
        else:
            self.__channelSwitch.on()

        time.sleep(0.1)

    @staticmethod
    def __ReadBlock(ser : serial.Serial, timeoutBetweenBytes : float, timeoutFirstByte : float) -> bytearray:
        """ Receives a raw data block from serial port.

        Args:
            ser (serial.Serial): The serial port communicator.
            timeoutBetweenBytes (float): Timeout between receiving two bytes in seconds.
            timeoutFirstByte (float): Timeout for the first received byte in seconds.

        Returns:
            bytearray: The received data.
        """

        data = bytearray()
        tm = time.time()

        # extra timeout for the first byte?
        if timeoutFirstByte > 0.0:
            while True:
                rcv = ser.read()
                if len(rcv) > 0:
                    data.extend(rcv)
                    break

                if time.time() - tm > timeoutFirstByte:
                    return data

        # receive bytes and consider the timeout between the bytes
        tm = time.time()
        
        while time.time() - tm < timeoutBetweenBytes:
            rcv = ser.read()
            if len(rcv) > 0:
                data.extend(rcv)
                tm = time.time()

        return data

    def __ReceiveInfoData(self, channelNum : int) -> bytearray:
        """ Receives the data of one full info message.

        Args:
            channelNum (int): The channel (electricity meter).

        Returns:
            bytearray: The received data of one info message.
        """

        self.__selectChannel(channelNum)
        
        # discard old data
        self.__serial.reset_input_buffer()

        try:
            gc.disable()

            # wait until time gap before start of the info message
            EbzDD3.__ReadBlock(self.__serial, 0.3, 0.0)
            
            # now receive the info message
            data = EbzDD3.__ReadBlock(self.__serial, 0.3, 1.0)

            return data

        except:
            gc.enable()
            
        return bytearray()
    
    @staticmethod
    def __ExtractInfoFromDataSet(dataSet : Any) -> tuple[str | None, float | None]:
        """ Extracts meter reading from one dataset.

        Args:
            dataSet (Any): the data for one reading

        Returns:
            str | None: name of the reading
            float | None]: reading value
        """

        id = dataSet[0]
        value = dataSet[5]

        # +A: Active energy, grid supplies to customer.
        # -A: Active energy, customer supplies to grid

        if id == b'\x01\x00\x01\x08\x00\xFF':
            return "+A", value / 1E8            # meter reading +A, tariff-free in kWh
        
        if id == b'\x01\x00\x01\x08\x01\xFF':
            return "+A T1", value / 1E8         # meter reading +A, tariff 1 in kWh
        
        if id == b'\x01\x00\x01\x08\x02\xFF':
            return "+A T2", value / 1E8         # meter reading +A, tariff 2 in kWh
        
        if id == b'\x01\x00\x02\x08\x00\xFF':
            return "-A", value / 1E8            # meter reading -A, tariff-free in kWh
        
        if id == b'\x01\x00\x10\x07\x00\xFF':
            return "P", value / 1E2             # Sum of instantaneous power in all phases in W
        
        if id == b'\x01\x00\x24\x07\x00\xFF':
            return "P L1", value / 1E2          # Instantaneous power phase L1 in W
        
        if id == b'\x01\x00\x38\x07\x00\xFF':
            return "P L2", value / 1E2          # Instantaneous power phase L2 in W
        
        if id == b'\x01\x00\x4C\x07\x00\xFF':
            return "P L3", value / 1E2          # Instantaneous power phase L3 in W
        
        return None, None

    
    @staticmethod
    def __ExtractInfoFromData(data : bytearray) -> dict[str, float]:
        """ Extracts meter readings from the received raw data.

        Args:
            data (bytearray): The received raw data.

        Returns:
            dict[str, float]: The meter readinds.
        """

        messageList = sml.DecodeSmlMessages(data)

        # get the useful data sets
        dataSetList = messageList[1][3][1][4]
        info : dict[str, float] = {}

        for dataSet in dataSetList:
            name, value = EbzDD3.__ExtractInfoFromDataSet(dataSet)

            if name is not None and value is not None:
                info[name] = value

        return info

    def ReceiveInfo(self, channelNum : int) -> tuple[bool, dict[str, float]]:
        """ Receives the information from a electricity meter. (The meter readings.)

            Example:

            {
                "+A": 849.45,
                "+A T1": 848.46,
                "+A T2" : 0.995,
                "-A" : 2.197,
                "P" : 3200.17,
                "P L1" : 1014.71,
                "P L2" :  = 1026.48,
                "P L3" : 1158.98
            }

            +A: Active energy, grid supplies to customer.
            -A: Active energy, customer supplies to grid

            "+A"      = meter reading +A, tariff-free in kWh
            "+A T1"   = meter reading +A, tariff 1 in kWh
            "+A T2"   = meter reading +A, tariff 2 in kWh
            "-A"      = meter reading -A, tariff-free in kWh
            "P"       = Sum of instantaneous power in all phases in W
            "P L1"    = Instantaneous power phase L1 in W
            "P L2"    = Instantaneous power phase L2 in W
            "P L3"    = Instantaneous power phase L3 in W

        Args:
            channelNum (int): The channel = the electricity meter 0 or 1.

        Returns:
            dict[str, float]: The electricity meter information.
        """

        try:
            data = self.__ReceiveInfoData(channelNum)
            if len(data) == 0:
                return False, {}
            
            info = EbzDD3.__ExtractInfoFromData(data)
            return True, info
    
        except:
            return False, {}
    
    @staticmethod
    def PrintInfo(info : dict[str, float]) -> None:
        """ Prints information got with function ReceiveInfo() in human readable form.

        Args:
            info (dict[str, float]): The information got with function ReceiveInfo().
        """

        for key in info.keys():
            print(f"{key} = {info[key]} {Units[key]}")

    