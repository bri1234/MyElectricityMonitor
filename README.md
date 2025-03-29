# MyElectricityMonitor

My electricity monitor using two DD3 electricity meters and one HM-600 solar inverter.

# Hardware

Electricity meter:
2 x EbzDD3              (interface IR-UART)

Solar inverter:
1 x Hoymiles HM-600     (interface radio nRF24L01+)

## Switch for two electricity meters

This is the signal switch used two connect two electricity meters to one **UART**.

![Electricity meter signal switch circuit](TwoEnergyMetersSwitch.png)

## Electricity meter Raspberry PI pin connections

| RPI Pin | RPI Signal           | IR-Sensor (Switch)    |
| ------- | -------------------- | --------------------- |
| 2       | +5V                  | +5V                   |
| 6       | GND                  | GND                   |
| 10      | RXD, GPIO 15 (Input) | RX (Output)           |
| 11      | GPIO 17 (Output)     | Switch Select (Input) |

GPIO is used to switch between two electricity meters.

## Solar inverter nRF24L01+ Raspberry PI pin connections

| RPI Pin | RPI Signal              | nRF24 Pin | nRF24 Signal |
| ------- | ----------------------- | --------- | ------------ |
| 17      | +3.3V                   | 2         | +3.3V        |
| 18      | GPIO 24 (Output)        | 3         | CE (Input)   |
| 19      | MOSI, GPIO 10 (Output)  | 6         | MOSI         |
| 20      | GND                     | 1         | GND          |
| 21      | MISO, GPIO 9 (Input)    | 7         | MISO         |
| (22)    | GPIO 25 (Input)         | (8)       | IRQ          |
| 23      | SCLK, GPIO 11 (Output)  | 5         | SCLK         |
| 24      | CS0, GPIO 8 (Output)    | 4         | CSN          |

Connection from Raspberry PI pin 22 to nRF24L01+ IRQ pin 8 is not necessary!
nRF24L01+ CE pin 3 can be connected to an other Raspberry PI GPIO pin.

# Software

## Rapsberry PI enable UART for electricity meters

sudo raspi-config

"Interface Options" -> "Serial Port"

"Would you like a login shell to be accessible over serial?" -> "NO"

"Would you like the serial port hardware to be enabled?" -> "YES"

## Raspberry PI enable SPI for nRF24L01+

sudo raspi-config

"Interface Options" -> "SPI"

"Would you like the SPI interface to be enabled?" -> "YES"

## Raspberry PI Python GPIO module: gpiozero

sudo python3 -m pip install gpiozero

## Raspebrry PI Python module for nRF24L01+: pyrf24

This Python code needs the pyrf24 module for communication. Install the module with the following line:

python3 -m pip install pyrf24

(see https://github.com/nRF24/pyRF24)

## Raspberry PI Python GPIO module: pyserial

python3 -m pip install pyserial

# Infos

## eBZ DD3 supported infos

+A: Wirkenergie, Netz liefert an Kunden
-A: Wirkenergie, Kunde liefert an Netz

| Data type         | Name                          | Comment       |
|-------------------|-------------------------------|---------------|
| 81 81 C7 82 03 FF | Hersteller-Identifikation     | Hersteller-Kennung und Gerätetyp mit Software Version: /EBZ5DD3BZ06ETA_107 |
| 01 00 00 00 09 FF | Geräte-Identifikation         | Nach DIN 43863-5 z.B.: 1EBZ0100000024 |
| 01 00 01 08 00 FF | Zählerstand zu +A, tariflos   | Auflösung 10 μW*h (6 Vorkomma- und 8 Nachkommastellen) |
| 01 00 01 08 01 FF | Zählerstand zu +A, Tarif 1    | Auflösung 10 μW*h (6 Vorkomma- und 8 Nachkommastellen) |
| 01 00 01 08 02 FF | Zählerstand zu +A, Tarif 2    | Auflösung 10 μW*h (6 Vorkomma- und 8 Nachkommastellen) |
| 01 00 02 08 00 FF | Zählerstand zu -A, tariflos   | Auflösung 10 μW*h (6 Vorkomma- und 8 Nachkommastellen) | 
| 01 00 10 07 00 FF | Summe der Momentan-Leistungen in allen Phasen | Auflösung 0,01W (5 Vorkomma- und 2 Nachkommastellen) |
| 01 00 24 07 00 FF | Momentane Leistung in Phase L1 | Auflösung 0,01W (5 Vorkomma- und 2 Nachkommastellen) |
| 01 00 38 07 00 FF | Momentane Leistung in Phase L2 | Auflösung 0,01W (5 Vorkomma- und 2 Nachkommastellen) |
| 01 00 4C 07 00 FF | Momentane Leistung in Phase L3 | Auflösung 0,01W (5 Vorkomma- und 2 Nachkommastellen) |
