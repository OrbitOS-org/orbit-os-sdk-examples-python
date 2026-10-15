"""WiFi scan example: list the WiFi interfaces, then scan for networks on the
first one.
"""
import argparse
import os
import sys

import grpc

import metadata
from client import Client
from logger import Logger

LOG_TAG = "wifi_scan"

# DEFAULT_HOST is only used in development, when the app runs on your computer
# and talks to a device in Developer Mode. On the device the SDK connects locally.
DEFAULT_HOST = "192.168.1.100"

# metadata.json is the app manifest. Orbit Studio reads the same file when it
# builds the .orb package.
MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="List the WiFi interfaces and scan for networks.")
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
    wifi = client.wifi_manager

    ifaces = wifi.list_interfaces()
    Logger.info(LOG_TAG, f"WiFi interfaces: {len(ifaces)}")
    for i, iface in enumerate(ifaces):
        Logger.info(LOG_TAG, f"  [{i}] name={iface.interface_name!r} mac={iface.mac_address!r} state={iface.state}")
    if not ifaces:
        Logger.info(LOG_TAG, "No WiFi interface on this device: nothing to scan.")
        return

    ifname = ifaces[0].interface_name
    Logger.info(LOG_TAG, f"Scanning on {ifname!r}")

    networks = wifi.scan(ifname)
    Logger.info(LOG_TAG, f"Networks found: {len(networks)}")
    for i, n in enumerate(networks):
        Logger.info(LOG_TAG, f"  [{i}] ssid={n.ssid!r} security={n.security!r} rssi={n.signal_strength} "
                             f"ch={n.channel} band={n.band!r}")


def error_text(e: Exception) -> str:
    """The message of an error from the SDK. Connection errors carry a status code."""
    if isinstance(e, grpc.RpcError):
        return f"{e.code().name}: {e.details()}"
    return str(e)


if __name__ == "__main__":
    sys.exit(main())
