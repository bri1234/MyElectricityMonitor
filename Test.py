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

import Hoymiles as hoy
import textwrap
import MyCrc as crc

_frames : dict[int, bytes] = {}

def DecodeResponse(packet : bytes | bytearray) -> None:

    print("------------------------------------------------------------------------------------")
    response = packet[0]
    print(f"response: ${response:02X}")

    print(f"checksum: {hoy.HoymilesHmDtu.CheckChecksum(packet)}")

    str = " ".join(textwrap.wrap(packet[1:5].hex(), 2))
    print(f"address 1: {str}")         # should be receiver address

    str = " ".join(textwrap.wrap(packet[5:9].hex(), 2))
    print(f"address 2: {str}")         # should be inverter address

    # last frame number is ored with 0x80
    print(f"frame number: ${packet[9]:02X}")

    # header is 10 bytes and last byte is the checksum
    payload = packet[10:-1]
    frameNum = packet[9] & 0x0F
    isLastFrame = (packet[9] & 0x80) != 0

    _frames[frameNum] = payload
    if isLastFrame:
        DecodeFullPacket()
        _frames.clear()

def DecodeFullPacket() -> None:

    print("*** FULL FRAME ***")

    if len(_frames) != 3:
        print("error")
        return
    
    data = bytearray()
    for idx in range(1, 4):
        data.extend(_frames[idx])

    crc1 = int.from_bytes(data[-2:], "big")
    crc2 = crc.CalculateHoymilesCrc16(data, len(data) - 2)

    print(f"    crc1 = ${crc1:04X} ${crc2:04X} {crc1 == crc2}")

    if crc1 == crc2:
        info = DecodeDataInverterTyp2(data[:-2])
        if info is None:
            print("invalid data length")
            return
        
        for key in info.keys():
            print(f"{key} = {info[key]}")



def DecodeDataInverterTyp1(data : bytes | bytearray) -> dict[str, float] | None:
    info : dict[str, float] = {}

    if len(data) != 30:
        return None
    
    info["DcV"] = int.from_bytes(data[2:4], "big") / 10.0           # V
    info["DcI"] = int.from_bytes(data[4:6], "big") / 100.0          # A
    info["DcP"] = int.from_bytes(data[6:8], "big") / 10.0           # W
    info["DcTotalE"] = int.from_bytes(data[8:12], "big") / 1000.0   # Wh
    info["DcDayE"] = int.from_bytes(data[12:14], "big") / 1.0       # Wh
    info["AcV"] = int.from_bytes(data[14:16], "big") / 10.0         # V
    info["AcF"] = int.from_bytes(data[16:18], "big") / 100.0        # Hz
    info["AcP"] = int.from_bytes(data[18:20], "big") / 10.0         # W
    info["Q"] = int.from_bytes(data[20:22], "big") / 10.0           # -
    info["AcI"] = int.from_bytes(data[22:24], "big") / 100.0        # A
    info["AcPF"] = int.from_bytes(data[24:26], "big") / 1000.0      # -
    info["T"] = int.from_bytes(data[26:28], "big") / 10.0           # °C
    info["EVT"] = int.from_bytes(data[28:30], "big") / 1.0          # -

    return info

def DecodeDataInverterTyp2(data : bytes | bytearray) -> dict[str, float] | None:
    info : dict[str, float] = {}

    if len(data) != 42:
        return None

    info["DcV1"] = int.from_bytes(data[2:4], "big") / 10.0          # V
    info["DcI1"] = int.from_bytes(data[4:6], "big") / 100.0         # A
    info["DcP1"] = int.from_bytes(data[6:8], "big") / 10.0          # W
    info["DcV2"] = int.from_bytes(data[8:10], "big") / 10.0         # V
    info["DcI2"] = int.from_bytes(data[10:12], "big") / 100.0       # A
    info["DcP2"] = int.from_bytes(data[12:14], "big") / 10.0        # W
    info["DcTotalE1"] = int.from_bytes(data[14:18], "big") / 1000.0 # kWh
    info["DcTotalE2"] = int.from_bytes(data[18:22], "big") / 1000.0 # kWh
    info["DcDayE1"] = int.from_bytes(data[22:24], "big") / 1.0      # Wh
    info["DcDayE2"] = int.from_bytes(data[24:26], "big") / 1.0      # Wh
    info["AcV"] = int.from_bytes(data[26:28], "big") / 10.0         # V
    info["AcF"] = int.from_bytes(data[28:30], "big") / 100.0        # Hz
    info["AcP"] = int.from_bytes(data[30:32], "big") / 10.0         # W
    info["Q"] = int.from_bytes(data[32:34], "big") / 10.0           # -
    info["AcI"] = int.from_bytes(data[34:36], "big") / 100.0        # A
    info["AcPF"] = int.from_bytes(data[36:38], "big") / 1000.0      # -
    info["T"] = int.from_bytes(data[38:40], "big") / 10.0           # °C
    info["EVT"] = int.from_bytes(data[40:42], "big") / 1.0          # -

    return info

if __name__ == "__main__":

    _frames.clear()

    filename = "responses.txt"
    #filename = "responses2.txt"

    with open(filename, "r") as f:
        lines = f.readlines()

    for line in lines:
        if len(line.strip()) == 0:
            continue

        response = bytes.fromhex(line)
        DecodeResponse(response)
