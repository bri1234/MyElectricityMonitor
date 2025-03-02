"""
Decoder for SML messages.

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

from typing import Any
import MyCrc as crc

__ESCAPE_SEQUENCE = bytes([0x1B, 0x1B, 0x1B, 0x1B])
__SML_START = bytes([0x01, 0x01, 0x01, 0x01])

__DATA_TYPE_STR = 0
__DATA_TYPE_BOOL = 4
__DATA_TYPE_INT = 5
__DATA_TYPE_UINT = 6
__DATA_TYPE_LIST = 7

def __DecodeTypeLengthField(data : bytearray, pos : int) -> tuple[int, int, int]:
    """ Decodes the type length field.

    Args:
        data (bytearray): The raw SML binary data.
        pos (int): The position of the type length field.

    Returns:
        tuple[int, int, int]: The number of type length field read, the data typ, the data length
    """

    tlFieldSize = 1
    tlField = data[pos]
    dataType = ((tlField & 0x70) >> 4)
    dataLen = tlField & 0x0F

    while (tlField & 0x80) != 0:
        pos += 1
        tlFieldSize += 1
        dataLen <<= 4
        dataLen |= data[pos] & 0x0F

    return tlFieldSize, dataType, dataLen

def __DecodeValue(data : bytearray, pos : int) -> tuple[bytes | bool | int | list[Any], int, bool]:
    """ Decodes a value of type string, bool, int, uint or list.

    Args:
        data (bytearray): The raw SML binary data.
        pos (int): The position of the type length field.

    Returns:
        str | bool | int | list[Any]: The decoded value.
        int: The position after the value.
    """

    tlFieldSize, dataType, dataLen = __DecodeTypeLengthField(data, pos)
    valueStartPos = pos + tlFieldSize
    valueEndPos = pos + dataLen

    # __PrintDebug(data, pos, dataType, dataLen, tlFieldSize)

    value : bytes | bool | int | list[Any]
    endOfMsg = False

    if data[pos] == 0:
        value = 0
        endOfMsg = True
        valueEndPos = pos + 1
    elif (dataType == __DATA_TYPE_STR) and (dataLen >= 1):
        value = bytes(data[valueStartPos:valueEndPos])
    elif (dataType == __DATA_TYPE_BOOL) and (dataLen == 2):
        value = (data[valueStartPos] != 0)
    elif (dataType == __DATA_TYPE_INT) and (dataLen >= 2) and (dataLen <= 9):
        value = int.from_bytes(data[valueStartPos:valueEndPos], byteorder="big", signed=True)
    elif (dataType == __DATA_TYPE_UINT) and (dataLen >= 2) and (dataLen <= 9):
        value = int.from_bytes(data[valueStartPos:valueEndPos], byteorder="big", signed=False)
    elif dataType == __DATA_TYPE_LIST:
        value = list()
        for _ in range(dataLen):
            listItem, valueEndPos, endOfMsg = __DecodeValue(data, valueStartPos)
            valueStartPos = valueEndPos

            if not endOfMsg:
                value.append(listItem)
    else:
        raise Exception(f"Unknown data type {data[pos]:02X} at position {pos}")
    
    return value, valueEndPos, endOfMsg

def CheckIfSmlIsValid(data : bytearray) -> bool:
    """ Checks if the check sum of the SML message is valid.

    Args:
        data (bytearray): The raw byte data of the SML message.

    Returns:
        bool: True if the ckeck sum is valid.
    """

    count = len(data)
    checkSum1 = int.from_bytes(data[count - 2:count], byteorder="little", signed=False)
    checkSum2 = crc.CalculateSmlCrc16(data, len(data) - 2)

    return checkSum1 == checkSum2

def DecodeSmlMessages(data : bytearray) -> list[Any]:
    """ Decodes the SML messages.

    Args:
        data (bytearray): The raw byte data of the SML messages.

    Returns:
        list[Any]: List of decoded messages.
    """

    # check for escape sequence
    if data[0:4] != __ESCAPE_SEQUENCE:
        raise Exception("missing escape sequence at position 0")

    # check version
    if data[4:8] != __SML_START:
        raise Exception("missing SML start sequence at position 4")

    # check for second escape sequence
    count = len(data)

    if data[count - 8:count - 4] != __ESCAPE_SEQUENCE:
        raise Exception(f"missing second escape sequence at position {count - 8}")

    if data[count - 4] != 0x1A:
        raise Exception(f"missing 0x1A at position {count - 4}")

    # get number of fill bytes
    numberOfFillBytes = data[count - 3]
    lastMsgBodyIndex = count - 8 - numberOfFillBytes

    # check checksum
    checkSum1 = int.from_bytes(data[count - 2:count], byteorder="little", signed=False)
    checkSum2 = crc.CalculateSmlCrc16(data, len(data) - 2)

    if checkSum1 != checkSum2:
        raise Exception(f"Checksum error: file {checkSum1:04X} calc {checkSum2:04X}")
    
    messageList : list[Any] = []
    pos = 8
    while pos < lastMsgBodyIndex:
        message, pos, endOfMsg = __DecodeValue(data, pos)

        if not endOfMsg:
            raise Exception(f"missing end of message")

        messageList.append(message)

    return messageList

def PrintValue(value : bytes | bool | int | list[Any], indent : int = 0) -> None:
    """ Prints the SML data structure.

    Args:
        value (bytes | bool | int | list[Any]): The SML data structure.
        indent (int, optional): The number of spaces before the before. Defaults to 0.
    """
    print(" " * indent, end="")

    if isinstance(value, list):
        print("List:")
        for listItem in value:
            PrintValue(listItem, indent + 4)
    elif isinstance(value, bytes):
        s = value.replace(b"\0", b"\\0")
        print(f"String: {s}")
    elif isinstance(value, bool):
        print(f"Bool: {value}")
    elif isinstance(value, int):
        print(f"Int: {value}")
    else:
        raise Exception(f"Invalid value: {value}")

def __LoadHexDataFromString(hexData : str) -> bytearray:
    """ Converts hex bytes in a string to an array oif bytes.

    Args:
        hexData (str): The hex byte string in the form "A5 42 FF ...".

    Returns:
        bytearray: the converted byte array.
    """

    byteArr = bytearray()

    strArr = hexData.split(" ")
    for s in strArr:
        byteArr.append(int(s, 16))

    return byteArr

if __name__ == "__main__":

    testData = [
        "1B 1B 1B 1B 01 01 01 01 76 05 00 95 A0 D5 62 00 62 00 72 65 00 00 01 01 76 01 01 07 65 42 5A 44 44 33 0B 09 01 45 42 5A 01 00 2D 16 C3 01 01 63 32 DE 00 76 05 00 95 A0 D6 62 00 62 00 72 65 00 00 07 01 77 01 0B 09 01 45 42 5A 01 00 2D 16 C3 01 72 62 01 65 00 18 F1 35 7A 77 07 81 81 C7 82 03 FF 01 01 01 01 04 45 42 5A 01 77 07 01 00 00 00 09 FF 01 01 01 01 0B 09 01 45 42 5A 01 00 2D 16 C3 01 77 07 01 00 01 08 00 FF 64 01 01 80 01 62 1E 52 FB 69 00 00 00 08 BA 13 9B 6E 01 77 07 01 00 01 08 01 FF 01 01 62 1E 52 FB 69 00 00 00 08 B4 25 5B 8E 01 77 07 01 00 01 08 02 FF 01 01 62 1E 52 FB 69 00 00 00 00 05 EE 3F E0 01 77 07 01 00 02 08 00 FF 64 01 01 80 01 62 1E 52 FB 69 00 00 00 00 0D 18 5B 20 01 77 07 01 00 10 07 00 FF 01 01 62 1B 52 FE 55 00 00 01 85 01 77 07 01 00 24 07 00 FF 01 01 62 1B 52 FE 55 00 00 01 85 01 77 07 01 00 38 07 00 FF 01 01 62 1B 52 FE 55 00 00 00 00 01 77 07 01 00 4C 07 00 FF 01 01 62 1B 52 FE 55 00 00 00 00 01 01 01 63 88 D6 00 76 05 00 95 A0 D7 62 00 62 00 72 65 00 00 02 01 71 01 63 76 07 00 00 00 00 1B 1B 1B 1B 1A 03 4E 67",
        "1B 1B 1B 1B 01 01 01 01 76 05 00 95 A0 DB 62 00 62 00 72 65 00 00 01 01 76 01 01 07 65 42 5A 44 44 33 0B 09 01 45 42 5A 01 00 2D 16 C3 01 01 63 27 AC 00 76 05 00 95 A0 DC 62 00 62 00 72 65 00 00 07 01 77 01 0B 09 01 45 42 5A 01 00 2D 16 C3 01 72 62 01 65 00 18 F1 36 7A 77 07 81 81 C7 82 03 FF 01 01 01 01 04 45 42 5A 01 77 07 01 00 00 00 09 FF 01 01 01 01 0B 09 01 45 42 5A 01 00 2D 16 C3 01 77 07 01 00 01 08 00 FF 64 01 01 80 01 62 1E 52 FB 69 00 00 00 08 BA 13 9B CA 01 77 07 01 00 01 08 01 FF 01 01 62 1E 52 FB 69 00 00 00 08 B4 25 5B EA 01 77 07 01 00 01 08 02 FF 01 01 62 1E 52 FB 69 00 00 00 00 05 EE 3F E0 01 77 07 01 00 02 08 00 FF 64 01 01 80 01 62 1E 52 FB 69 00 00 00 00 0D 18 5B 20 01 77 07 01 00 10 07 00 FF 01 01 62 1B 52 FE 55 00 00 01 4B 01 77 07 01 00 24 07 00 FF 01 01 62 1B 52 FE 55 00 00 01 4B 01 77 07 01 00 38 07 00 FF 01 01 62 1B 52 FE 55 00 00 00 00 01 77 07 01 00 4C 07 00 FF 01 01 62 1B 52 FE 55 00 00 00 00 01 01 01 63 56 AB 00 76 05 00 95 A0 DD 62 00 62 00 72 65 00 00 02 01 71 01 63 44 21 00 00 00 00 1B 1B 1B 1B 1A 03 DE 02",
        "1B 1B 1B 1B 01 01 01 01 76 05 00 95 A0 E1 62 00 62 00 72 65 00 00 01 01 76 01 01 07 65 42 5A 44 44 33 0B 09 01 45 42 5A 01 00 2D 16 C3 01 01 63 D8 CF 00 76 05 00 95 A0 E2 62 00 62 00 72 65 00 00 07 01 77 01 0B 09 01 45 42 5A 01 00 2D 16 C3 01 72 62 01 65 00 18 F1 37 7A 77 07 81 81 C7 82 03 FF 01 01 01 01 04 45 42 5A 01 77 07 01 00 00 00 09 FF 01 01 01 01 0B 09 01 45 42 5A 01 00 2D 16 C3 01 77 07 01 00 01 08 00 FF 64 01 01 80 01 62 1E 52 FB 69 00 00 00 08 BA 13 9C 30 01 77 07 01 00 01 08 01 FF 01 01 62 1E 52 FB 69 00 00 00 08 B4 25 5C 50 01 77 07 01 00 01 08 02 FF 01 01 62 1E 52 FB 69 00 00 00 00 05 EE 3F E0 01 77 07 01 00 02 08 00 FF 64 01 01 80 01 62 1E 52 FB 69 00 00 00 00 0D 18 5B 20 01 77 07 01 00 10 07 00 FF 01 01 62 1B 52 FE 55 00 00 01 6E 01 77 07 01 00 24 07 00 FF 01 01 62 1B 52 FE 55 00 00 01 6E 01 77 07 01 00 38 07 00 FF 01 01 62 1B 52 FE 55 00 00 00 00 01 77 07 01 00 4C 07 00 FF 01 01 62 1B 52 FE 55 00 00 00 00 01 01 01 63 EA FE 00 76 05 00 95 A0 E3 62 00 62 00 72 65 00 00 02 01 71 01 63 B2 FE 00 00 00 00 1B 1B 1B 1B 1A 03 71 58",
        "1B 1B 1B 1B 01 01 01 01 76 05 00 95 A0 E7 62 00 62 00 72 65 00 00 01 01 76 01 01 07 65 42 5A 44 44 33 0B 09 01 45 42 5A 01 00 2D 16 C3 01 01 63 07 23 00 76 05 00 95 A0 E8 62 00 62 00 72 65 00 00 07 01 77 01 0B 09 01 45 42 5A 01 00 2D 16 C3 01 72 62 01 65 00 18 F1 38 7A 77 07 81 81 C7 82 03 FF 01 01 01 01 04 45 42 5A 01 77 07 01 00 00 00 09 FF 01 01 01 01 0B 09 01 45 42 5A 01 00 2D 16 C3 01 77 07 01 00 01 08 00 FF 64 01 01 80 01 62 1E 52 FB 69 00 00 00 08 BA 13 9C 93 01 77 07 01 00 01 08 01 FF 01 01 62 1E 52 FB 69 00 00 00 08 B4 25 5C B3 01 77 07 01 00 01 08 02 FF 01 01 62 1E 52 FB 69 00 00 00 00 05 EE 3F E0 01 77 07 01 00 02 08 00 FF 64 01 01 80 01 62 1E 52 FB 69 00 00 00 00 0D 18 5B 20 01 77 07 01 00 10 07 00 FF 01 01 62 1B 52 FE 55 00 00 01 66 01 77 07 01 00 24 07 00 FF 01 01 62 1B 52 FE 55 00 00 01 66 01 77 07 01 00 38 07 00 FF 01 01 62 1B 52 FE 55 00 00 00 00 01 77 07 01 00 4C 07 00 FF 01 01 62 1B 52 FE 55 00 00 00 00 01 01 01 63 C0 EF 00 76 05 00 95 A0 E9 62 00 62 00 72 65 00 00 02 01 71 01 63 80 D8 00 00 00 00 1B 1B 1B 1B 1A 03 3B 6A", 
        "1B 1B 1B 1B 01 01 01 01 76 05 00 95 A0 ED 62 00 62 00 72 65 00 00 01 01 76 01 01 07 65 42 5A 44 44 33 0B 09 01 45 42 5A 01 00 2D 16 C3 01 01 63 77 1E 00 76 05 00 95 A0 EE 62 00 62 00 72 65 00 00 07 01 77 01 0B 09 01 45 42 5A 01 00 2D 16 C3 01 72 62 01 65 00 18 F1 39 7A 77 07 81 81 C7 82 03 FF 01 01 01 01 04 45 42 5A 01 77 07 01 00 00 00 09 FF 01 01 01 01 0B 09 01 45 42 5A 01 00 2D 16 C3 01 77 07 01 00 01 08 00 FF 64 01 01 80 01 62 1E 52 FB 69 00 00 00 08 BA 13 9C F5 01 77 07 01 00 01 08 01 FF 01 01 62 1E 52 FB 69 00 00 00 08 B4 25 5D 15 01 77 07 01 00 01 08 02 FF 01 01 62 1E 52 FB 69 00 00 00 00 05 EE 3F E0 01 77 07 01 00 02 08 00 FF 64 01 01 80 01 62 1E 52 FB 69 00 00 00 00 0D 18 5B 20 01 77 07 01 00 10 07 00 FF 01 01 62 1B 52 FE 55 00 00 01 5E 01 77 07 01 00 24 07 00 FF 01 01 62 1B 52 FE 55 00 00 01 5E 01 77 07 01 00 38 07 00 FF 01 01 62 1B 52 FE 55 00 00 00 00 01 77 07 01 00 4C 07 00 FF 01 01 62 1B 52 FE 55 00 00 00 00 01 01 01 63 81 76 00 76 05 00 95 A0 EF 62 00 62 00 72 65 00 00 02 01 71 01 63 6E C5 00 00 00 00 1B 1B 1B 1B 1A 03 C0 EA", 
        "1B 1B 1B 1B 01 01 01 01 76 05 00 95 A0 F3 62 00 62 00 72 65 00 00 01 01 76 01 01 07 65 42 5A 44 44 33 0B 09 01 45 42 5A 01 00 2D 16 C3 01 01 63 E7 59 00 76 05 00 95 A0 F4 62 00 62 00 72 65 00 00 07 01 77 01 0B 09 01 45 42 5A 01 00 2D 16 C3 01 72 62 01 65 00 18 F1 3A 7A 77 07 81 81 C7 82 03 FF 01 01 01 01 04 45 42 5A 01 77 07 01 00 00 00 09 FF 01 01 01 01 0B 09 01 45 42 5A 01 00 2D 16 C3 01 77 07 01 00 01 08 00 FF 64 01 01 80 01 62 1E 52 FB 69 00 00 00 08 BA 13 9D 60 01 77 07 01 00 01 08 01 FF 01 01 62 1E 52 FB 69 00 00 00 08 B4 25 5D 80 01 77 07 01 00 01 08 02 FF 01 01 62 1E 52 FB 69 00 00 00 00 05 EE 3F E0 01 77 07 01 00 02 08 00 FF 64 01 01 80 01 62 1E 52 FB 69 00 00 00 00 0D 18 5B 20 01 77 07 01 00 10 07 00 FF 01 01 62 1B 52 FE 55 00 00 01 83 01 77 07 01 00 24 07 00 FF 01 01 62 1B 52 FE 55 00 00 01 83 01 77 07 01 00 38 07 00 FF 01 01 62 1B 52 FE 55 00 00 00 00 01 77 07 01 00 4C 07 00 FF 01 01 62 1B 52 FE 55 00 00 00 00 01 01 01 63 54 B7 00 76 05 00 95 A0 F5 62 00 62 00 72 65 00 00 02 01 71 01 63 8C B9 00 00 00 00 1B 1B 1B 1B 1A 03 57 44", 
        "1B 1B 1B 1B 01 01 01 01 76 05 00 95 A0 F9 62 00 62 00 72 65 00 00 01 01 76 01 01 07 65 42 5A 44 44 33 0B 09 01 45 42 5A 01 00 2D 16 C3 01 01 63 97 64 00 76 05 00 95 A0 FA 62 00 62 00 72 65 00 00 07 01 77 01 0B 09 01 45 42 5A 01 00 2D 16 C3 01 72 62 01 65 00 18 F1 3B 7A 77 07 81 81 C7 82 03 FF 01 01 01 01 04 45 42 5A 01 77 07 01 00 00 00 09 FF 01 01 01 01 0B 09 01 45 42 5A 01 00 2D 16 C3 01 77 07 01 00 01 08 00 FF 64 01 01 80 01 62 1E 52 FB 69 00 00 00 08 BA 13 9D BA 01 77 07 01 00 01 08 01 FF 01 01 62 1E 52 FB 69 00 00 00 08 B4 25 5D DA 01 77 07 01 00 01 08 02 FF 01 01 62 1E 52 FB 69 00 00 00 00 05 EE 3F E0 01 77 07 01 00 02 08 00 FF 64 01 01 80 01 62 1E 52 FB 69 00 00 00 00 0D 18 5B 20 01 77 07 01 00 10 07 00 FF 01 01 62 1B 52 FE 55 00 00 01 45 01 77 07 01 00 24 07 00 FF 01 01 62 1B 52 FE 55 00 00 01 45 01 77 07 01 00 38 07 00 FF 01 01 62 1B 52 FE 55 00 00 00 00 01 77 07 01 00 4C 07 00 FF 01 01 62 1B 52 FE 55 00 00 00 00 01 01 01 63 05 8B 00 76 05 00 95 A0 FB 62 00 62 00 72 65 00 00 02 01 71 01 63 0A 89 00 00 00 00 1B 1B 1B 1B 1A 03 AB B4" 
    ]

    for d in testData:
        data = __LoadHexDataFromString(d)
        messageList = DecodeSmlMessages(data)
        
        for msg in messageList:
            PrintValue(msg)

###################################################################################################
# functions for debugging

def __PrintDebug(data : bytearray, pos : int, dataType : int, dataLen : int, tlFieldSize : int) -> None: # type: ignore
    """ Debug output for value type parsing.

    Args:
        data (bytearray): The raw SML binary data.
        pos (int): The position of the type length field.
        dataType (int): Parsed data type.
        dataLen (int): Parsed data length.
        tlFieldSize (int): Parsed type length field size.
    """
    if data[pos] == 0:
        print(f"Pos: {pos} END_OF_MSG")
        return
    
    tlfStr = " ".join(f'{a:02X}' for a in data[pos:pos + tlFieldSize])

    print(f"Pos: {pos} Type: {__ValueTypeToStr(dataType)} Len: {dataLen} TLF: {tlfStr}")
    if dataType == __DATA_TYPE_LIST:
        print(f"    {tlfStr}")
    else:
        print(f"    {' '.join(f'{a:02X}' for a in data[pos:pos + dataLen])}")

def __ValueTypeToStr(valueType : int) -> str:
    """ Converts value type to string.

    Args:
        valueType (int): The value type.

    Returns:
        str: The value type as a string.
    """
    match valueType:
        case 0:
            return "String"
        case 4:
            return "Bool"
        case 5:
            return "Int"
        case 6:
            return "UInt"
        case 7:
            return "List"
        case _:
            return "???"

