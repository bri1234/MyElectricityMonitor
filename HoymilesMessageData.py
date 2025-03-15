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

import MyCrc as crc

REQUEST_RF_VERSION = 0x06
ANSWER_RF_VERSION = REQUEST_RF_VERSION | 0x80

REQUEST_INFO = 0x15
ANSWER_INFO = REQUEST_INFO | 0x80

__MAX_PACKET_SIZE = 32

def CreateRequestInfoPacket(receiverAddr : bytes, senderAddr : bytes, currentTime : float) -> bytearray:
    """ Creates the packet that can be sent to the inverter to request information.

    Args:
        receiverAddr (bytes): The address of the receiver generated from the receiver (inverter) serial number. (4 bytes)
        senderAddr (bytes): The address of the sender generated from the sender (DTU) serial number. (4 bytes)
        currentTime (float): The current time in seconds since the start of the epoch.

    Returns:
        bytearray: The packet to be sent to the inverter.
    """
    # the header
    packet = __CreatePacketHeader(REQUEST_INFO, receiverAddr, senderAddr, 0x80)

    # the payload
    payload = __CreateRequestInfoPayload(currentTime)
    packet.extend(payload)

    # the payload checksum
    payloadChecksum = crc.CalculateHoymilesCrc16(payload, len(payload))
    packet.extend(payloadChecksum.to_bytes(2, "big", signed=False))

    # the packet checksum
    packetChecksum = crc.CalculateHoymilesCrc8(packet, len(packet))
    packet.extend(packetChecksum.to_bytes(1, "big", signed=False))

    if len(packet) != 27:
        raise Exception(f"Internal error __CreatePacket: packet size {len(packet)} != 27")
    
    # replace special characters
    packet = EscapeData(packet)

    if len(packet) > __MAX_PACKET_SIZE:
        raise Exception(f"Internal error __CreatePacket: packet size {len(packet)} > MAX_PACKET_SIZE {__MAX_PACKET_SIZE}")
    
    return packet

def CreateRfVersionPacket(receiverAddr : bytes, senderAddr : bytes) -> bytearray:
    """ Creates the packet that can be sent to the inverter to request the RF version.

    Args:
        receiverAddr (bytes): The address of the receiver generated from the receiver (inverter) serial number. (4 bytes)
        senderAddr (bytes): The address of the sender generated from the sender (DTU) serial number. (4 bytes)

    Returns:
        bytearray: The packet to be sent to the inverter.
    """
    # the header
    packet = __CreatePacketHeader(REQUEST_RF_VERSION, receiverAddr, senderAddr, 0)

    # no payload

    # the packet checksum
    packetChecksum = crc.CalculateHoymilesCrc8(packet, len(packet))
    packet.extend(packetChecksum.to_bytes(1, "big", signed=False))

    if len(packet) != 11:
        raise Exception(f"Internal error __CreatePacket: packet size {len(packet)} != 11")
    
    # replace special characters
    packet = EscapeData(packet)

    if len(packet) > __MAX_PACKET_SIZE:
        raise Exception(f"Internal error __CreatePacket: packet size {len(packet)} > MAX_PACKET_SIZE {__MAX_PACKET_SIZE}")
    
    return packet

def __CreatePacketHeader(command : int, receiverAddr : bytes, senderAddr : bytes, frame : int) -> bytearray:
    """ Creates the packet header.

    Args:
        command (InverterCmd): The packet command.
        receiverAddr (bytes): The address of the receiver generated from the receiver (inverter) serial number. (4 bytes)
        senderAddr (bytes): The address of the sender generated from the sender (DTU) serial number. (4 bytes)
        frame (int): The frame number for message data.

    Returns:
        bytearray: The packet header.
    """
    if len(receiverAddr) != 4:
        raise Exception(f"Invalid length of receiver address: {len(receiverAddr)}. (must be 4 bytes)")
    
    if len(senderAddr) != 4:
        raise Exception(f"Invalid length of sender address: {len(senderAddr)}. (must be 4 bytes)")
    
    header = bytearray(10)

    header[0] = command
    header[1:5] = receiverAddr
    header[5:9] = senderAddr
    header[9] = frame
    
    if len(header) != 10:
        raise Exception(f"Internal error CreatePacketHeader: size {len(header)} != 10")
    
    return header

def __CreateRequestInfoPayload(currentTime : float) -> bytearray:
    """ Creates payload data filled with the time.

    Args:
        currentTime (float): The current time in seconds since the start of the epoch.

    Returns:
        bytearray: The payload data.
    """
    payload = bytearray(14)

    payload[0] = 0x0B   # sub command
    payload[1] = 0x00   # revision
    payload[2:6] = int(currentTime).to_bytes(4, "big", signed = False)
    payload[9] = 0x05

    if len(payload) != 14:
        raise Exception(f"Internal error __CreatePayloadFromTime: size {len(payload)} != 14")
    
    return payload

def EscapeData(input : bytes | bytearray) -> bytearray:
    """ Replaces bytes with special meaning by escape sequences.
        0x7D -> 0x7D 0x5D
        0x7E -> 0x7D 0x5E
        0x7F -> 0x7D 0x5F

    Args:
        input (bytes | bytearray): The input data.

    Returns:
        bytearray: The escaped output data.
    """
    output = bytearray()

    for b in input:
        match b:
            case 0x7D:
                output.append(0x7D)
                output.append(0x5D)
            case 0x7E:
                output.append(0x7D)
                output.append(0x5E)
            case 0x7F:
                output.append(0x7D)
                output.append(0x5F)
            case _:
                output.append(b)

    return output

def UnescapeData(input : bytes | bytearray) -> bytearray:
    """ Undo replace of bytes with special meaning by escape sequences.

    Args:
        input (bytes | bytearray): The input data.

    Returns:
        bytearray: The output data without escaped bytes.
    """
    output = bytearray()

    idx = 0
    while idx < len(input):
        b = input[idx]

        if b == 0x7D:
            idx += 1
            match input[idx]:
                case 0x5D:
                    output.append(0x7D)
                case 0x5E:
                    output.append(0x7E)
                case 0x5F:
                    output.append(0x7F)
                case _:
                    raise Exception("UnescapeData(): Invalid data, can not decode.")
        else:
            output.append(b)

        idx += 1

    return output

