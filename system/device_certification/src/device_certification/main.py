"""Device certification example: check whether the app runs on certified
hardware, with is_device_certified and get_serial_number (added in API 26.1).

Expected output on a certified device:

    IsDeviceCertified: True
    SerialNumber:      <certification serial>

Expected output on a community board (for example a Raspberry Pi):

    IsDeviceCertified: False
    SerialNumber:      (empty)
"""
import argparse
import os
import sys

import grpc

import metadata
from client import Client
from logger import Logger

LOG_TAG = "device_certification"

# DEFAULT_HOST is only used in development, when the app runs on your computer
# and talks to a device in Developer Mode. On the device the SDK connects locally.
DEFAULT_HOST = "192.168.1.100"

# metadata.json is the app manifest. Orbit Studio reads the same file when it
# builds the .orb package.
MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether the app runs on certified hardware and read the certification serial.")
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
    sys_mgr = client.system_manager

    # These calls need a device with API 26.1 or newer.
    api_ver, api_rev = sys_mgr.get_api_version()
    Logger.info(LOG_TAG, f"Device API version: {api_ver}.{api_rev}")

    Logger.info(LOG_TAG, "--- Device certification")

    certified = sys_mgr.is_device_certified()
    Logger.info(LOG_TAG, f"IsDeviceCertified: {certified}")

    # The certification serial is empty on a device that is not certified.
    serial = sys_mgr.get_serial_number()
    Logger.info(LOG_TAG, f"SerialNumber:      {serial or '(empty)'}")

    # Board information, for comparison. BoardSerial is the serial of the
    # hardware itself; it is not the certification serial.
    Logger.info(LOG_TAG, "--- Board information")
    Logger.info(LOG_TAG, f"BoardVendor:       {sys_mgr.get_board_vendor()}")
    Logger.info(LOG_TAG, f"BoardModel:        {sys_mgr.get_board_model()}")
    Logger.info(LOG_TAG, f"BoardSerial:       {sys_mgr.get_board_serial()}")

    if certified:
        Logger.info(LOG_TAG, f"This is a certified device (serial {serial}).")
    else:
        Logger.info(LOG_TAG, "This is a community board: it has no certification serial.")


def error_text(e: Exception) -> str:
    """The message of an error from the SDK. Connection errors carry a status code."""
    if isinstance(e, grpc.RpcError):
        return f"{e.code().name}: {e.details()}"
    return str(e)


if __name__ == "__main__":
    sys.exit(main())
