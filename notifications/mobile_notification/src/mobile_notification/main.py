"""Mobile notification example: send a push notification to the phones linked
to the device owner's Orbit OS account, with the mobile notification
manager's send (added in API 26.1).

The app only calls send. Orbit OS delivers the notification through the
Orbit OS Cloud Services; the app holds no cloud credentials.

What you get back depends on the device at the time of the run:
  - the device is not signed in to an Orbit OS account, or no phone is
    linked to that account: an error;
  - signed in, with at least one phone linked: sent is 1 or more.
"""
import argparse
import os
import sys

import grpc

import metadata
from client import Client
from logger import Logger

LOG_TAG = "mobile_notification"

# DEFAULT_HOST is only used in development, when the app runs on your computer
# and talks to a device in Developer Mode. On the device the SDK connects locally.
DEFAULT_HOST = "192.168.1.100"

# metadata.json is the app manifest. Orbit Studio reads the same file when it
# builds the .orb package.
MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.json")

# NOTIFICATION_BODY is the text shown in the notification.
NOTIFICATION_BODY = "Device status changed"


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a push notification to the phones linked to the device owner's account.")
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
    # There is no title parameter. Orbit OS always sets the title to
    # "<device name> · <this app's name>", taken from the app's identity, so
    # one app cannot send a notification that looks like it came from another.
    #
    # The optional fields are keyword arguments. For example, to attach data
    # for the mobile app and replace an earlier notification:
    #
    #     send(NOTIFICATION_BODY, data={"screen": "status"}, collapse_key="status")
    sent, failed = client.mobile_notification_manager.send(NOTIFICATION_BODY)

    # sent and failed count the phones the notification was sent to.
    Logger.info(LOG_TAG, f"Notification sent: sent={sent} failed={failed}")


def error_text(e: Exception) -> str:
    """The message of an error from the SDK. Connection errors carry a status code."""
    if isinstance(e, grpc.RpcError):
        return f"{e.code().name}: {e.details()}"
    return str(e)


if __name__ == "__main__":
    sys.exit(main())
