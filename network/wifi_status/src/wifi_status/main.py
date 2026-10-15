"""WiFi status example: for each WiFi interface, show whether it is connected,
its mode, and the details of the connection (client mode) or of the access
point (AP mode).

The example only reads. It does not change the WiFi configuration.
"""
import argparse
import os
import sys

import grpc

import metadata
from client import Client
from client.wifi_manager import WiFiMode
from logger import Logger

LOG_TAG = "wifi_status"

# DEFAULT_HOST is only used in development, when the app runs on your computer
# and talks to a device in Developer Mode. On the device the SDK connects locally.
DEFAULT_HOST = "192.168.1.100"

# metadata.json is the app manifest. Orbit Studio reads the same file when it
# builds the .orb package.
MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="Show, for each WiFi interface, whether it is connected, its mode and the details of the connection or access point.")
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
    if not ifaces:
        Logger.info(LOG_TAG, "No WiFi interface on this device.")
        return

    for iface in ifaces:
        name = iface.interface_name
        Logger.info(LOG_TAG, f"--- {name}")

        connected = wifi.is_connected(name)
        link = wifi.get_link_properties(name)
        mode = link.mode if link is not None else WiFiMode.UNKNOWN
        Logger.info(LOG_TAG, f"connected={connected} mode={mode.name} state={iface.state} mac={iface.mac_address!r}")

        # Read the details of the mode the interface is in: client properties
        # when it joined a network, AP properties when it is an access point.
        if mode in (WiFiMode.CLIENT, WiFiMode.AP_CLIENT):
            c = wifi.get_client_properties(name)
            if c is not None:
                Logger.info(LOG_TAG, f"client: ssid={c.ssid!r} security={c.security!r} rssi={c.signal_strength}")
                Logger.info(LOG_TAG, f"client: ipv4={c.ipv4_address!r} gw={c.ipv4_gateway!r} "
                                     f"dns=[{','.join(c.ipv4_dns)}]")
        if mode in (WiFiMode.AP, WiFiMode.AP_CLIENT):
            ap = wifi.get_ap_properties(name)
            if ap is not None:
                Logger.info(LOG_TAG, f"access point: ssid={ap.ssid!r} security={ap.security!r} "
                                     f"ipv4={ap.ipv4_address!r} ch={ap.channel} band={ap.band!r} "
                                     f"hidden={ap.hidden} active={ap.active} clients={ap.connected_clients}")


def error_text(e: Exception) -> str:
    """The message of an error from the SDK. Connection errors carry a status code."""
    if isinstance(e, grpc.RpcError):
        return f"{e.code().name}: {e.details()}"
    return str(e)


if __name__ == "__main__":
    sys.exit(main())
