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

class EbzDD3:
    """ Class to query information from eBZ DD3 electricity meters.
    """

    __SERIAL_PORT = "/dev/serial0"
    __GPIO_SWITCH = 17

    __channelSwitch : gpiozero.DigitalOutputDevice
    __serial : serial.Serial

    def __init__(self) -> None:
        """ Creates a new instance of the electricity meter reader.
        """
        self.__channelSwitch = gpiozero.DigitalOutputDevice(EbzDD3.__GPIO_SWITCH)
        self.__selectChannel(0)

        self.__serial = serial.Serial(self.__SERIAL_PORT, 9600, timeout=0.2)

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

    def Read(self, channelNum : int) -> None:

        self.__selectChannel(channelNum)
        
        s = self.__serial

        # discard old data
        s.reset_input_buffer()

        try:
            gc.disable()
            # read until start of info

            # die Lücke suchen

            self.__serial.read(EbzDD3.__MAX_INFO_SIZE)

            data = self.__serial.read(EbzDD3.__MAX_INFO_SIZE)

            print(f"len={len(data)}")

        except:
            gc.enable()
            
