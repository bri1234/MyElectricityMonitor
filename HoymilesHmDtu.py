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
import time
import uuid
import gc
import random

class HoymilesHmDtu:
    """ Class for communication with HM300, HM350, HM400, HM600, HM700, HM800, HM1200 & HM1500 inverter.
        (DTU means 'data transfer unit'.)

        Usage:

            hm = HoymilesHmDtu("1141xxxxxxxx", 0, 24)
            hm.InitializeCommunication()
            success, info = hm.QueryInverterInfo()

    """

    # the nRF24L01 receive pipeline
    __RX_PIPE_NUM = 1

    # timeout for channel scan
    __RECEIVE_TIMEOUT_MS = 5

    # the SPI communication frequency
    __SPI_FREQUENCY_HZ = 1000000

    # the power level to send the request to the receiver
    __RADIO_POWER_LEVEL = nrf.rf24_pa_dbm_e.RF24_PA_MAX

    # time to wait before a new request is sent to the inverter if the previous request was not received
    __WAIT_BEFORE_RETRY_S = 3

    # maximum size of packets that can be sent with the nRF24L01 module
    __MAX_PACKET_SIZE = 32

    # list of channels where the inverter listen for requests
    __TX_CHANNELS = [ 3, 23, 40, 61, 75 ]

    # list of channels where the inverter sends the responses depending on the channel, where the request was received
    __RX_CHANNEL_LISTS = {
        3: [ 23, 40, 61 ],
        23: [ 40, 61, 75 ],
        40 : [ 61, 75,  3 ],
        61 : [ 75,  3, 23 ],
        75 : [  3, 23, 40 ]
    }

    # DTU (this device) 4 bytes radio address
    __dtuRadioAddress : bytes

    # inverter serial number (12 digits)
    __inverterSerialNumber : str

    # the inverter has 1, 2 or 4 channels
    __inverterNumberOfChannels : int

    # inverter 4 bytes radio address (part of the inverter serial number)
    __inverterRadioAddress : bytes

    # the CSn pin: 0 or 1, usually 0
    __pinCsn : int

    # the GPIO pin where the CE signal is connected
    __pinCe : int

    # the nRF24L01 radio object
    __radio : nrf.RF24 | None

    def __init__(self, inverterSerialNumber : str,
                 pinCsn : int = 0, pinCe : int = 24) -> None:
        """ Creates a new Hoymiles HM communication object.

        Args:
            inverterSerialNumber (str): The inverter serial number. (As printed on the sticker on the inverter case.)
            pinCsn (int, optional): The CSN pin as SPI device number (0 or 1), usually 0. Defaults to 0.
            pinCe (int, optional): The GPIO pin connected to the NRF24L01 CE signal. Defaults to 24.
        """
        self.__inverterSerialNumber = inverterSerialNumber
        self.__pinCsn = pinCsn
        self.__pinCe = pinCe

        self.__dtuRadioAddress = HoymilesHmDtu.__GenerateDtuRadioAddress()
        self.__inverterRadioAddress = HoymilesHmDtu.__GetInverterRadioAddress(self.__inverterSerialNumber)
        self.__inverterNumberOfChannels = HoymilesHmDtu.__GetInverterNumberOfChannels(self.__inverterSerialNumber)

    def InitializeCommunication(self) -> None:
        """ Initializes the NRF24L01 communication.
        """
        radio = nrf.RF24(self.__pinCe, self.__pinCsn, HoymilesHmDtu.__SPI_FREQUENCY_HZ)

        if not radio.begin():
            raise Exception("Can not initialize RF24!")
        
        if not radio.isChipConnected():
            raise Exception("Error chip is not connected!")

        radio.stopListening()

        radio.setDataRate(nrf.rf24_datarate_e.RF24_250KBPS)
        radio.setPALevel(nrf.rf24_pa_dbm_e.RF24_PA_MIN)
        radio.setCRCLength(nrf.rf24_crclength_e.RF24_CRC_16)
        radio.setAddressWidth(5)

        radio.openWritingPipe(b'\01' + self.__inverterRadioAddress)
        radio.openReadingPipe(HoymilesHmDtu.__RX_PIPE_NUM, b'\01' + self.__dtuRadioAddress)

        radio.enableDynamicPayloads()
        radio.setRetries(3, 10)
        radio.setAutoAck(True)

        self.__radio = radio

    def QueryInverterInfo(self, numberOfRetries : int = 20) -> tuple[bool, dict[str, float | list[dict[str, float]]]]:
        """ Requests info data from the inverter and returns the inverter response.

        Args:
            numberOfRetries (int): Number of requests before giving up.

        Returns:
            bool: Success (True or False)
            dict[str, float | list[dict[str, float]]]: The inverter information.
        """

        if self.__radio is None:
            raise Exception("Communication is not initialized!")
        
        radio = self.__radio

        radio.flush_tx()
        radio.flush_rx()

        try:
            # increase power level
            radio.setPALevel(HoymilesHmDtu.__RADIO_POWER_LEVEL)

            for retryIndex in range(numberOfRetries):

                if retryIndex > 0:
                    time.sleep(HoymilesHmDtu.__WAIT_BEFORE_RETRY_S)

                # select a random channel for the request
                txChannelIndex = random.randint(0, len(HoymilesHmDtu.__TX_CHANNELS) - 1)
                txChannel = HoymilesHmDtu.__TX_CHANNELS[txChannelIndex]
                rxChannelList = HoymilesHmDtu.__RX_CHANNEL_LISTS[txChannel]

                # create packet to send to the inverter
                txPacket = HoymilesHmDtu.__CreateRequestInfoPacket(self.__inverterRadioAddress, self.__dtuRadioAddress, time.time())
                
                # send request and scan for responses
                responseList = HoymilesHmDtu.__SendRequestAndScanForResponses(radio, txChannel, rxChannelList, txPacket)

                # did we get a valid response?
                success, responseData = HoymilesHmDtu.__EvaluateInverterInfoResponse(responseList, self.__inverterRadioAddress, self.__inverterNumberOfChannels)
                if success:
                    success, info = HoymilesHmDtu.__ExtractInverterInfo(responseData, self.__inverterNumberOfChannels)
                    if success:
                        return True, info

        finally:
            radio.setPALevel(nrf.rf24_pa_dbm_e.RF24_PA_MIN)

        return False, {}

    @staticmethod
    def PrintInverterInfo(info : dict[str, float | list[dict[str, float]]]) -> None:
        """ Prints inverter information in human readable form.

        Args:
            info (dict[str, float  |  list[dict[str, float]]]): The inverter information got with function QueryInverterInfo().
        """
        for key in info.keys():
            value = info[key]
            
            if key == "Channels" and isinstance(value, list):
                for channelIndex in range(len(value)):
                    print(f"Channel {channelIndex + 1}")

                    for k in value[channelIndex].keys():
                        print(f"    {k} = {value[channelIndex][k]}")

            else:
                print(f"{key} = {info[key]}")

    def PrintNrf24l01Info(self) -> None:
        """ Prints NRF24L01 module information on standard output.
        """
        if self.__radio is None:
            raise Exception("Communication is not initialized!")

        self.__radio.print_pretty_details()

    @staticmethod
    def __SendRequestAndScanForResponses(radio : nrf.RF24, txChannel : int, rxChannelList : list[int],
                                         txPacket : bytearray) -> list[bytearray]:
        """ Send a request to the inverter and scan receive channels for the response.

        Args:
            radio (nrf.RF24): The radio used to sent the request.
            txChannel (int): The channel where the request shall be sent.
            rxChannelList (list[int]): The channel list to scan for responses.
            txPacket (bytearray): The request packet.

        Returns:
            list[bytearray]: List of reponse packets.
        """
        responseList : list[bytearray] = []

        try:
            gc.disable()

            # send request to the inverter
            radio.stopListening()
            radio.setChannel(txChannel)
            radio.flush_rx()

            radio.write(txPacket)

            # scan channels for response from the inverter
            radio.startListening()

            for rxChannelIndex in range(100):
                rxChannel = rxChannelList[rxChannelIndex % 3]

                radio.setChannel(rxChannel)

                endTime = time.time_ns() + HoymilesHmDtu.__RECEIVE_TIMEOUT_MS * 1000000

                while time.time_ns() < endTime:
                    if radio.available():
                        # read packet data
                        packetLen = radio.getDynamicPayloadSize()
                        packet = radio.read(packetLen)
                        radio.flush_rx()

                        # store raw packet data
                        responseList.append(packet)

        finally:
            gc.enable()

        # undo replace of special characters
        for idx in range(len(responseList)):
            responseList[idx] = HoymilesHmDtu.__UnescapeData(responseList[idx])

        return responseList

    @staticmethod
    def __ExtractInverterInfo(responseData : bytearray, numberOfChannels : int) -> tuple[bool, dict[str, float | list[dict[str, float]]]]:
        """ Extracts the inverter infos from the reponse data.

        Args:
            responseData (bytearray): The response data.
            numberOfChannels (int): Number of inverter channels.

        Returns:
            bool: True if successfull
            dict[str, float | list[dict[str, float]]]: The inverter infos.
        """
        # check the checksum
        crc1 = int.from_bytes(responseData[-2:], "big")
        crc2 = HoymilesHmDtu.__CalculateCrc16(responseData, len(responseData) - 2)
        if crc1 != crc2:
            return False, {}
        
        # extract the data depending on the inverter type
        if numberOfChannels == 1:
            return True, HoymilesHmDtu.__ExtractInverterInfoOneChannel(responseData)

        if numberOfChannels == 2:
            return True, HoymilesHmDtu.__ExtractInverterInfoTwoChannels(responseData)

        if numberOfChannels == 4:
            return True, HoymilesHmDtu.__ExtractInverterInfoFourChannels(responseData)
        
        raise Exception(f"Can not extract inverter info. Inverter with {numberOfChannels} channel(s) not supported!")

    @staticmethod
    def __ExtractInverterInfoOneChannel(responseData : bytearray) -> dict[str, float | list[dict[str, float]]]:
        """ Extracts inverter infos for inverters with one channel.

        Args:
            responseData (bytearray): The response data.

        Returns:
            dict[str, float | list[dict[str, float]]]: The inverter infos.
        """
        
        channel1 : dict[str, float] = {}

        channel1["DC V"] = int.from_bytes(responseData[2:4], "big") / 10.0           # V
        channel1["DC I"] = int.from_bytes(responseData[4:6], "big") / 100.0          # A
        channel1["DC P"] = int.from_bytes(responseData[6:8], "big") / 10.0           # W
        channel1["DC E total"] = int.from_bytes(responseData[8:12], "big") / 1000.0  # kWh
        channel1["DC E day"] = int.from_bytes(responseData[12:14], "big") / 1.0      # Wh

        info : dict[str, float | list[dict[str, float]]] = {}
        info["Channels"] = [channel1]

        info["AC V"] = int.from_bytes(responseData[14:16], "big") / 10.0         # V
        info["AC F"] = int.from_bytes(responseData[16:18], "big") / 100.0        # Hz
        info["AC P"] = int.from_bytes(responseData[18:20], "big") / 10.0         # W
        info["Q"] = int.from_bytes(responseData[20:22], "big") / 10.0            # VAR (W) reactive power
        info["AC I"] = int.from_bytes(responseData[22:24], "big") / 100.0        # A
        info["AC PF"] = int.from_bytes(responseData[24:26], "big") / 1000.0      # -
        info["T"] = int.from_bytes(responseData[26:28], "big") / 10.0            # °C
        info["EVT"] = int.from_bytes(responseData[28:30], "big") / 1.0           # -

        return info

    @staticmethod
    def __ExtractInverterInfoTwoChannels(responseData : bytearray) -> dict[str, float | list[dict[str, float]]]:
        """ Extracts inverter infos for inverters with two channels.

        Args:
            responseData (bytearray): The response data.

        Returns:
            dict[str, float | list[dict[str, float]]]: The inverter infos.
        """
        
        channel1 : dict[str, float] = {}

        channel1["DC V"] = int.from_bytes(responseData[2:4], "big") / 10.0           # V
        channel1["DC I"] = int.from_bytes(responseData[4:6], "big") / 100.0          # A
        channel1["DC P"] = int.from_bytes(responseData[6:8], "big") / 10.0           # W
        channel1["DC E total"] = int.from_bytes(responseData[14:18], "big") / 1000.0 # kWh
        channel1["DC E day"] = int.from_bytes(responseData[22:24], "big") / 1.0      # Wh

        channel2 : dict[str, float] = {}

        channel2["DC V"] = int.from_bytes(responseData[8:10], "big") / 10.0          # V
        channel2["DC I"] = int.from_bytes(responseData[10:12], "big") / 100.0        # A
        channel2["DC P"] = int.from_bytes(responseData[12:14], "big") / 10.0         # W
        channel2["DC E total"] = int.from_bytes(responseData[18:22], "big") / 1000.0 # kWh
        channel2["DC E day"] = int.from_bytes(responseData[24:26], "big") / 1.0      # Wh

        info : dict[str, float | list[dict[str, float]]] = {}
        info["Channels"] = [channel1, channel2]

        info["AC V"] = int.from_bytes(responseData[26:28], "big") / 10.0         # V
        info["AC F"] = int.from_bytes(responseData[28:30], "big") / 100.0        # Hz
        info["AC P"] = int.from_bytes(responseData[30:32], "big") / 10.0         # W
        info["Q"] = int.from_bytes(responseData[32:34], "big") / 10.0            # VAR (W) reactive power
        info["AC I"] = int.from_bytes(responseData[34:36], "big") / 100.0        # A
        info["AC PF"] = int.from_bytes(responseData[36:38], "big") / 1000.0      # -
        info["T"] = int.from_bytes(responseData[38:40], "big") / 10.0            # °C
        info["EVT"] = int.from_bytes(responseData[40:42], "big") / 1.0           # -

        return info

    @staticmethod
    def __ExtractInverterInfoFourChannels(responseData : bytearray) -> dict[str, float | list[dict[str, float]]]:
        """ Extracts inverter infos for inverters with four channels.

        Args:
            responseData (bytearray): The response data.

        Returns:
            dict[str, float | list[dict[str, float]]]: The inverter infos.
        """

        channel1 : dict[str, float] = {}

        channel1["DC V"] = int.from_bytes(responseData[2:4], "big") / 10.0           # V
        channel1["DC I"] = int.from_bytes(responseData[4:6], "big") / 100.0          # A
        channel1["DC P"] = int.from_bytes(responseData[8:10], "big") / 10.0          # W
        channel1["DC E total"] = int.from_bytes(responseData[12:16], "big") / 1000.0 # kWh
        channel1["DC E day"] = int.from_bytes(responseData[20:22], "big") / 1.0      # Wh

        channel2 : dict[str, float] = {}

        channel2["DC V"] = int.from_bytes(responseData[2:4], "big") / 10.0           # V
        channel2["DC I"] = int.from_bytes(responseData[6:8], "big") / 100.0          # A
        channel2["DC P"] = int.from_bytes(responseData[10:12], "big") / 10.0         # W
        channel2["DC E total"] = int.from_bytes(responseData[16:20], "big") / 1000.0 # kWh
        channel2["DC E day"] = int.from_bytes(responseData[22:24], "big") / 1.0      # Wh

        channel3 : dict[str, float] = {}

        channel3["DC V"] = int.from_bytes(responseData[24:26], "big") / 10.0         # V
        channel3["DC I"] = int.from_bytes(responseData[26:28], "big") / 100.0        # A
        channel3["DC P"] = int.from_bytes(responseData[30:32], "big") / 10.0         # W
        channel3["DC E total"] = int.from_bytes(responseData[34:38], "big") / 1000.0 # kWh
        channel3["DC E day"] = int.from_bytes(responseData[42:44], "big") / 1.0      # Wh

        channel4 : dict[str, float] = {}

        channel4["DC V"] = int.from_bytes(responseData[24:26], "big") / 10.0         # V
        channel4["DC I"] = int.from_bytes(responseData[28:30], "big") / 100.0        # A
        channel4["DC P"] = int.from_bytes(responseData[32:34], "big") / 10.0         # W
        channel4["DC E total"] = int.from_bytes(responseData[38:42], "big") / 1000.0 # kWh
        channel4["DC E day"] = int.from_bytes(responseData[44:46], "big") / 1.0      # Wh

        info : dict[str, float | list[dict[str, float]]] = {}
        info["Channels"] = [channel1, channel2, channel3, channel4]

        info["AC V"] = int.from_bytes(responseData[46:48], "big") / 10.0         # V
        info["AC F"] = int.from_bytes(responseData[48:50], "big") / 100.0        # Hz
        info["AC P"] = int.from_bytes(responseData[50:52], "big") / 10.0         # W
        info["Q"] = int.from_bytes(responseData[52:54], "big") / 10.0            # VAR (W) reactive power
        info["AC I"] = int.from_bytes(responseData[54:56], "big") / 100.0        # A
        info["AC PF"] = int.from_bytes(responseData[56:58], "big") / 1000.0      # -
        info["T"] = int.from_bytes(responseData[58:60], "big") / 10.0            # °C
        info["EVT"] = int.from_bytes(responseData[60:62], "big") / 1.0           # -

        return info

    @staticmethod
    def __EvaluateInverterInfoResponse(responseList : list[bytearray],
                                       inverterRadioAddress : bytes, inverterNumberOfChannels : int) -> tuple[bool, bytearray]:
        """ Checks if the responses are valid and returns the assembled data.

        Args:
            responseList (list[bytearray]): List of received inverter responses.
            inverterRadioAddress (bytes): The inverter radio address (4 bytes).
            inverterNumberOfChannels (int): The number of inverter channels.

        Returns:
            bool: True if all responses are valid.
            bytearray: The assembled response data.
        """
        
        numberOfResponses = inverterNumberOfChannels + 1
        responseData = bytearray()

        # did we get the right number of responses?
        if len(responseList) != numberOfResponses:
            return False, responseData

        for idx in range(numberOfResponses):
            response = responseList[idx]

            # are the frame numbers valid?
            frameNumberResponse = response[9]
            frameNumberExpected = idx + 1
            if frameNumberExpected == numberOfResponses: # is it the last frame?
                frameNumberExpected |= 0x80

            if frameNumberResponse != frameNumberExpected:
                return False, responseData

            # are the receiver addresses valid?
            address1 = response[1:5]
            address2 = response[5:9]
            if (address1 != inverterRadioAddress) or (address2 != inverterRadioAddress):
                return False, responseData

            # is the checksum valid?
            if not HoymilesHmDtu.__CheckChecksum(response):
                return False, responseData
            
            # header is 10 bytes and last byte is the checksum
            responseData.extend(response[10:-1])

        return True, responseData

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
    def __GetInverterRadioAddress(inverterSerialNumber : str) -> bytes:
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
    def __GenerateDtuRadioAddress() -> bytes:
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
    def __CheckChecksum(packet : bytes | bytearray) -> bool:
        """ Checks the checksum of a packet.

        Args:
            packet (bytes | bytearray): The packet to be checked.

        Returns:
            bool: True if the checksum is valid.
        """
        checksum1 = HoymilesHmDtu.__CalculateCrc8(packet, len(packet) - 1)
        checksum2 = packet[-1]
        return checksum1 == checksum2

    @staticmethod
    def __EscapeData(input : bytes | bytearray) -> bytearray:
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

            if b == 0x7D:
                output.append(0x7D)
                output.append(0x5D)
            elif b == 0x7E:
                output.append(0x7D)
                output.append(0x5E)
            elif b == 0x7F:
                output.append(0x7D)
                output.append(0x5F)
            else:
                output.append(b)

        return output

    @staticmethod
    def __UnescapeData(input : bytes | bytearray) -> bytearray:
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
                b = input[idx]

                if b == 0x5D:
                    output.append(0x7D)
                elif b == 0x5E:
                    output.append(0x7E)
                elif b == 0x5F:
                    output.append(0x7F)
                else:
                    raise Exception("UnescapeData(): Invalid data, can not decode.")
            else:
                output.append(b)

            idx += 1

        return output

    @staticmethod
    def __CreateRequestInfoPacket(receiverAddr : bytes, senderAddr : bytes, currentTime : float) -> bytearray:
        """ Creates the packet that can be sent to the inverter to request information.

        Args:
            receiverAddr (bytes): The address of the receiver generated from the receiver (inverter) serial number. (4 bytes)
            senderAddr (bytes): The address of the sender generated from the sender (DTU) serial number. (4 bytes)
            currentTime (float): The current time in seconds since the start of the epoch.

        Returns:
            bytearray: The packet to be sent to the inverter.
        """
        # the header
        packet = HoymilesHmDtu.__CreatePacketHeader(0x15, receiverAddr, senderAddr, 0x80)

        # the payload
        payload = HoymilesHmDtu.__CreateRequestInfoPayload(currentTime)
        packet.extend(payload)

        # the payload checksum
        payloadChecksum = HoymilesHmDtu.__CalculateCrc16(payload, len(payload))
        packet.extend(payloadChecksum.to_bytes(2, "big", signed=False))

        # the packet checksum
        packetChecksum = HoymilesHmDtu.__CalculateCrc8(packet, len(packet))
        packet.extend(packetChecksum.to_bytes(1, "big", signed=False))

        if len(packet) != 27:
            raise Exception(f"Internal error CreateRequestInfoPacket: packet size {len(packet)} != 27")
        
        # replace special characters
        packet = HoymilesHmDtu.__EscapeData(packet)

        if len(packet) > HoymilesHmDtu.__MAX_PACKET_SIZE:
            raise Exception(f"Internal error CreateRequestInfoPacket: packet size {len(packet)} > MAX_PACKET_SIZE {HoymilesHmDtu.__MAX_PACKET_SIZE}")
        
        return packet

    @staticmethod
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
            raise Exception(f"Internal error __CreatePacketHeader: size {len(header)} != 10")
        
        return header

    @staticmethod
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
            raise Exception(f"Internal error __CreateRequestInfoPayload: size {len(payload)} != 14")
        
        return payload
    
    @staticmethod
    def __CalculateCrc8(data : bytes | bytearray, dataLen : int) -> int:
        """ Calculates CRC8 checksum for communication with hoymiles inverters.
            poly = 0x101; reversed = False; init-value = 0x00; XOR-out = 0x00; Check = 0x31

        Args:
            data (bytearray): The byte array on which the ckecksum is to be calculated.
            dataLen (int): Number of bytes to be used to calculate the checksum.

        Returns:
            int: The crc checksum.
        """
        crc = 0

        for idx in range(dataLen):
            crc ^= data[idx]
            for _ in range(8):
                crc <<= 1
                if crc & 0x0100:
                    crc ^= 0x01
                crc &= 0xFF

        return crc

    @staticmethod
    def __CalculateCrc16(data : bytes | bytearray, dataLen : int) -> int:
        """ Calculates CRC16 checksum for communication with hoymiles inverters.
            poly = 0x8005; reversed = True; init-value = 0xFFFF; XOR-out = 0x0000; Check = 0x4B37

        Args:
            data (bytearray): The byte array on which the ckecksum is to be calculated.
            dataLen (int): Number of bytes to be used to calculate the checksum.

        Returns:
            int: The crc checksum.
        """

        crc = 0xFFFF

        for idx in range(dataLen):
            crc ^= data[idx]
            for _ in range(8):
                if crc & 0x0001:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1

        return crc

###################################################################################################
# functions for debugging
###################################################################################################

if __name__ == "__main__":

    hm = HoymilesHmDtu("114184020874", 0, 24)
    hm.InitializeCommunication()
    success, info = hm.QueryInverterInfo()

    print(f"success: {success}")
    HoymilesHmDtu.PrintInverterInfo(info)

