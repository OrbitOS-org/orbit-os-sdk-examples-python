"""PWM example: list the PWM channels, set the first one to a fixed frequency
and duty cycle, then read the settings back.

The channel keeps running with these settings after the example ends.
"""
import argparse
import os
import sys

import grpc

import metadata
from client import Client
from logger import Logger

LOG_TAG = "pwm"

# DEFAULT_HOST is only used in development, when the app runs on your computer
# and talks to a device in Developer Mode. On the device the SDK connects locally.
DEFAULT_HOST = "192.168.1.100"

# metadata.json is the app manifest. Orbit Studio reads the same file when it
# builds the .orb package.
MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.json")

# DUTY_CYCLE is the fraction of each period the output stays high (0.5 = 50%).
DUTY_CYCLE = 0.5
# FREQUENCY_HZ is the output frequency.
FREQUENCY_HZ = 10.0


def main() -> int:
    parser = argparse.ArgumentParser(description="List the PWM channels and set frequency and duty cycle on the first one.")
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
    pwm = client.pwm_manager

    channels = pwm.list_channels()
    Logger.info(LOG_TAG, f"PWM channels: {len(channels)}")
    for i, ch in enumerate(channels):
        Logger.info(LOG_TAG, f"  [{i}] name={ch.name!r} channel={ch.channel}")
    if not channels:
        Logger.info(LOG_TAG, "No PWM channel on this device: nothing to configure.")
        return

    channel = channels[0]
    Logger.info(LOG_TAG, f"Setting {channel.name!r} to duty={DUTY_CYCLE * 100:.0f}% frequency={FREQUENCY_HZ:g} Hz")
    pwm.set_pwm(channel, DUTY_CYCLE, FREQUENCY_HZ)

    # Read the settings back to confirm what the device applied.
    props = pwm.get_properties(channel)
    Logger.info(LOG_TAG, f"Read back: enabled={props.enabled} duty={props.duty_cycle:.3f} "
                         f"frequency={props.frequency_hz:.3f} Hz")


def error_text(e: Exception) -> str:
    """The message of an error from the SDK. Connection errors carry a status code."""
    if isinstance(e, grpc.RpcError):
        return f"{e.code().name}: {e.details()}"
    return str(e)


if __name__ == "__main__":
    sys.exit(main())
