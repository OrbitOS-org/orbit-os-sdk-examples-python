"""System metrics example: read one snapshot of the device metrics — CPU,
memory, disk and temperature — with the system manager's get_metrics.
"""
import argparse
import os
import sys

import grpc

import metadata
from client import Client
from logger import Logger

LOG_TAG = "metrics_info"

# DEFAULT_HOST is only used in development, when the app runs on your computer
# and talks to a device in Developer Mode. On the device the SDK connects locally.
DEFAULT_HOST = "192.168.1.100"

# metadata.json is the app manifest. Orbit Studio reads the same file when it
# builds the .orb package.
MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read one snapshot of CPU, memory, disk and temperature metrics.")
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
    resp = client.system_manager.get_metrics()
    if not resp.HasField("metrics"):
        Logger.info(LOG_TAG, "The device returned no metrics.")
        return
    m = resp.metrics

    # CPU: overall usage, then one value per core.
    cores = " ".join(f"{v:.2f}" for v in m.cpu_core_percent)
    Logger.info(LOG_TAG, f"cpu: usage={m.cpu_usage:.1f}% cores=[{cores}]")

    Logger.info(LOG_TAG, f"memory: usage={m.memory_usage:.1f}%")

    # Disk usage comes as a map of mount point to usage. Sort the mount
    # points so the output is the same on every run.
    for path in sorted(m.disk_usage):
        Logger.info(LOG_TAG, f"disk {path}: usage={m.disk_usage[path].percent:.1f}%")

    Logger.info(LOG_TAG, f"thermal: soc={m.soc_thermal:.1f}°C sensors={m.sensors_temperatures}°C")


def error_text(e: Exception) -> str:
    """The message of an error from the SDK. Connection errors carry a status code."""
    if isinstance(e, grpc.RpcError):
        return f"{e.code().name}: {e.details()}"
    return str(e)


if __name__ == "__main__":
    sys.exit(main())
