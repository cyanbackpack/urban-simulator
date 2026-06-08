#!/usr/bin/env python3
"""Local CityBench web server with scorer/validator API endpoints.

    python web_server.py

Then open http://127.0.0.1:8765/web/
"""

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import score_v2
import validate as validate_mod


HOST = "127.0.0.1"
PORT = 8765
MAX_BODY = 24 * 1024 * 1024


def _payload_parts(payload):
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    terrain = payload.get("terrain")
    submission = payload.get("submission")
    if not isinstance(terrain, dict):
        raise ValueError("payload.terrain must be an object")
    if not isinstance(submission, dict):
        raise ValueError("payload.submission must be an object")
    return terrain, submission


def score_payload(payload):
    terrain, submission = _payload_parts(payload)
    return score_v2.run(terrain, submission)


def validate_payload(payload):
    terrain, submission = _payload_parts(payload)
    return validate_mod.validate(terrain, submission)


class CityBenchHandler(SimpleHTTPRequestHandler):
    server_version = "CityBenchWorkbench/0.1"

    def do_POST(self):
        routes = {
            "/api/score": score_payload,
            "/api/validate": validate_payload,
        }
        handler = routes.get(self.path)
        if not handler:
            self.send_error(404, "unknown endpoint")
            return
        try:
            payload = self._read_json()
            result = handler(payload)
            self._send_json(result)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            self._send_json({"error": str(exc), "type": exc.__class__.__name__}, status=500)

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("invalid Content-Length") from exc
        if length <= 0:
            raise ValueError("empty request body")
        if length > MAX_BODY:
            raise ValueError("request body too large")
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON: {exc}") from exc

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main():
    server = ThreadingHTTPServer((HOST, PORT), CityBenchHandler)
    print(f"CityBench web server: http://{HOST}:{PORT}/web/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
