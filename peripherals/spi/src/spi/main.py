"""SPI example: list the SPI devices, open one, read its configuration and run
a full-duplex transfer.

Set the constants below to match your wiring.
"""
import argparse
import os
import sys

import grpc

import metadata
from client import Client
from logger import Logger

LOG_TAG = "spi"

# DEFAULT_HOST is only used in development, when the app runs on your computer
# and talks to a device in Developer Mode. On the device the SDK connects locally.
DEFAULT_HOST = "192.168.1.100"

# metadata.json is the app manifest. Orbit Studio reads the same file when it
# builds the .orb package.
MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.json")

# SPI_BUS and SPI_CS select the device: bus 0, chip select 2 is "spidev0.2".
SPI_BUS = 0
SPI_CS = 2
# SPI_SPEED_HZ is the maximum clock speed.
SPI_SPEED_HZ = 10_000
# SPI_BITS_PER_WORD, SPI_MODE and SPI_LSB_FIRST set the frame format.
SPI_BITS_PER_WORD = 8
SPI_MODE = 0
SPI_LSB_FIRST = False
# SPI_LOOPBACK: with MOSI wired to MISO, set this to True to send a short
# pattern and check that the same bytes come back.
SPI_LOOPBACK = False


def main() -> int:
    parser = argparse.ArgumentParser(description="List the SPI devices, read the configuration and run a full-duplex transfer.")
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
    spi = client.spi_manager

    devices = spi.list_devices()
    Logger.info(LOG_TAG, f"SPI devices: {devices}")

    dev = spi.open(SPI_BUS, SPI_CS, SPI_SPEED_HZ, SPI_BITS_PER_WORD, SPI_MODE, SPI_LSB_FIRST)

    cfg = dev.get_config()
    Logger.info(LOG_TAG, f"Config spidev{SPI_BUS}.{SPI_CS}: speed={cfg.max_speed_hz} bits={cfg.bits_per_word} "
                         f"mode={cfg.mode} lsbFirst={cfg.lsb_first}")

    # SPI is full duplex: for every byte sent, one byte is received.
    tx = bytes([0xAB, 0xCD, 0x12, 0x34]) if SPI_LOOPBACK else bytes([0xD1, 0x00, 0x00, 0x01, 0xFF, 0xFF])

    rx = dev.transfer(tx, len(tx))
    Logger.info(LOG_TAG, f"TX {tx.hex()}")
    Logger.info(LOG_TAG, f"RX {rx.hex()}")

    if SPI_LOOPBACK and rx != tx:
        raise RuntimeError(f"loopback failed: sent {tx.hex()}, received {rx.hex()}")


def error_text(e: Exception) -> str:
    """The message of an error from the SDK. Connection errors carry a status code."""
    if isinstance(e, grpc.RpcError):
        return f"{e.code().name}: {e.details()}"
    return str(e)


if __name__ == "__main__":
    sys.exit(main())
