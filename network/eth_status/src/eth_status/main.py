"""Ethernet status example: list the Ethernet interfaces and print the link
state and IP configuration of each one.
"""
import argparse
import os
import sys

import grpc

import metadata
from client import Client
from logger import Logger

LOG_TAG = "eth_status"

# DEFAULT_HOST is only used in development, when the app runs on your computer
# and talks to a device in Developer Mode. On the device the SDK connects locally.
DEFAULT_HOST = "192.168.1.100"

# metadata.json is the app manifest. Orbit Studio reads the same file when it
# builds the .orb package.
MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="List the Ethernet interfaces with link state and IP configuration.")
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
    eth = client.ethernet_manager

    ifaces = eth.list_ethernet_interfaces()
    Logger.info(LOG_TAG, f"Ethernet interfaces: {len(ifaces)}")
    for i, iface in enumerate(ifaces):
        name = iface.interface_name

        # A failure on one interface should not hide the others.
        try:
            link_up = eth.is_ethernet_connected(name)
            props = eth.get_ethernet_link_properties(name)
        except (RuntimeError, grpc.RpcError) as e:
            Logger.error(LOG_TAG, f"  [{i}] {name!r}: {error_text(e)}")
            continue

        line = f"  [{i}] {name!r} linkUp={link_up} state={iface.state} mac={iface.mac_address!r}"
        if props is not None:
            line += (f" mtu={props.mtu} ipv4={props.ipv4_address!r} gw={props.ipv4_gateway!r}"
                     f" dns=[{','.join(props.ipv4_dns)}]")
        Logger.info(LOG_TAG, line)


def error_text(e: Exception) -> str:
    """The message of an error from the SDK. Connection errors carry a status code."""
    if isinstance(e, grpc.RpcError):
        return f"{e.code().name}: {e.details()}"
    return str(e)


if __name__ == "__main__":
    sys.exit(main())
