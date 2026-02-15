# Wiring a Heltec V3 to a Raspberry Pi

This guide covers connecting a Heltec WiFi LoRa 32 V3 running MeshCore repeater bridge firmware to a Raspberry Pi via UART for use with meshcore-net-bridge.

## Pin Connections

The MeshCore RS232 bridge firmware on the Heltec V3 uses **Serial2** with the following pins:

| Heltec V3 | Direction | Raspberry Pi         |
|-----------|-----------|----------------------|
| GPIO 6 (TX) | -->    | GPIO 15 / Pin 10 (RX) |
| GPIO 5 (RX) | <--    | GPIO 14 / Pin 8 (TX)  |
| GND        | ---      | GND / Pin 6           |
| 5V         | <--      | 5V / Pin 4 (optional) |

**Important:**
- TX connects to RX and vice versa (crossover). Both the ESP32-S3 and the Pi use 3.3V logic levels on their UART pins, so they are directly compatible without a level shifter.
- The Heltec can optionally be powered from the Pi's 5V pin. If doing this, do **not** also connect the Heltec to the Pi via USB — feeding 5V into both the header pin and USB simultaneously can damage either board.

### Heltec V3 Header

GPIO 5 and GPIO 6 are on the **left** side of the board, near the top (screen facing forward with the USB port at the bottom and IPEX connector at top). Refer to the [Heltec V3 pin diagram](http://community.heltec.cn/uploads/default/original/2X/1/1c9f2df23e5cb1e6886c9c6280af8af9546a760a.jpeg) for the full pinout.

```
        Heltec V3 (USB port down, IPEX connector up)

          Left            Right
        +------+---------+------+
 GP7    |      |         |      |  GP19
 GP6 <--|  TX  |         |      |  GP20
 GP5 <--|  RX  |         |      |  GP21
 GP4    |      |         |      |  GP26
  ...   |      |         |      |  ...
 3V3    |      |         |      |  Ve
 3V3    |      |         |  5V  |-->  5V
 GND <--|  GND |         |      |  GND
        +------+---------+------+
               |   USB   |
               +---------+
```

### Raspberry Pi GPIO Header

```
        Pi Header (USB ports at bottom)

                +------+------+
        3.3V  1 |      |      | 2  5V
      GPIO 2  3 |      |      | 4  5V  --> to Heltec 5V (optional)
      GPIO 3  5 |      |      | 6  GND  <-- GND
      GPIO 4  7 |      |      | 8  GPIO 14 (TX)  --> to Heltec RX
        GND   9 |      |      | 10 GPIO 15 (RX)  <-- from Heltec TX
              ...
                +------+------+
```

## Raspberry Pi UART Configuration

The Raspberry Pi 3 maps its full PL011 UART (`/dev/ttyAMA0`) to the Bluetooth module by default, leaving only the less reliable mini-UART on the GPIO header. For a stable serial connection, reconfigure the Pi to put PL011 back on the GPIO pins.

### 1. Disable the serial console

The Pi uses the UART as a login console by default. Disable it:

```bash
sudo raspi-config
```

Navigate to **Interface Options > Serial Port**:
- "Would you like a login shell to be accessible over serial?" --> **No**
- "Would you like the serial port hardware to be enabled?" --> **Yes**

### 2. Swap UART to PL011

Add the following to `/boot/firmware/config.txt` (or `/boot/config.txt` on older OS images):

```ini
dtoverlay=miniuart-bt
```

This moves Bluetooth to the mini-UART and assigns the reliable PL011 UART to GPIO 14/15 as `/dev/ttyAMA0`.

Alternatively, to disable Bluetooth entirely:

```ini
dtoverlay=disable-bt
```

If disabling Bluetooth, also stop the modem service:

```bash
sudo systemctl disable hciuart
```

### 3. Reboot

```bash
sudo reboot
```

### 4. Verify

After rebooting, confirm the serial port is available:

```bash
ls -l /dev/ttyAMA0
```

## MeshCore Firmware

Flash the Heltec V3 with the `Heltec_v3_repeater_bridge_rs232` firmware variant from [MeshCore](https://github.com/meshcore-dev/MeshCore). This enables the RS232 bridge on Serial2 at 115200 baud.

## Bridge Configuration

In your `config.yaml`, point the serial port to `/dev/ttyAMA0`:

```yaml
serial:
  port: "/dev/ttyAMA0"
  baud: 115200
```
