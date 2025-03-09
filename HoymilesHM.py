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
import MyCrc as crc
import time
from enum import Enum, IntEnum

class InverterType(Enum):
    HM300 = 1
    HM600 = 2
    HM1200 = 3

class InverterCmd(IntEnum):
    TX_REQ_INFO = 0x15
    TX_REQ_DEVCONTROL = 0x51

class InverterFrame(IntEnum):
    ALL_FRAMES = 0x80
    SINGLE_FRAME = 0x81

class HoymilesHmDtu:
    """ Class for communication with HM300, HM350, HM400, HM600, HM700, HM800, HM1200 & HM1500 inverter.
        DTU means 'data transfer unit'.
    """

    __TX_CHANNELS : list[int] = [ 3, 23, 40, 61, 75 ]

    __RX_CHANNELS : dict[int, list[int]] = {
        3 : [40, 61],
        23 : [61, 75],
        40 : [3, 75],
        61 : [3, 23],
        75 : [23, 40]
    }

    __RX_PIPE = 1
    __RX_PACKET_TIMEOUT_NS = 10_000_000
    __MAX_PACKET_SIZE = 32

    __dtuSerialNumber : str
    __dtuRadioId : bytearray        # CP_U32_LittleEndian(&mTxBuf[5], mDtuSn);

    __inverterSerialNumber : str
    __inverterRadioId : bytearray   # CP_U32_BigEndian(&mTxBuf[1], ivId >> 8);
    __inverterType : InverterType

    __pinCsn : int
    __pinCe : int
    __spiFrequency : int
    
    __radio : nrf.RF24 | None

    __expectedResponsePackages : list[int]

    __txChannel : int

    def __init__(self, inverterSerialNumber : str,
                 pinCsn : int = 0, pinCe : int = 24, spiFrequency : int = 1000000, txChannelNumber : int = 0) -> None:
        """ Creates a new communication object.

        Args:
            inverterSerialNumber (str): The inverter serial number. (As printed on a sticker on the inverter case.)
            pinCsn (int, optional): The CSN pin as SPI device number (0 or 1). Defaults to 0.
            pinCe (int, optional): The GPIO pin connected to NRF24L01 signal CE. Defaults to 24.
            spiFrequency (int, optional): The SPI frequency in Hz. Defaults to 1000000.
            txChannelNumber (int, optional): TX channel number 0 .. 4.
        """
        self.__inverterSerialNumber = inverterSerialNumber
        self.__pinCsn = pinCsn
        self.__pinCe = pinCe
        self.__spiFrequency = spiFrequency

        self.__inverterType = HoymilesHmDtu.__GetInverterTypeFromSerialNumber(self.__inverterSerialNumber)
        self.__expectedResponsePackages = HoymilesHmDtu.__GetResponsePacketTypesFromInverterType(self.__inverterType)

        self.__txChannel = HoymilesHmDtu.__TX_CHANNELS[txChannelNumber]
        self.__rxChannel = HoymilesHmDtu.__RX_CHANNELS[self.__txChannel]
        
    def InitializeCommunication(self) -> None:
        """ Initializes the NRF24L01 communication.
        """
        radio = nrf.RF24(self.__pinCe, self.__pinCsn, self.__spiFrequency)

        if not radio.begin():
            raise Exception("Can not initialize RF24!")

        radio.set_radiation(nrf.rf24_pa_dbm_e.RF24_PA_LOW, nrf.rf24_datarate_e.RF24_250KBPS)
        radio.set_retries(3, 15)
        radio.dynamic_payloads = True
        radio.set_auto_ack(HoymilesHmDtu.__RX_PIPE, True)
        radio.crc_length = nrf.rf24_crclength_e.RF24_CRC_16
        radio.address_width = 5
        radio.open_rx_pipe(HoymilesHmDtu.__RX_PIPE, self.__dtuRadioId)

        self.__radio = radio

    def QueryInformations(self, timeout : float = 3) -> None:

        # create request info message
        payloadCurrentTime = HoymilesHmDtu.__CreatePayloadFromTime(time.time())
        packetRequestInfo = self.__CreatePacket(HoymilesHmDtu.__CMD_TX_REQ_INFO, payloadCurrentTime)

        startTime = time.time()




    def __TransmitPacket(self, channel : int, packet : bytearray) -> None:
        """ Sends a package to the rceiver. The sender and receiver address is included in the package data.
            Receiver address: bytes 1 - 4.
            Sender address: bytes 5 - 8.

        Args:
            channel (int): The channel where the data shall be sent.
            packet (bytearray): The data.
        """
        if self.__radio is None:
            raise Exception("Communication is not initialized!")

        receiverAddr = b'\01' + packet[1:5]
        senderAddr = b'\01' + packet[5:9]

        self.__radio.flush_tx()
        self.__radio.channel = channel
        self.__radio.listen = False
        self.__radio.open_tx_pipe(receiverAddr)

        self.__radio.write(packet)
    
    def __ReceivePackets(self, channel : int, packetsToReceive : list[int]) -> dict[int, bytearray]:
        """ Receives a list of packets. 

        Args:
            channel (int): The channel where to listen.
            packetsToReceive (list[int]): List of type of packets to receive.

        Returns:
            dict[int, bytearray]: Received packets. (Can be less then requested number of packets.)
        """
        if self.__radio is None:
            raise Exception("Communication is not initialized!")
        
        self.__radio.channel = channel
        self.__radio.listen = True

        remainingPacketsToReceive = packetsToReceive.copy()
        receivedPackets : dict[int, bytearray] = {}
        startTime = time.time_ns()

        while time.time_ns() - startTime  < HoymilesHmDtu.__RX_PACKET_TIMEOUT_NS:

            if not self.__radio.available():
                continue
            
            buffer = self.__radio.read(32)

            # ignore data if CRC error
            checksum1 = crc.CalculateHoymilesCrc8(buffer, 26)
            checksum2 = buffer[26]
            if checksum1 != checksum2:
                continue

            receivedPacketType = buffer[9]

            if receivedPacketType in remainingPacketsToReceive:
                remainingPacketsToReceive.remove(receivedPacketType)

                receivedPacketData = buffer[10:26]
                receivedPackets[receivedPacketType] = receivedPacketData

                if len(remainingPacketsToReceive):
                    break

        return receivedPackets
    
    @staticmethod
    def __CreatePayloadFromTime(currentTime : float) -> bytearray:
        """ Creates payload data filled with the time.

        Args:
            currentTime (float): The current time.

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
    
    def __CreatePacketHeader(self, command : InverterCmd, frame : InverterFrame) -> bytearray:
        """ Creates the packet header.

        Args:
            command (InverterCmd): The packet command.
            frame (InverterFrame): The packet frame.

        Returns:
            bytearray: The packet header.
        """
        header = bytearray(10)

        header[0] = command
        header[1:5] = self.__inverterRadioId
        header[5:9] = self.__dtuRadioId
        header[9] = frame
        
        if len(header) != 10:
            raise Exception(f"Internal error __CreatePacketHeader: size {len(header)} != 10")
        
        return header
    
    def __CreatePacket(self, command : InverterCmd, frame : InverterFrame, payload : bytes | bytearray | None) -> bytearray:
        """ Creates the packet.

        Args:
            command (InverterCmd): The packet command.
            frame (InverterFrame): The packet frame.
            payload (bytes | bytearray | None): The payload to be sent.

        Returns:
            bytearray: The packet.
        """

        packet = self.__CreatePacketHeader(command, frame)

        if (payload is not None) and (len(payload) > 0):
            packet.extend(payload)

            crc16 = crc.CalculateHoymilesCrc16(payload, len(payload))
            packet.extend(crc16.to_bytes(2, "big", signed=False))

        crc8 = crc.CalculateHoymilesCrc8(packet, len(packet))
        packet.extend(crc8.to_bytes(1, "big", signed=False))

        if len(packet) > HoymilesHmDtu.__MAX_PACKET_SIZE:
            raise Exception(f"Internal error __CreatePacket: packet size ({len(packet)}) > MAX_PACKET_SIZE ({HoymilesHmDtu.__MAX_PACKET_SIZE})")
        
        return packet
    
    def PrintNrf24l01Info(self) -> None:
        """ Prints NRF24L01 module info on standard output.
        """
        if self.__radio is None:
            raise Exception("Communication is not initialized!")
        
        self.__radio.print_pretty_details()

    @staticmethod
    def __GetInverterTypeFromSerialNumber(inverterSerialNumber : str) -> InverterType:
        """ Determines the inverter type from serial number.

        Args:
            inverterSerialNumber (str): The inverter serial number as printed on the sticker on the inverter case.

        Returns:
            int: The inverter type: 1 = HM300, HM350, HM400; 2 = HM600, HM700, HM800; 3 = HM1200, HM1500
        """
        match inverterSerialNumber[:4]:
            case "1121":
                return InverterType.HM300
            case "1141":
                return InverterType.HM600
            case "1161":
                return InverterType.HM1200
            case _:
                raise Exception(f"Inverter type is not supported. (Serial number must start with: 1121, 1141 or 1161)")

    @staticmethod
    def __GetResponsePacketTypesFromInverterType(inverterType : InverterType) -> list[int]:
        """ Returns a list of the packet types that the inverter will send if data is querried.

        Args:
            inverterType (InverterType): The type of the inverter.

        Returns:
            list[int]: List of packet types for a response on a data query.
        """
        match inverterType:
            case InverterType.HM300:
                return [ 0x01, 0x82 ]
            case InverterType.HM600:
                return [ 0x01, 0x02, 0x83 ]
            case InverterType.HM1200:
                return [ 0x01, 0x02, 0x03, 0x04, 0x85 ]
            case _:
                raise Exception(f"Unsupported inverter type {inverterType}")

    @staticmethod
    def __GetInverterRadioId(inverterSerialNumber : str) -> bytes:
        
    @staticmethod
    def __GetInverterRadioId(inverterSerialNumber : str) -> bytes:
        
    @staticmethod
    def __GenerateDtuSerialNumber() -> str:
        id = 56346234234566
        id &= 0x0FFFFFFF
        id |= 0x80000000
        return str(id)

if __name__ == "__main__":

    hm = HoymilesHmDtu("114184020874", 0, 24, 1000000)
    hm.InitializeCommunication()
    hm.PrintNrf24l01Info()

        