"""PWM fade example: fade the first PWM channel in and out, like a breathing
LED, until Ctrl+C. The output is stopped when the example ends.
"""
import argparse
import os
import signal
import sys
import time

import grpc

import metadata
from client import Client
from logger import Logger

LOG_TAG = "pwm_fade"

# DEFAULT_HOST is only used in development, when the app runs on your computer
# and talks to a device in Developer Mode. On the device the SDK connects locally.
DEFAULT_HOST = "192.168.1.100"

# metadata.json is the app manifest. Orbit Studio reads the same file when it
# builds the .orb package.
MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.json")

# FREQUENCY_HZ is the output frequency. 1 kHz is fast enough for an LED
# not to flicker.
FREQUENCY_HZ = 1000.0
# STEPS is the number of duty cycle levels between off and fully on.
STEPS = 50
# STEP_INTERVAL is the time spent on each level (seconds).
STEP_INTERVAL = 0.02


def main() -> int:
    parser = argparse.ArgumentParser(description="Raise and lower the duty cycle step by step, like an LED fading in and out, then stop the output.")
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
    pwm = client.pwm_manager

    channels = pwm.list_channels()
    if not channels:
        Logger.info(LOG_TAG, "No PWM channel on this device: nothing to do.")
        return

    channel = channels[0]
    Logger.info(LOG_TAG, f"Fading {channel.name!r} at {FREQUENCY_HZ:g} Hz. Ctrl+C to stop.")

    try:
        # step goes 0, 1, … STEPS, then back down to 0, and repeats.
        step, direction = 0, 1
        while True:
            pwm.set_pwm(channel, step / STEPS, FREQUENCY_HZ)

            if step == STEPS:
                direction = -1
            elif step == 0:
                direction = 1
            step += direction

            time.sleep(STEP_INTERVAL)
    finally:
        # Stop the output when done, so the channel is not left running.
        try:
            pwm.stop_pwm(channel)
        except (RuntimeError, grpc.RpcError) as e:
            Logger.error(LOG_TAG, f"stop_pwm: {error_text(e)}")


def error_text(e: Exception) -> str:
    """The message of an error from the SDK. Connection errors carry a status code."""
    if isinstance(e, grpc.RpcError):
        return f"{e.code().name}: {e.details()}"
    return str(e)


if __name__ == "__main__":
    sys.exit(main())
