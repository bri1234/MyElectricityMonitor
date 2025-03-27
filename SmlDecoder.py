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
    checkSum2 = __CalculateSmlCrc16(data, len(data) - 2)

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
    checkSum2 = __CalculateSmlCrc16(data, len(data) - 2)

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

__CRC16_X25_TABLE = [
	0x0000, 0x1189, 0x2312, 0x329B, 0x4624, 0x57AD,	0x6536, 0x74BF,
	0x8C48, 0x9DC1, 0xAF5A, 0xBED3, 0xCA6C, 0xDBE5, 0xE97E, 0xF8F7,
	0x1081, 0x0108,	0x3393, 0x221A, 0x56A5, 0x472C, 0x75B7, 0x643E,
	0x9CC9, 0x8D40, 0xBFDB, 0xAE52, 0xDAED, 0xCB64,	0xF9FF, 0xE876,
	0x2102, 0x308B, 0x0210, 0x1399,	0x6726, 0x76AF, 0x4434, 0x55BD,
	0xAD4A, 0xBCC3,	0x8E58, 0x9FD1, 0xEB6E, 0xFAE7, 0xC87C, 0xD9F5,
	0x3183, 0x200A, 0x1291, 0x0318, 0x77A7, 0x662E,	0x54B5, 0x453C,
	0xBDCB, 0xAC42, 0x9ED9, 0x8F50,	0xFBEF, 0xEA66, 0xD8FD, 0xC974,
	0x4204, 0x538D,	0x6116, 0x709F, 0x0420, 0x15A9, 0x2732, 0x36BB,
	0xCE4C, 0xDFC5, 0xED5E, 0xFCD7, 0x8868, 0x99E1,	0xAB7A, 0xBAF3,
	0x5285, 0x430C, 0x7197, 0x601E,	0x14A1, 0x0528, 0x37B3, 0x263A,
	0xDECD, 0xCF44,	0xFDDF, 0xEC56, 0x98E9, 0x8960, 0xBBFB, 0xAA72,
	0x6306, 0x728F, 0x4014, 0x519D, 0x2522, 0x34AB,	0x0630, 0x17B9,
	0xEF4E, 0xFEC7, 0xCC5C, 0xDDD5,	0xA96A, 0xB8E3, 0x8A78, 0x9BF1,
	0x7387, 0x620E,	0x5095, 0x411C, 0x35A3, 0x242A, 0x16B1, 0x0738,
	0xFFCF, 0xEE46, 0xDCDD, 0xCD54, 0xB9EB, 0xA862,	0x9AF9, 0x8B70,
	0x8408, 0x9581, 0xA71A, 0xB693,	0xC22C, 0xD3A5, 0xE13E, 0xF0B7,
	0x0840, 0x19C9,	0x2B52, 0x3ADB, 0x4E64, 0x5FED, 0x6D76, 0x7CFF,
	0x9489, 0x8500, 0xB79B, 0xA612, 0xD2AD, 0xC324,	0xF1BF, 0xE036,
	0x18C1, 0x0948, 0x3BD3, 0x2A5A,	0x5EE5, 0x4F6C, 0x7DF7, 0x6C7E,
	0xA50A, 0xB483,	0x8618, 0x9791, 0xE32E, 0xF2A7, 0xC03C, 0xD1B5,
	0x2942, 0x38CB, 0x0A50, 0x1BD9, 0x6F66, 0x7EEF,	0x4C74, 0x5DFD,
	0xB58B, 0xA402, 0x9699, 0x8710,	0xF3AF, 0xE226, 0xD0BD, 0xC134,
	0x39C3, 0x284A,	0x1AD1, 0x0B58, 0x7FE7, 0x6E6E, 0x5CF5, 0x4D7C,
	0xC60C, 0xD785, 0xE51E, 0xF497, 0x8028, 0x91A1,	0xA33A, 0xB2B3,
	0x4A44, 0x5BCD, 0x6956, 0x78DF,	0x0C60, 0x1DE9, 0x2F72, 0x3EFB,
	0xD68D, 0xC704,	0xF59F, 0xE416, 0x90A9, 0x8120, 0xB3BB, 0xA232,
	0x5AC5, 0x4B4C, 0x79D7, 0x685E, 0x1CE1, 0x0D68,	0x3FF3, 0x2E7A,
	0xE70E, 0xF687, 0xC41C, 0xD595,	0xA12A, 0xB0A3, 0x8238, 0x93B1,
	0x6B46, 0x7ACF,	0x4854, 0x59DD, 0x2D62, 0x3CEB, 0x0E70, 0x1FF9,
	0xF78F, 0xE606, 0xD49D, 0xC514, 0xB1AB, 0xA022,	0x92B9, 0x8330,
	0x7BC7, 0x6A4E, 0x58D5, 0x495C,	0x3DE3, 0x2C6A, 0x1EF1, 0x0F78]

def __CalculateSmlCrc16(data : bytes | bytearray, dataLen : int) -> int:
	""" Calculates the CRC16 checksum for Smart Message Language of a byte array.

	Args:
		data (bytearray): The byte array on which the ckecksum is to be calculated.
		dataLen (int): Number of bytes to be used to calculate the checksum.

	Returns:
		int: The CRC16 checksum of the byte array.
	"""
	crcsum = 0xFFFF

	for idx in range(dataLen):
		crcsum = __CRC16_X25_TABLE[(data[idx] ^ crcsum) & 0xff] ^ (crcsum >> 8 & 0xff)

	crcsum ^= 0xffff
	return crcsum

###################################################################################################
# functions for debugging
###################################################################################################

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
    if valueType == 0:
        return "String"
    if valueType == 4:
        return "Bool"
    if valueType == 5:
        return "Int"
    if valueType == 6:
        return "UInt"
    if valueType == 7:
        return "List"
    
    return "???"

