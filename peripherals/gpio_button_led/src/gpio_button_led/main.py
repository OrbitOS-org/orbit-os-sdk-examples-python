"""GPIO button and LED example: the LED is on while the button is pressed.

It reads an input pin and writes its level to an output pin, until Ctrl+C.
Set the two pin names below to match your wiring.
"""
import argparse
import os
import signal
import sys
import time

import grpc

import metadata
from client import Client
from client.gpio_manager import GPIO_DIR_IN, GPIO_DIR_OUT, GPIO_LEVEL_HIGH, GPIO_LEVEL_LOW
from logger import Logger

LOG_TAG = "gpio_button_led"

# DEFAULT_HOST is only used in development, when the app runs on your computer
# and talks to a device in Developer Mode. On the device the SDK connects locally.
DEFAULT_HOST = "192.168.1.100"

# metadata.json is the app manifest. Orbit Studio reads the same file when it
# builds the .orb package.
MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.json")

# BUTTON_PIN_NAME and LED_PIN_NAME must match names returned by list_pins.
BUTTON_PIN_NAME = "GPIO24"
LED_PIN_NAME = "GPIO23"
# POLL_INTERVAL is how often the button is read (seconds).
POLL_INTERVAL = 0.02


def main() -> int:
    parser = argparse.ArgumentParser(description="Read a button on an input pin and drive an LED on an output pin with it.")
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

    pins = {p.name: p for p in gpio.list_pins()}
    button, led = pins.get(BUTTON_PIN_NAME), pins.get(LED_PIN_NAME)
    if button is None:
        raise RuntimeError(f"pin {BUTTON_PIN_NAME} not found on this device")
    if led is None:
        raise RuntimeError(f"pin {LED_PIN_NAME} not found on this device")

    gpio.set_direction(button, GPIO_DIR_IN)
    gpio.set_direction(led, GPIO_DIR_OUT)

    Logger.info(LOG_TAG, f"{BUTTON_PIN_NAME} (button) drives {LED_PIN_NAME} (LED). Ctrl+C to stop.")
    try:
        # Write to the LED only when the button changes, not on every read.
        last = None
        while True:
            level = gpio.get_level(button)
            if level != last:
                gpio.set_level(led, level)
                if level == GPIO_LEVEL_HIGH:
                    Logger.info(LOG_TAG, "Button pressed: LED on")
                else:
                    Logger.info(LOG_TAG, "Button released: LED off")
                last = level
            time.sleep(POLL_INTERVAL)
    finally:
        # Whatever happens, leave the LED off.
        try:
            gpio.set_level(led, GPIO_LEVEL_LOW)
        except (RuntimeError, grpc.RpcError) as e:
            Logger.error(LOG_TAG, f"Turn the LED off on exit: {error_text(e)}")


def error_text(e: Exception) -> str:
    """The message of an error from the SDK. Connection errors carry a status code."""
    if isinstance(e, grpc.RpcError):
        return f"{e.code().name}: {e.details()}"
    return str(e)


if __name__ == "__main__":
    sys.exit(main())
