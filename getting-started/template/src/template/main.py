"""Template: the smallest useful Orbit OS app. It connects to the device and
reads one value.

To start your own app: copy this project folder, rename it and src/template,
update orbit.project.json and metadata.json, then replace the body of run
with your own code.
"""
import argparse
import os
import sys

import grpc

import metadata
from client import Client
from logger import Logger

LOG_TAG = "template"

# DEFAULT_HOST is only used in development, when the app runs on your computer
# and talks to a device in Developer Mode. On the device the SDK connects locally.
DEFAULT_HOST = "192.168.1.100"

# metadata.json is the app manifest. Orbit Studio reads the same file when it
# builds the .orb package.
MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="Orbit OS Python SDK template app.")
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
    """The app logic. Raise an exception to stop the app with exit code 1."""
    model = client.system_manager.get_hardware_model()
    Logger.info(LOG_TAG, f"Hardware model: {model}")

    # Add your code here. To call another service, add it to "permissions"
    # in metadata.json first: Orbit OS refuses calls to services that are
    # not listed there.


def error_text(e: Exception) -> str:
    """The message of an error from the SDK. Connection errors carry a status code."""
    if isinstance(e, grpc.RpcError):
        return f"{e.code().name}: {e.details()}"
    return str(e)


if __name__ == "__main__":
    sys.exit(main())
