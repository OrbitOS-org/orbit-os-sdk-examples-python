"""I2C example: list the I2C buses, open the first one, read its configuration
and scan it for devices.
"""
import argparse
import os
import sys

import grpc

import metadata
from client import Client
from logger import Logger

LOG_TAG = "i2c"

# DEFAULT_HOST is only used in development, when the app runs on your computer
# and talks to a device in Developer Mode. On the device the SDK connects locally.
DEFAULT_HOST = "192.168.1.100"

# metadata.json is the app manifest. Orbit Studio reads the same file when it
# builds the .orb package.
MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.json")

# CLOCK_HZ is the bus speed: 100000 is standard mode (100 kHz).
CLOCK_HZ = 100000
# TEN_BIT_ADDR selects 10-bit addressing. Most devices use 7-bit addresses.
TEN_BIT_ADDR = False
# CLOCK_STRETCHING lets a slow device hold the clock line while it gets ready.
CLOCK_STRETCHING = True


def main() -> int:
    parser = argparse.ArgumentParser(description="List the I2C buses, read the configuration and scan for devices.")
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help="Device IP address (development only; ignored when the app runs on the device)")
    args = parser.parse_args()

    app_manifest = metadata.must_parse_app_manifest_json(MANIFEST_PATH)
    meta = metadata.build(app_manifest)
    Logger.init(meta.name, "INFO", True)
    Logger.info(LOG_TAG, f"Starting {meta.name} v{meta.version}")
    app_manifest.print_info()

    try:
        client = Client.connect(args.host.strip())
    except FileNotFoundError as e:
        # Outside the device the SDK needs the development certificates, which
        # Orbit Studio puts in certs/grpc/ at the project root.
        Logger.fatal(LOG_TAG, f"Connect: certificate not found: {e}")
        return 1

    try:
        run(client)
    except (RuntimeError, grpc.RpcError) as e:
        Logger.fatal(LOG_TAG, error_text(e))
        return 1
    finally:
        client.close()
    Logger.info(LOG_TAG, "Done.")
    return 0


def run(client: Client) -> None:
    i2c = client.i2c_manager

    buses = i2c.list_buses()
    Logger.info(LOG_TAG, f"I2C buses: {buses}")
    if not buses:
        Logger.info(LOG_TAG, "No I2C bus on this device: nothing to do.")
        return

    bus_number = buses[0]
    Logger.info(LOG_TAG, f"Using bus {bus_number}")

    bus = i2c.open(bus_number, CLOCK_HZ, TEN_BIT_ADDR, CLOCK_STRETCHING)

    cfg = bus.get_config()
    Logger.info(LOG_TAG, f"Config: clockHz={cfg.clock_hz} tenBit={cfg.ten_bit_addr} "
                         f"clockStretching={cfg.clock_stretching}")

    addrs = bus.scan()
    if not addrs:
        Logger.info(LOG_TAG, f"No device answered on bus {bus_number}.")
        return
    Logger.info(LOG_TAG, f"{len(addrs)} device(s) on bus {bus_number}:")
    for addr in addrs:
        Logger.info(LOG_TAG, f"  address 0x{addr:02X}")

    # To read from a device, use one of the addresses found above. For example,
    # to read 1 byte from the device at 0x48:
    #
    #     data = bus.read(0x48, 1)


def error_text(e: Exception) -> str:
    """The message of an error from the SDK. Connection errors carry a status code."""
    if isinstance(e, grpc.RpcError):
        return f"{e.code().name}: {e.details()}"
    return str(e)


if __name__ == "__main__":
    sys.exit(main())
