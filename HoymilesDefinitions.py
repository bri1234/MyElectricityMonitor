"""
Communication functions for Hoymiles HM300, HM350, HM400, HM600, HM700,
HM800, HM1200 & HM1500 inverters.

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

from enum import Enum, IntEnum

class InverterType(Enum):
    """ Inverter types = number of channels = number of solar panels per inverter.
    """
    InverterOneChannel = 1
    InverterTwoChannels = 2
    InverterFourChannels = 4

class Request(IntEnum):
    """ Inverter remote command definitions.
    """

    VERSION = 0x0F
    INFO = 0x15
    DEVIVE_CONTROL = 0x51

    @staticmethod
    def ToString(request : int) -> str:
        match request:
            case Request.VERSION:
                return "VERSION"
            case Request.INFO:
                return "INFO"
            case Request.DEVIVE_CONTROL:
                return "DEVIVE_CONTROL"
            case _:
                return "???"

class Response(IntEnum):
    """ Inverter remote answer definitions.
    """

    VERSION = Request.VERSION | 0x80
    INFO = Request.INFO | 0x80
    DEVIVE_CONTROL = Request.DEVIVE_CONTROL | 0x80

    @staticmethod
    def ToString(response : int) -> str:
        match response:
            case Response.VERSION:
                return "VERSION"
            case Response.INFO:
                return "INFO"
            case Response.DEVIVE_CONTROL:
                return "DEVIVE_CONTROL"
            case _:
                return "???"

# indicates that the last frame is sent
IS_LAST_FRAME = 0x80

""" Inverter RF channel definitions.
    RF channel frequency: F0= 2400 + RF_CH [MHz]
"""
RF_CHANNELS : list[int] = [ 3, 23, 40, 61, 75 ]

