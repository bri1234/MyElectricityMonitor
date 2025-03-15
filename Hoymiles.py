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

import pyrf24 as nrf
import MyCrc as crc
import time
import uuid
import textwrap
import HoymilesDefinitions as hoyDef

class HoymilesHmDtu:
    """ Class for communication with HM300, HM350, HM400, HM600, HM700, HM800, HM1200 & HM1500 inverter.
        DTU means 'data transfer unit'.
    """

    __RX_PIPE = 1
    __RX_PACKET_TIMEOUT_NS = 10_000_000

    __dtuRadioId : bytes
    __dtuRadioAddress : bytes

    __inverterSerialNumber : str
    __inverterRadioId : bytes
    __inverterRadioAddress : bytes
    __inverterType : hoyDef.InverterType

    __pinCsn : int
    __pinCe : int
    __spiFrequency : int
    
    __radio : nrf.RF24 | None

    __expectedResponsePackets : list[int]

    def __init__(self, inverterSerialNumber : str,
                 pinCsn : int = 0, pinCe : int = 24, spiFrequency : int = 1000000) -> None:
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

        self.__dtuRadioId = HoymilesHmDtu.__GenerateDtuRadioId()
        self.__dtuRadioAddress = b'\01' + self.__dtuRadioId

        self.__inverterRadioId = HoymilesHmDtu.__GetInverterRadioId(self.__inverterSerialNumber)
        self.__inverterRadioAddress = b'\01' + self.__inverterRadioId

        self.__inverterType = HoymilesHmDtu.__GetInverterTypeFromSerialNumber(self.__inverterSerialNumber)
        self.__expectedResponsePackets = HoymilesHmDtu.__GetResponseFramesFromInverterType(self.__inverterType)
        
    def InitializeCommunication(self) -> None:
        """ Initializes the NRF24L01 communication.
        """
        radio = nrf.RF24(self.__pinCe, self.__pinCsn, self.__spiFrequency)

        if not radio.begin():
            raise Exception("Can not initialize RF24!")

        radio.set_radiation(nrf.rf24_pa_dbm_e.RF24_PA_LOW, nrf.rf24_datarate_e.RF24_250KBPS)
        radio.set_retries(10, 15)
        radio.dynamic_payloads = True
        radio.set_auto_ack(HoymilesHmDtu.__RX_PIPE, True)
        radio.crc_length = nrf.rf24_crclength_e.RF24_CRC_16
        radio.address_width = 5

        radio.open_rx_pipe(HoymilesHmDtu.__RX_PIPE, self.__dtuRadioAddress) 

        self.__radio = radio

    # def QueryInformations(self, timeout : float = 3) -> None:

    #     # create request info message
    #     payloadCurrentTime = HoymilesHmDtu.__CreatePayloadFromTime(time.time())
    #     packetRequestInfo = self.__CreatePacket(HoymilesHmDtu.__CMD_TX_REQ_INFO, payloadCurrentTime)

    #     startTime = time.time()

    def __SetPowerLevel(self, powerLevel : nrf.rf24_pa_dbm_e) -> None:
        """ Changes the output power level.

        Args:
            powerLevel (nrf.rf24_pa_dbm_e): The new power level.
        """
        if self.__radio is None:
            raise Exception("Communication is not initialized!")

        self.__radio.set_radiation(powerLevel, nrf.rf24_datarate_e.RF24_250KBPS)

    def __SendPacket(self, channel : int, packet : bytearray | bytes) -> bool:
        """ Sends a package to the receiver.

        Args:
            channel (int): The channel where the data shall be sent.
            packet (bytearray): The data.
        """
        if self.__radio is None:
            raise Exception("Communication is not initialized!")

        # ATTENTION: the data to be sent must not contain the control bytes 0x7D, 0x7E, 0x7F
        if (0x7D in packet) or (0x7D in packet) or (0x7D in packet):
            raise Exception("the data to be sent must not contain the control bytes 0x7D, 0x7E, 0x7F")
        
        radio = self.__radio

        radio.listen = False
        radio.flush_rx()
        radio.channel = channel
        radio.open_tx_pipe(self.__inverterRadioAddress) 

        success = radio.write(packet)
        return success
    
    def TestReceivePackets(self, channel : int, timeout_ms : int) -> None:
        if self.__radio is None:
            raise Exception("Communication is not initialized!")

        radio = self.__radio

        radio.flush_tx()
        radio.channel = channel
        radio.listen = True

        startTime = time.time_ns()
        while (time.time_ns() - startTime) / 1000000 < timeout_ms:
            
            isDataAvailable, pipeNum = radio.available_pipe()

            if isDataAvailable:
                print("data available")

            if (not isDataAvailable) or (pipeNum != HoymilesHmDtu.__RX_PIPE):
                continue
            
            packetLength = radio.get_dynamic_payload_size()
            packet = radio.read(packetLength)

            print(f"***** packet received on channel {channel}: len = {len(packet)} *****")
            str = " ".join(textwrap.wrap(packet.hex(), 2))
            print(f"   {str}")


        radio.listen = False

    def TestComm(self) -> None:

        try:
            self.__SetPowerLevel(nrf.rf24_pa_dbm_e.RF24_PA_HIGH)

            payload = self.__CreatePayloadFromTime(time.time())
            packet = self.__CreatePacket(hoyDef.Request.INFO, 1 | hoyDef.IS_LAST_FRAME, payload)

            txChannel = 3
            print(f"tx channel {txChannel}")

            rxChannelList = hoyDef.RF_CHANNELS.copy()
            rxChannelList.remove(txChannel)

            for _ in range(1000):
                # listen for response
                for rxChannel in rxChannelList:
                    # send request
                    print(f"    tx channel {txChannel}")
                    if self.__SendPacket(txChannel, packet):
                        print("SEND SUCCESS")
                    
                    print(f"    rx channel {rxChannel}")
                    self.TestReceivePackets(rxChannel, 100)

        finally:
            self.__SetPowerLevel(nrf.rf24_pa_dbm_e.RF24_PA_LOW)


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
        
        radio = self.__radio

        radio.channel = channel
        radio.listen = True

        remainingPacketsToReceive = packetsToReceive.copy()
        receivedPackets : dict[int, bytearray] = {}
        startTime = time.time_ns()

        while time.time_ns() - startTime  < HoymilesHmDtu.__RX_PACKET_TIMEOUT_NS:

            if not self.__radio.available():
                continue
            
            packetLength = radio.get_dynamic_payload_size()
            packet = radio.read(packetLength)

            # ignore data if CRC error
            if not HoymilesHmDtu.CheckChecksum(packet):
                continue

            receivedPacketType = packet[9]

            if receivedPacketType in remainingPacketsToReceive:
                remainingPacketsToReceive.remove(receivedPacketType)

                receivedPacketData = packet[10:]
                receivedPackets[receivedPacketType] = receivedPacketData

                if len(remainingPacketsToReceive):
                    break

        return receivedPackets
    
    
    def PrintNrf24l01Info(self) -> None:
        """ Prints NRF24L01 module information on standard output.
        """
        if self.__radio is None:
            raise Exception("Communication is not initialized!")
        
        self.__radio.print_pretty_details()

    @staticmethod
    def __GetInverterTypeFromSerialNumber(inverterSerialNumber : str) -> hoyDef.InverterType:
        """ Determines the inverter type from serial number.

        Args:
            inverterSerialNumber (str): The inverter serial number as printed on the sticker on the inverter case.

        Returns:
            int: The inverter type: 1 = HM300, HM350, HM400; 2 = HM600, HM700, HM800; 3 = HM1200, HM1500
        """
        match inverterSerialNumber[0:2]:
            case "10" | "11":
                match inverterSerialNumber[2:4]:
                    case "21" | "22" | "24":
                        return hoyDef.InverterType.InverterOneChannel
                    case "41" | "42" | "44":
                        return hoyDef.InverterType.InverterTwoChannels
                    case "61" | "62" | "64":
                        return hoyDef.InverterType.InverterFourChannels
                    case _:
                        pass
            case _:
                pass

        raise Exception(f"Inverter type with serial number {inverterSerialNumber} is not supported.")

    @staticmethod
    def __GetResponseFramesFromInverterType(inverterType : hoyDef.InverterType) -> list[int]:
        """ Returns a list of the frames that the inverter will send if data is querried.

        Args:
            inverterType (InverterType): The type of the inverter.

        Returns:
            list[int]: List of packet types for a response on a data query.
        """

        # hint: 0x80 indicates that it is the last frame

        match inverterType:
            case hoyDef.InverterType.InverterOneChannel:
                return [ 0x01, 0x82 ]                       # inverter sends 2 frames
            case hoyDef.InverterType.InverterTwoChannels:
                return [ 0x01, 0x02, 0x83 ]                 # inverter sends 3 frames
            case hoyDef.InverterType.InverterFourChannels:
                return [ 0x01, 0x02, 0x03, 0x04, 0x85 ]     # inverter sends 5 frames
            case _:
                raise Exception(f"Unsupported inverter type {inverterType}")

    @staticmethod
    def __GetInverterRadioId(inverterSerialNumber : str) -> bytes:
        """ Returns the inverter radio ID from the serial number.
            The radio ID is used to send and receive packets.

        Args:
            inverterSerialNumber (str): The inverter serial number.

        Returns:
            bytes: The inverter radio ID.
        """
        serialNumberStr = inverterSerialNumber[4:]
        serialNumber = bytearray.fromhex(serialNumberStr)
        # serialNumber.reverse()

        return bytes(serialNumber)

    @staticmethod
    def __GenerateDtuRadioId() -> bytes:
        """ Generates a DTU radio ID (data transfer unit, this device) from the system UUID.
            The radio ID is used to send and receive packets.

        Returns:
            bytes: The DTU radio ID.
        """

        # u = uuid.uuid1().int

        # id = 0x81000000
        # id |= (u % 10) << 4
        # id |= ((u // 10) % 10) << 8
        # id |= ((u // 100) % 10) << 12
        # id |= ((u // 1000) % 10) << 16
        # id |= ((u // 10000) % 10) << 20

        # return id.to_bytes(4, "big", signed=False)

        return bytes([0x78, 0x56, 0x30, 0x01])

    @staticmethod
    def CheckChecksum(packet : bytes | bytearray) -> bool:
        """ Checks the checksum of a packet.

        Args:
            packet (bytes | bytearray): The packet to be checked.

        Returns:
            bool: True if the checksum is valid.
        """
        checksum1 = crc.CalculateHoymilesCrc8(packet, len(packet) - 1)
        checksum2 = packet[-1]
        return checksum1 == checksum2
        
if __name__ == "__main__":

    hm = HoymilesHmDtu("114184020874", 0, 24, 1000000)

    hm.InitializeCommunication()
    hm.PrintNrf24l01Info()
    hm.TestComm()

