
Hoymiles HM-600 hex response for command 0x15 (REQUEST INFO)
------------------------------------------------------------

Answer 0x95 = Command 0x15 | 0x80

Receiver address  = created from serial number
Sender address    = created from serial number

Frame | 0x80 = last frame

Frame 1:
Command | Receiver Address | Sender address | Frame | Payload                                         | Packet CRC8
95      | 84 02 08 74      | 84 02 08 74    | 01    | 00 01 01 15 00 08 00 16 01 16 00 08 00 16 00 09 | 9f

Frame 2:
Command | Receiver Address | Sender address | Frame | Payload                                         | Packet CRC8
95      | 84 02 08 74      | 84 02 08 74    | 02    | 99 38 00 09 ca f1 00 c7 00 ce 09 28 13 86 00 2a | 93

Frame 3 (last frame):
Command | Receiver Address | Sender address | Frame | Payload                       | Payload CRC16 | Packet CRC8
95      | 84 02 08 74      | 84 02 08 74    | 83    | 00 00 00 02 03 e9 00 25 00 18 | ea b5         | 9c

