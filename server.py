
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8000"))

LANES = {
    "north": "North",
    "south": "South",
    "east": "East",
    "west": "West"
}

VEHICLE_TYPES = {
    "car": 1,
    "bus": 2,
    "bike": 3
}

engine = None
engine_lock = threading.Lock()


def start_engine():
    global engine

    executable = BASE_DIR / "main"

    if not executable.is_file():
        raise FileNotFoundError(
            f"C engine not found: {executable}"
        )

    engine = subprocess.Popen(
        [str(executable), "server"],
        cwd=str(BASE_DIR),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None,
        text=True,
        encoding="utf-8",
        bufsize=1
    )

    if engine.poll() is not None:
        raise RuntimeError("C engine exited during startup.")


def send_to_engine(command):
    with engine_lock:
        if engine is None or engine.poll() is not None:
            raise RuntimeError("C engine is not running.")

        engine.stdin.write(command + "\n")
        engine.stdin.flush()

        response = engine.stdout.readline()

        if not response:
            raise RuntimeError(
                "C engine returned no response. "
                "Check that main.c supports server mode."
            )

        try:
            return json.loads(response)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "C engine did not return valid JSON: "
                + response[:200]
            ) from exc


def normalize_lane(value):
    if not isinstance(value, str):
        raise ValueError(
            "Select a lane: North, South, East, or West."
        )

    lane = LANES.get(value.strip().lower())

    if lane is None:
        raise ValueError(
            "Lane must be North, South, East, or West."
        )

    return lane


def send_json(handler, data, status=200):
    body = json.dumps(data).encode("utf-8")

    handler.send_response(status)
    handler.send_header(
        "Content-Type",
        "application/json; charset=utf-8"
    )
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


class TrafficFlowHandler(BaseHTTPRequestHandler):

    def log_message(self, format_string, *args):
        print(
            "[TrafficFlow] " + format_string % args,
            flush=True
        )

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/api/status":
            try:
                send_json(self, send_to_engine("STATUS"))
            except Exception as exc:
                print(str(exc), file=sys.stderr, flush=True)
                send_json(
                    self,
                    {"success": False, "error": str(exc)},
                    500
                )
            return

        files = {
            "/": "index.html",
            "/index.html": "index.html",
            "/style.css": "style.css",
            "/script.js": "script.js"
        }

        filename = files.get(path)

        if filename is None:
            send_json(
                self,
                {"success": False, "error": "Page not found."},
                404
            )
            return

        file_path = BASE_DIR / filename

        if not file_path.is_file():
            send_json(
                self,
                {"success": False, "error": "Website file missing."},
                404
            )
            return

        content = file_path.read_bytes()

        content_type = (
            "text/html; charset=utf-8"
            if filename.endswith(".html")
            else "text/css; charset=utf-8"
            if filename.endswith(".css")
            else "application/javascript; charset=utf-8"
        )

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        path = urlparse(self.path).path

        try:
            length = int(self.headers.get("Content-Length", "0"))

            if length <= 0 or length > 1000000:
                raise ValueError("Invalid request body.")

            data = json.loads(
                self.rfile.read(length).decode("utf-8")
            )

            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object.")

            if path == "/api/add":
                lane = normalize_lane(data.get("lane"))

                try:
                    vehicle_id = int(data.get("id"))
                except (ValueError, TypeError):
                    raise ValueError(
                        "Vehicle ID must be an integer."
                    )

                vehicle_type = data.get("type")

                if vehicle_id <= 0:
                    raise ValueError(
                        "Vehicle ID must be positive."
                    )

                if not isinstance(vehicle_type, str):
                    raise ValueError(
                        "Vehicle type must be Car, Bus, or Bike."
                    )

                type_code = VEHICLE_TYPES.get(
                    vehicle_type.strip().lower()
                )

                if type_code is None:
                    raise ValueError(
                        "Vehicle type must be Car, Bus, or Bike."
                    )

                result = send_to_engine(
                    f"ADD {lane} {vehicle_id} {type_code}"
                )

            elif path == "/api/signal":
                lane = normalize_lane(data.get("lane"))
                result = send_to_engine(f"SIGNAL {lane}")

            elif path == "/api/automatic":
                result = send_to_engine("AUTO")

            elif path == "/api/search":
                try:
                    vehicle_id = int(data.get("id"))
                except (ValueError, TypeError):
                    raise ValueError(
                        "Vehicle ID must be an integer."
                    )

                if vehicle_id <= 0:
                    raise ValueError(
                        "Vehicle ID must be positive."
                    )

                result = send_to_engine(
                    f"SEARCH {vehicle_id}"
                )

            else:
                send_json(
                    self,
                    {"success": False, "error": "API endpoint not found."},
                    404
                )
                return

            send_json(self, result)

        except (json.JSONDecodeError, UnicodeDecodeError):
            send_json(
                self,
                {"success": False, "error": "Invalid JSON request."},
                400
            )

        except (ValueError, TypeError) as exc:
            send_json(
                self,
                {"success": False, "error": str(exc)},
                400
            )

        except Exception as exc:
            print(
                f"[TrafficFlow] Request error: {exc}",
                file=sys.stderr,
                flush=True
            )
            send_json(
                self,
                {"success": False, "error": str(exc)},
                500
            )


def main():
    try:
        start_engine()

        server = ThreadingHTTPServer(
            (HOST, PORT),
            TrafficFlowHandler
        )

        print(
            f"TrafficFlow running on port {PORT}",
            flush=True
        )

        server.serve_forever()

    except KeyboardInterrupt:
        print("TrafficFlow stopping...", flush=True)

    finally:
        if engine is not None and engine.poll() is None:
            engine.terminate()

            try:
                engine.wait(timeout=5)
            except subprocess.TimeoutExpired:
                engine.kill()
                engine.wait()


if __name__ == "__main__":
    main()
