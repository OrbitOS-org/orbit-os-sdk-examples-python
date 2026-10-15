"""Notification options example: send a push notification with the optional
fields of the mobile notification manager's send (added in API 26.1).

See the mobile_notification example first: it sends the simplest
notification and explains what the result means.
"""
import argparse
import os
import sys

import grpc

import metadata
from client import Client
from logger import Logger

LOG_TAG = "notification_options"

# DEFAULT_HOST is only used in development, when the app runs on your computer
# and talks to a device in Developer Mode. On the device the SDK connects locally.
DEFAULT_HOST = "192.168.1.100"

# metadata.json is the app manifest. Orbit Studio reads the same file when it
# builds the .orb package.
MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.json")

# NOTIFICATION_BODY is the text shown in the notification.
NOTIFICATION_BODY = "Water tank level is low"
# COLLAPSE_KEY groups notifications: a new one replaces an earlier one with
# the same key that the phone has not shown yet.
COLLAPSE_KEY = "tank-level"
# TTL_SECONDS is how long the notification is kept for a phone that is
# offline. After that it is dropped.
TTL_SECONDS = 3600


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a push notification with the optional fields: data for the mobile app, a collapse key and a time to live.")
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
    sent, failed = client.mobile_notification_manager.send(
        NOTIFICATION_BODY,
        # data is delivered to the mobile app with the notification, for
        # example to open a specific screen. It is not shown to the user.
        data={
            "screen": "tank",
            "level": "12",
        },
        collapse_key=COLLAPSE_KEY,
        ttl_seconds=TTL_SECONDS,
    )

    # sent and failed count the phones the notification was sent to.
    Logger.info(LOG_TAG, f"Notification sent: sent={sent} failed={failed}")


def error_text(e: Exception) -> str:
    """The message of an error from the SDK. Connection errors carry a status code."""
    if isinstance(e, grpc.RpcError):
        return f"{e.code().name}: {e.details()}"
    return str(e)


if __name__ == "__main__":
    sys.exit(main())
