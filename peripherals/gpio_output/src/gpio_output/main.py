"""GPIO output example: list the GPIO lines of the device, then blink the
first one.

Check which line comes first on your board before you wire anything to it.
"""
import argparse
import os
import signal
import sys
import time

import grpc

import metadata
from client import Client
from client.gpio_manager import GPIO_DIR_OUT, GPIO_LEVEL_HIGH, GPIO_LEVEL_LOW
from logger import Logger

LOG_TAG = "gpio_output"

# DEFAULT_HOST is only used in development, when the app runs on your computer
# and talks to a device in Developer Mode. On the device the SDK connects locally.
DEFAULT_HOST = "192.168.1.100"

# metadata.json is the app manifest. Orbit Studio reads the same file when it
# builds the .orb package.
MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.json")

# BLINK_PHASE is how long the line stays high, and then low, in each cycle (seconds).
BLINK_PHASE = 0.5
# BLINK_CYCLES is the number of high-then-low cycles.
BLINK_CYCLES = 20


def main() -> int:
    parser = argparse.ArgumentParser(description="List the GPIO lines and blink the first one.")
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help="Device IP address (development only; ignored when the app runs on the device)")
    args = parser.parse_args()

    app_manifest = metadata.must_parse_app_manifest_json(MANIFEST_PATH)
    meta = metadata.build(app_manifest)
    Logger.init(meta.name, "INFO", True)
    Logger.info(LOG_TAG, f"Starting {meta.name} v{meta.version}")
    app_manifest.print_info()

    # Stop cleanly on Ctrl+C, and on SIGTERM, which Orbit OS sends to stop an
    # app: both raise KeyboardInterrupt, which ends run.
    signal.signal(signal.SIGTERM, signal.default_int_handler)

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
    except KeyboardInterrupt:
        pass  # asked to stop: run has cleaned up
    finally:
        client.close()
    Logger.info(LOG_TAG, "Done.")
    return 0


def run(client: Client) -> None:
    gpio = client.gpio_manager

    pins = gpio.list_pins()
    Logger.info(LOG_TAG, f"GPIO lines: {len(pins)}")
    for i, p in enumerate(pins):
        Logger.info(LOG_TAG, f"  [{i}] name={p.name!r} gpiochip={p.chip_number} line={p.number}")
    if not pins:
        Logger.info(LOG_TAG, "No GPIO line on this device: nothing to blink.")
        return

    pin = pins[0]
    Logger.info(LOG_TAG, f"Blinking {pin.name!r} (gpiochip={pin.chip_number} line={pin.number})")

    gpio.set_direction(pin, GPIO_DIR_OUT)
    try:
        for cycle in range(1, BLINK_CYCLES + 1):
            gpio.set_level(pin, GPIO_LEVEL_HIGH)
            Logger.info(LOG_TAG, f"  cycle {cycle}/{BLINK_CYCLES} high")
            time.sleep(BLINK_PHASE)

            gpio.set_level(pin, GPIO_LEVEL_LOW)
            Logger.info(LOG_TAG, f"  cycle {cycle}/{BLINK_CYCLES} low")
            time.sleep(BLINK_PHASE)
    finally:
        # Whatever happens, leave the line low.
        try:
            gpio.set_level(pin, GPIO_LEVEL_LOW)
        except (RuntimeError, grpc.RpcError) as e:
            Logger.error(LOG_TAG, f"Set the line low on exit: {error_text(e)}")


def error_text(e: Exception) -> str:
    """The message of an error from the SDK. Connection errors carry a status code."""
    if isinstance(e, grpc.RpcError):
        return f"{e.code().name}: {e.details()}"
    return str(e)


if __name__ == "__main__":
    sys.exit(main())
