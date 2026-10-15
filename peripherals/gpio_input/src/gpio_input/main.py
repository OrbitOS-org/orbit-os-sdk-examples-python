"""GPIO input example: wait until an input pin reads high.

Set INPUT_PIN_NAME below to a pin of your board that is configured as an input.
"""
import argparse
import os
import signal
import sys
import time

import grpc

import metadata
from client import Client
from client.gpio_manager import GPIO_DIR_IN, GPIO_LEVEL_HIGH
from logger import Logger

LOG_TAG = "gpio_input"

# DEFAULT_HOST is only used in development, when the app runs on your computer
# and talks to a device in Developer Mode. On the device the SDK connects locally.
DEFAULT_HOST = "192.168.1.100"

# metadata.json is the app manifest. Orbit Studio reads the same file when it
# builds the .orb package.
MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.json")

# INPUT_PIN_NAME must match a name returned by list_pins.
INPUT_PIN_NAME = "GPIO24"
# POLL_INTERVAL is how often the pin level is read (seconds).
POLL_INTERVAL = 0.05


def main() -> int:
    parser = argparse.ArgumentParser(description="Wait for an input pin (GPIO24) to go high.")
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

    pin = next((p for p in gpio.list_pins() if p.name == INPUT_PIN_NAME), None)
    if pin is None:
        raise RuntimeError(f"pin {INPUT_PIN_NAME} not found on this device")

    # This example only reads. It does not change the direction of the pin.
    direction = gpio.get_direction(pin)
    if direction != GPIO_DIR_IN:
        raise RuntimeError(f"pin {INPUT_PIN_NAME} is not an input (direction={direction.name})")

    Logger.info(LOG_TAG, f"Waiting for {INPUT_PIN_NAME} to go high (Ctrl+C to stop)")
    try:
        while gpio.get_level(pin) != GPIO_LEVEL_HIGH:
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        Logger.info(LOG_TAG, f"Stopped before {INPUT_PIN_NAME} went high.")
        return
    Logger.info(LOG_TAG, f"{INPUT_PIN_NAME} is high.")


def error_text(e: Exception) -> str:
    """The message of an error from the SDK. Connection errors carry a status code."""
    if isinstance(e, grpc.RpcError):
        return f"{e.code().name}: {e.details()}"
    return str(e)


if __name__ == "__main__":
    sys.exit(main())
