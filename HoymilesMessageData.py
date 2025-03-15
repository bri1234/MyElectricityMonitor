

import HoymilesDefinitions as hd
import MyCrc as crc

MAX_PACKET_SIZE = 32
MAX_PAYLOAD_PER_PACKET = 16

def CreatePacketList(command : hd.Request, receiverAddr : bytes, senderAddr : bytes, data : bytes | bytearray | None) -> list[bytearray]:
    """ Creates a list of packets to be sent from the data to be sent.

    Args:
        command (InverterCmd): The packet command.
        receiverAddr (bytes): The address of the receiver generated from the receiver (inverter) serial number. (4 bytes)
        senderAddr (bytes): The address of the sender generated from the sender (DTU) serial number. (4 bytes)
        data (bytes | bytearray | None): The data to be sent.

    Returns:
        list[bytearray]: List of packets to be sent.
    """
    if (data is None) or (len(data) == 0):
        return [CreatePacket(command, receiverAddr, senderAddr, 1, True, None)]
    
    packetList : list[bytearray] = []
    payloadList = CreatePayloadListFromData(data)

    payloadCount = len(payloadList)
    packetNumber = 1

    for payload in payloadList:
        isLastPacket = (packetNumber == payloadCount)
        packet = CreatePacket(command, receiverAddr, senderAddr, packetNumber, isLastPacket, payload)

        packetList.append(packet)
        packetNumber += 1
    
    return packetList

def CreatePayloadListFromData(data : bytes | bytearray) -> list[bytes | bytearray]:
    """ Create payloads to be sent in packets from data.
        CRC16 checksum is added and data is split in small pieces.

    Args:
        data (bytes | bytearray): The data to be packet in multiple payloads.

    Returns:
        list[bytes | bytearray]: List of payloads.
    """
    # add payload CRC16 checksum
    crc16 = crc.CalculateHoymilesCrc16(data, len(data))
    data = data + crc16.to_bytes(2, "big", signed=False)

    # split payload into small pieces
    dataList = [data[idx:idx + MAX_PAYLOAD_PER_PACKET] for idx in range(0, len(data), MAX_PAYLOAD_PER_PACKET)]
    return dataList

def CreatePacket(command : hd.Request, receiverAddr : bytes, senderAddr : bytes, packetNumber : int, isLastPacket : bool,
                 packetPayload : bytes | bytearray | None) -> bytearray:
    """ Creates one packet.
        A paket is used for communication between the DTU (this device) and the inverter.

    Args:
        command (InverterCmd): The packet command.
        receiverAddr (bytes): The address of the receiver generated from the receiver (inverter) serial number. (4 bytes)
        senderAddr (bytes): The address of the sender generated from the sender (DTU) serial number. (4 bytes)
        packetNumber (int): The frame number (1, 2, ...) for message data that does not fit in one packet.
        isLastPacket (bool): True if it is the last frame for message data that does not fit in one packet.
        payload (bytes | bytearray | None): The payload to be sent in this packet.

    Returns:
        bytearray: The packet.
    """

    packet = CreatePacketHeader(command, receiverAddr, senderAddr, packetNumber, isLastPacket)

    if (packetPayload is not None) and (len(packetPayload) > 0):
        if len(packetPayload) > 16:
            raise Exception(f"Packet payload is too large: {len(packetPayload)}")
        
        packet.extend(packetPayload)

    crc8 = crc.CalculateHoymilesCrc8(packet, len(packet))
    packet.extend(crc8.to_bytes(1, "big", signed=False))

    # replace special characters
    packet = EscapeData(packet)

    if len(packet) > MAX_PACKET_SIZE:
        raise Exception(f"Internal error __CreatePacket: packet size ({len(packet)}) > MAX_PACKET_SIZE ({MAX_PACKET_SIZE})")
    
    return packet

def CreatePacketHeader(command : hd.Request, receiverAddr : bytes, senderAddr : bytes, packetNumber : int, isLastPacket : bool) -> bytearray:
    """ Creates the packet header.

    Args:
        command (InverterCmd): The packet command.
        receiverAddr (bytes): The address of the receiver generated from the receiver (inverter) serial number. (4 bytes)
        senderAddr (bytes): The address of the sender generated from the sender (DTU) serial number. (4 bytes)
        packetNumber (int): The frame number (1, 2, ...) for message data that does not fit in one packet.
        isLastPacket (bool): True if it is the last frame for message data that does not fit in one packet.

    Returns:
        bytearray: The packet header.
    """
    if len(receiverAddr) != 4:
        raise Exception(f"Invalid length of receiver address: {len(receiverAddr)}. (must be 4 bytes)")
    
    if len(senderAddr) != 4:
        raise Exception(f"Invalid length of sender address: {len(senderAddr)}. (must be 4 bytes)")
    
    if packetNumber > 15:
        raise Exception(f"Packet number is too large: {packetNumber}")
    
    header = bytearray(10)

    header[0] = command
    header[1:5] = receiverAddr
    header[5:9] = senderAddr
    header[9] = packetNumber
    
    if isLastPacket:
        if packetNumber == 1:
            header[9] = 0x80
        else:
            header[9] |= 0x80

    if len(header) != 10:
        raise Exception(f"Internal error CreatePacketHeader: size {len(header)} != 10")
    
    return header

def CreateDataFromTime(currentTime : float) -> bytearray:
    """ Creates payload data filled with the time.

    Args:
        currentTime (float): The current time in s since the start of the epoch.

    Returns:
        bytearray: The payload data.
    """
    payload = bytearray(14)

    payload[0] = 0x0B
    payload[1] = 0x00
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

    for idx in range(len(input)):
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

    return output

