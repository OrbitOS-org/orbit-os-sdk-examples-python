"""Basic example: connect to the device and read system information —
API version, device identity, hardware, software versions and live metrics.

Every value comes from the system manager. The table in run lists each getter
by name, so the source doubles as a map of what the system service offers.
"""
import argparse
import os
import sys

import grpc

import metadata
from client import Client
from logger import Logger

LOG_TAG = "basic"

# DEFAULT_HOST is only used in development, when the app runs on your computer
# and talks to a device in Developer Mode. On the device the SDK connects locally.
DEFAULT_HOST = "192.168.1.100"

# metadata.json is the app manifest. Orbit Studio reads the same file when it
# builds the .orb package.
MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="Connect to the device and read system information: API version, device identity, hardware, OS.")
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

    # The API version belongs to the device. It is not the version of the SDK
    # this app was built with.
    api_ver, api_rev = sys_mgr.get_api_version()
    Logger.info(LOG_TAG, f"Device API version: {api_ver}.{api_rev}")

    sections = [
        ("Device identity", [
            ("DeviceName", sys_mgr.get_device_name),
            ("SocModel", sys_mgr.get_soc_model),
            ("SocVendor", sys_mgr.get_soc_vendor),
            ("BoardModel", sys_mgr.get_board_model),
            ("BoardVendor", sys_mgr.get_board_vendor),
            ("HardwareModel", sys_mgr.get_hardware_model),
            ("HardwareVersion", sys_mgr.get_hardware_version),
            ("SystemUuid", sys_mgr.get_system_uuid),
            ("BoardSerial", sys_mgr.get_board_serial),
            ("CpuSerial", sys_mgr.get_cpu_serial),
            ("MachineId", sys_mgr.get_machine_id),
            ("Architecture", sys_mgr.get_architecture),
            ("CpuModel", sys_mgr.get_cpu_model),
        ]),
        ("Software", [
            ("OsName", sys_mgr.get_os_name),
            ("OsVersion", sys_mgr.get_os_version),
            ("OsRevision", sys_mgr.get_os_revision),
            ("KernelVersion", sys_mgr.get_kernel_version),
            ("Distro", sys_mgr.get_distro),
            ("DistroVersion", sys_mgr.get_distro_version),
            ("RuntimeVersion", sys_mgr.get_runtime_version),
            ("RuntimeBuildDate", sys_mgr.get_runtime_build_date),
        ]),
        ("CPU and memory", [
            ("TotalRAM", sys_mgr.get_total_ram),
            ("CpuCores", sys_mgr.get_cpu_cores),
            ("CpuThreads", sys_mgr.get_cpu_threads),
            ("CpuMinMhz", lambda: f"{sys_mgr.get_cpu_min_mhz():.1f}"),
            ("CpuMaxMhz", lambda: f"{sys_mgr.get_cpu_max_mhz():.1f}"),
        ]),
    ]
    for title, fields in sections:
        Logger.info(LOG_TAG, f"--- {title}")
        for name, get in fields:
            Logger.info(LOG_TAG, f"{name + ':':<17} {get()}")

    # One snapshot of the live metrics. The metrics_info example shows more.
    Logger.info(LOG_TAG, "--- Metrics")

    resp = sys_mgr.get_metrics()
    if not resp.HasField("metrics"):
        Logger.info(LOG_TAG, "The device returned no metrics.")
        return
    m = resp.metrics
    Logger.info(LOG_TAG, f"{'CpuUsage:':<17} {m.cpu_usage:.1f}%")
    Logger.info(LOG_TAG, f"{'MemoryUsage:':<17} {m.memory_usage:.1f}%")
    Logger.info(LOG_TAG, f"{'SocThermal:':<17} {m.soc_thermal:.1f}°C")
    Logger.info(LOG_TAG, f"{'SensorsTemp:':<17} {m.sensors_temperatures}°C")
    if m.HasField("network"):
        Logger.info(LOG_TAG, f"{'Network RxBytes:':<17} {m.network.bytes_recv}")
        Logger.info(LOG_TAG, f"{'Network TxBytes:':<17} {m.network.bytes_sent}")


def error_text(e: Exception) -> str:
    """The message of an error from the SDK. Connection errors carry a status code."""
    if isinstance(e, grpc.RpcError):
        return f"{e.code().name}: {e.details()}"
    return str(e)


if __name__ == "__main__":
    sys.exit(main())
