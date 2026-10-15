"""Camera snapshot example: list the cameras, lock the first one, take one
picture, save it to a file and release the camera.

On the device the file is written to the app's data folder, which is the
working directory of the app.
"""
import argparse
import os
import sys

import grpc

import metadata
from client import Client, set_rpc_timeout
from logger import Logger

LOG_TAG = "camera_snapshot"

# DEFAULT_HOST is only used in development, when the app runs on your computer
# and talks to a device in Developer Mode. On the device the SDK connects locally.
DEFAULT_HOST = "192.168.1.100"

# metadata.json is the app manifest. Orbit Studio reads the same file when it
# builds the .orb package.
MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.json")

# CAPTURE_WIDTH, CAPTURE_HEIGHT and CAPTURE_FORMAT describe the picture to
# take. The camera must support them: see the formats and resolutions the
# example prints for each camera.
CAPTURE_WIDTH = 640
CAPTURE_HEIGHT = 480
CAPTURE_FORMAT = "mjpeg"
# OUTPUT_FILE is where the picture is saved. An MJPEG frame is a JPEG image.
OUTPUT_FILE = "snapshot.jpg"
# CALL_TIMEOUT is the longest each camera call may take (seconds).
CALL_TIMEOUT = 15


def main() -> int:
    parser = argparse.ArgumentParser(description="List the cameras, take one picture with the first one and save it to a file.")
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
    camera = client.camera_manager

    # Listing the cameras and capturing can take longer than the SDK default.
    set_rpc_timeout(CALL_TIMEOUT)

    devices = camera.list_devices()
    Logger.info(LOG_TAG, f"Cameras: {len(devices)}")
    for i, d in enumerate(devices):
        Logger.info(LOG_TAG, f"  [{i}] id={d.device_id!r} card={d.card!r} driver={d.driver!r} "
                             f"formats={d.supported_formats} resolutions={d.resolutions}")
    if not devices:
        Logger.info(LOG_TAG, "No camera on this device: nothing to capture.")
        return

    # Only one app can hold a camera at a time. Lock it, use it, unlock it.
    device_id = devices[0].device_id
    if not camera.lock_camera(device_id, LOG_TAG):
        raise RuntimeError(f"lock {device_id}: the camera is in use")
    try:
        Logger.info(LOG_TAG, f"Capturing {CAPTURE_WIDTH}x{CAPTURE_HEIGHT} {CAPTURE_FORMAT} from {device_id}")
        image = camera.capture_image(device_id, CAPTURE_WIDTH, CAPTURE_HEIGHT, CAPTURE_FORMAT)
        if not image.image_data:
            raise RuntimeError("the camera returned an empty image")

        with open(OUTPUT_FILE, "wb") as f:
            f.write(image.image_data)
        Logger.info(LOG_TAG, f"Saved {OUTPUT_FILE} ({len(image.image_data)} bytes, format {image.format})")
    finally:
        try:
            camera.unlock_camera(device_id, LOG_TAG)
        except grpc.RpcError as e:
            Logger.error(LOG_TAG, f"Unlock: {error_text(e)}")


def error_text(e: Exception) -> str:
    """The message of an error from the SDK. Connection errors carry a status code."""
    if isinstance(e, grpc.RpcError):
        return f"{e.code().name}: {e.details()}"
    return str(e)


if __name__ == "__main__":
    sys.exit(main())
