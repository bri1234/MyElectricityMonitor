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
import HoymilesMessageData as hmd
import gc
from typing import Union

class HoymilesHmDtu:
    """ Class for communication with HM300, HM350, HM400, HM600, HM700, HM800, HM1200 & HM1500 inverter.
        DTU means 'data transfer unit'.
    """

    __RX_PIPE = 1

    __dtuRadioId : bytes
    __dtuRadioAddress : bytes

    __inverterSerialNumber : str
    __inverterRadioId : bytes
    __inverterRadioAddress : bytes
    __inverterNumberOfChannels : int

    __pinCsn : int
    __pinCe : int
    __spiFrequency : int

    __radio : Union[nrf.RF24, None]

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

        self.__inverterNumberOfChannels = HoymilesHmDtu.__GetInverterNumberOfChannels(self.__inverterSerialNumber)
        self.__expectedResponsePackets = HoymilesHmDtu.__GetResponseFramesFromInverterType(self.__inverterNumberOfChannels)

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

        radio.open_rx_pipe(HoymilesHmDtu.__RX_PIPE, self.__dtuRadioAddress)
        radio.open_tx_pipe(self.__inverterRadioAddress)

        self.__radio = radio

    def __SetPowerLevel(self, powerLevel : nrf.rf24_pa_dbm_e) -> None:
        """ Changes the output power level.

        Args:
            powerLevel (nrf.rf24_pa_dbm_e): The new power level.
        """
        if self.__radio is None:
            raise Exception("Communication is not initialized!")

        self.__radio.set_radiation(powerLevel, nrf.rf24_datarate_e.RF24_250KBPS)

    def __SendPacket(self, channel : int, packet : Union[bytes, bytearray]) -> bool:
        """ Sends a package to the receiver.

        Args:
            channel (int): The channel where the data shall be sent.
            packet (bytearray): The data.
        """
        if self.__radio is None:
            raise Exception("Communication is not initialized!")

        if (0x7E in packet) or (0x7F in packet):
            raise Exception("the data to be sent must not contain the control bytes 0x7E, 0x7F")

        radio = self.__radio

        radio.listen = False
        radio.flush_rx()
        radio.channel = channel

        success = radio.write(packet)
        return success

    def TestReceivePackets(self, txChannel : int, txPacket : bytearray, rxChannel : int, timeout_ms : int) -> tuple[int, dict[int, int]]:
        if self.__radio is None:
            raise Exception("Communication is not initialized!")

        try:
            gc.disable()
            responseReceived = 0

            radio = self.__radio

            statistic : dict[int, int] = { 0x01: 0, 0x02: 0, 0x83: 0 }
            endTime = time.time_ns() + timeout_ms * 1000000

            radio.listen = False
            radio.flush_rx()
            radio.set_retries(3, 6) # not too many reties to listen fast enough on packet 1
            radio.channel = txChannel

            radio.write(txPacket)

            # radio.flush_tx()
            radio.channel = rxChannel
            radio.listen = True

            while time.time_ns() < endTime:

                isDataAvailable, pipeNum = radio.available_pipe()
                if (not isDataAvailable) or (pipeNum != HoymilesHmDtu.__RX_PIPE):
                    continue

                # TODO: check target radio ID

                packetLength = radio.get_dynamic_payload_size()
                packet = radio.read(packetLength)
                frameNum = packet[9]

                responseReceived += 1
                statistic[frameNum] += 1

                # print(f"    rx: frame=${frameNum:02X} ch={channel} ", flush=True)

            radio.listen = False

            return responseReceived, statistic
        finally:
            gc.enable()

    def TestComm(self) -> None:

        try:
            
            self.__SetPowerLevel(nrf.rf24_pa_dbm_e.RF24_PA_HIGH)

            # txPacket = hmd.CreateRfVersionPacket(self.__inverterRadioId, self.__dtuRadioId)
            txPacket = hmd.CreateRequestInfoPacket(self.__inverterRadioId, self.__dtuRadioId, time.time())
            
            channelList = [ 3, 23, 40, 61, 75 ]

            for txChannel in channelList:
                for rxChannel in channelList:
                    if txChannel == rxChannel:
                        continue

                    print(f"TX {txChannel} RX {rxChannel}", flush=True)
                    totalResponseReceived = 0
                    totalStatistic : dict[int, int] = { 0x01: 0, 0x02: 0, 0x83: 0 }

                    for _ in range(200):
                        time.sleep(0.9)
                        
                        responseReceived, statistic = self.TestReceivePackets(txChannel, txPacket, rxChannel, 200)

                        totalResponseReceived += responseReceived
                        for k in statistic.keys():
                            totalStatistic[k] += statistic[k]

                        print("." if responseReceived == 0 else "O", end="", flush=True)

                    print()
                    print(f"    TX {txChannel} RX {rxChannel} Response {totalResponseReceived}", flush=True)

                    for k in totalStatistic.keys():
                        print(f"        ${k:02X}: {totalStatistic[k]}", flush=True)
        finally:
            self.__SetPowerLevel(nrf.rf24_pa_dbm_e.RF24_PA_LOW)

    def TestReceivePacketsScan(self, channelList : list[int]) -> int:
        if self.__radio is None:
            raise Exception("Communication is not initialized!")

        responseReceived = 0
        timeout_ms = 20

        radio = self.__radio

        radio.flush_tx()
        radio.channel = channelList[0]
        radio.listen = True

        for _ in range(3):
            for channel in channelList:
                radio.channel = channel

                endTime = time.time_ns() + timeout_ms * 1000000
                while time.time_ns() < endTime:
                    isDataAvailable, pipeNum = radio.available_pipe()

                    # if isDataAvailable:
                    #     print("data available")

                    if (not isDataAvailable) or (pipeNum != HoymilesHmDtu.__RX_PIPE):
                        continue
                    
                    # TODO: check target radio ID

                    packetLength = radio.get_dynamic_payload_size()
                    packet = radio.read(packetLength)

                    responseReceived += 1

                    print(f"    rx: frame=${packet[9]:02X} ch={channel} ", flush=True)

        radio.listen = False

        return responseReceived

    def TestCommScan(self) -> None:

        try:
            self.__SetPowerLevel(nrf.rf24_pa_dbm_e.RF24_PA_HIGH)

            # packet = hmd.CreateRfVersionPacket(self.__inverterRadioId, self.__dtuRadioId)
            packet = hmd.CreateRequestInfoPacket(self.__inverterRadioId, self.__dtuRadioId, time.time())
            
            # channelList = [ 3, 23, 40, 61, 75 ]
            channelList = [ 3 ]

            for txChannel in channelList:

                rxChannelList = hmd.RX_CHANNELS_REQUEST_INFO[txChannel]

                print(f"TX {txChannel} RX {rxChannelList}", flush=True)

                for _ in range(100):
                    time.sleep(0.9)
                    
                    print(f"TX ch {txChannel}", flush=True)
                    self.__SendPacket(txChannel, packet)

                    self.TestReceivePacketsScan(rxChannelList)

        finally:
            self.__SetPowerLevel(nrf.rf24_pa_dbm_e.RF24_PA_LOW)


    def QueryInfo(self, txChannel : int = 3) -> None:
        if self.__radio is None:
            raise Exception("Communication is not initialized!")
        radio = self.__radio

        # variables
        timeout_ms = 20
        timeout_ns = timeout_ms * 1000000

        rxChannelList = hmd.RX_CHANNELS_REQUEST_INFO[txChannel]

        # create packet
        packet = hmd.CreateRequestInfoPacket(self.__inverterRadioId, self.__dtuRadioId, time.time())

        try:
            self.__SetPowerLevel(nrf.rf24_pa_dbm_e.RF24_PA_HIGH)
            gc.disable()

            radio.listen = False
            radio.set_retries(3, 5) # not too many retries because we want to listen fast enough for first packet
            
            numResponseReceived = 0

            for _ in range(20):
                # send packet
                radio.flush_rx()
                radio.channel = txChannel

                radio.write(packet)

                # listen for response
                radio.flush_tx()
                radio.listen = True
                
                for rxChannel in rxChannelList:
                    radio.channel = rxChannel

                    endTime = time.time_ns() + timeout_ns
                    while time.time_ns() < endTime:
                        isDataAvailable, pipeNum = radio.available_pipe()

                        if (not isDataAvailable) or (pipeNum != HoymilesHmDtu.__RX_PIPE):
                            continue
                        
                        # TODO: check target radio ID

                        packetLength = radio.get_dynamic_payload_size()
                        packet = radio.read(packetLength)

                        numResponseReceived += 1

                        # print(f"    rx: frame=${packet[9]:02X} ch={channel} ", flush=True)

            radio.listen = False

        finally:
            gc.enable()
            self.__SetPowerLevel(nrf.rf24_pa_dbm_e.RF24_PA_LOW)
        
        print(f"got {numResponseReceived} responses")

    def PrintNrf24l01Info(self) -> None:
        """ Prints NRF24L01 module information on standard output.
        """
        if self.__radio is None:
            raise Exception("Communication is not initialized!")

        self.__radio.print_pretty_details()

    @staticmethod
    def __GetInverterNumberOfChannels(inverterSerialNumber : str) -> int:
        """ Determines the inverter type from serial number.

        Args:
            inverterSerialNumber (str): The inverter serial number as printed on the sticker on the inverter case.

        Returns:
            int: The inverter type: 1 = HM300, HM350, HM400; 2 = HM600, HM700, HM800; 3 = HM1200, HM1500
        """
        if inverterSerialNumber[0:2] in ("10", "11"):
            
            s = inverterSerialNumber[2:4]

            if s in ("21", "22", "24"):
                return 1
            
            if s in ("41", "42", "44"):
                return 2
            
            if s in ("61", "62", "64"):
                return 4

        raise Exception(f"Inverter type with serial number {inverterSerialNumber} is not supported.")

    @staticmethod
    def __GetResponseFramesFromInverterType(inverterNumberOfChannels : int) -> list[int]:
        """ Returns a list of the frames that the inverter will send if data is querried.

        Args:
            inverterNumberOfChannels (int): The type of the inverter.

        Returns:
            list[int]: List of packet types for a response on a data query.
        """

        # 0x80 indicates that it is the last frame

        if inverterNumberOfChannels == 1:
            return [ 0x01, 0x82 ]                       # inverter sends 2 frames
        if inverterNumberOfChannels == 2:
            return [ 0x01, 0x02, 0x83 ]                 # inverter sends 3 frames
        if inverterNumberOfChannels == 4:
            return [ 0x01, 0x02, 0x03, 0x04, 0x85 ]     # inverter sends 5 frames
        
        raise Exception(f"Unsupported inverter type {inverterNumberOfChannels}")

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

        return bytes(serialNumber)

    @staticmethod
    def __GenerateDtuRadioId() -> bytes:
        """ Generates a DTU radio ID (data transfer unit, this device) from the system UUID.
            The radio ID is used to send and receive packets.

        Returns:
            bytes: The DTU radio ID.
        """

        u = uuid.uuid1().int
        id = 0

        for _ in range(7):
            id |= u % 10
            id <<= 4
            u //= 10

        id |= 0x80000000

        return id.to_bytes(4, "big", signed=False)

    @staticmethod
    def CheckChecksum(packet : Union[bytes, bytearray]) -> bool:
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
    # hm.TestComm()
    # hm.TestCommScan()
    hm.QueryInfo()

