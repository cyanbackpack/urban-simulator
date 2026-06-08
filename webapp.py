#!/usr/bin/env python3
"""CityBench web viewer + scorer.

A dependency-free HTTP server (Python stdlib only) that reuses the existing
deterministic scorer (`score_v2.run`) and reference generator
(`make_reference.generate_reference_submission`). The browser front-end draws
the terrain raster and a submission's zones / transit / facilities / events on
a canvas, then asks the server to score it. The server never re-implements any
scoring logic; it is a thin wrapper so "what you see is what is scored".

    python3 webapp.py [port]        # default 8000

Endpoints:
    GET  /                      -> web/index.html
    GET  /web/<file>            -> static assets
    GET  /api/terrains         -> [{file, name, terrain_type, objective, ...}]
    GET  /api/terrain?file=..  -> terrain JSON
    GET  /api/reference?file=. -> a baseline reference submission for that terrain
    POST /api/score            -> {terrain_file, submission} -> score_v2 result
"""

import glob
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import score_v2 as S

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(ROOT, "web")

# Lazily imported because it pulls numpy; the viewer works without it.
_make_reference = None


def _reference_module():
    global _make_reference
    if _make_reference is None:
        import make_reference
        _make_reference = make_reference
    return _make_reference


def _safe_terrain_path(file_name):
    """Resolve a terrain file name to a path inside ROOT, or None."""
    if not file_name:
        return None
    name = os.path.basename(file_name)              # strip any directory parts
    if not name.endswith(".json"):
        return None
    path = os.path.join(ROOT, name)
    return path if os.path.isfile(path) else None


def _safe_dir(dir_name):
    """Resolve a submissions directory (basename only) inside ROOT."""
    name = os.path.basename((dir_name or "submissions_demo").rstrip("/"))
    path = os.path.join(ROOT, name)
    return path if os.path.isdir(path) else None


def _safe_sub_path(dir_name, file_name):
    """Resolve a submission file inside an allowed directory under ROOT."""
    base = _safe_dir(dir_name)
    if not base or not file_name:
        return None
    name = os.path.basename(file_name)
    if not name.endswith(".json"):
        return None
    path = os.path.join(base, name)
    return path if os.path.isfile(path) else None


def list_terrains():
    out = []
    for path in sorted(glob.glob(os.path.join(ROOT, "terrain_*.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                t = json.load(f)
        except Exception:
            continue
        if "rows" not in t:                          # skip non-terrain json
            continue
        out.append({
            "file": os.path.basename(path),
            "name": t.get("name", os.path.basename(path)),
            "terrain_type": t.get("terrain_type", ""),
            "objective": t.get("objective", ""),
            "width": t.get("width", len(t["rows"][0]) if t["rows"] else 0),
            "height": t.get("height", len(t["rows"])),
            "difficulty": t.get("difficulty", 1.0),
            "budget": t.get("budget", 0),
            "events": len(t.get("events", [])),
        })
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "CityBench/0.4"

    # -- helpers -----------------------------------------------------------
    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, content_type):
        try:
            with open(path, "rb") as f:
                body = f.read()
        except OSError:
            self._send_json({"error": "not found"}, 404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):              # quieter console
        sys.stderr.write("  %s\n" % (fmt % args))

    # -- routing -----------------------------------------------------------
    def do_GET(self):
        parsed = urlparse(self.path)
        route = parsed.path
        qs = parse_qs(parsed.query)

        if route == "/" or route == "/index.html":
            return self._send_file(os.path.join(WEB_DIR, "index.html"),
                                   "text/html; charset=utf-8")
        if route.startswith("/web/"):
            name = os.path.basename(route)
            ctype = ("text/javascript" if name.endswith(".js")
                     else "text/css" if name.endswith(".css")
                     else "application/octet-stream")
            return self._send_file(os.path.join(WEB_DIR, name),
                                   ctype + "; charset=utf-8")
        if route == "/api/terrains":
            return self._send_json(list_terrains())
        if route == "/api/terrain":
            path = _safe_terrain_path((qs.get("file") or [None])[0])
            if not path:
                return self._send_json({"error": "unknown terrain"}, 404)
            with open(path, encoding="utf-8") as f:
                return self._send_json(json.load(f))
        if route == "/api/submissions":
            base = _safe_dir((qs.get("dir") or [None])[0])
            if not base:
                return self._send_json([])
            out = []
            for path in sorted(glob.glob(os.path.join(base, "*.json"))):
                out.append({"file": os.path.basename(path),
                            "dir": os.path.basename(base)})
            return self._send_json(out)
        if route == "/api/submission":
            path = _safe_sub_path((qs.get("dir") or [None])[0],
                                  (qs.get("file") or [None])[0])
            if not path:
                return self._send_json({"error": "unknown submission"}, 404)
            with open(path, encoding="utf-8") as f:
                return self._send_json(json.load(f))
        if route == "/api/leaderboard":
            tpath = _safe_terrain_path((qs.get("file") or [None])[0])
            base = _safe_dir((qs.get("dir") or [None])[0])
            if not tpath or not base:
                return self._send_json({"error": "unknown terrain or dir"}, 404)
            with open(tpath, encoding="utf-8") as f:
                terrain = json.load(f)
            rows = []
            for path in sorted(glob.glob(os.path.join(base, "*.json"))):
                with open(path, encoding="utf-8") as f:
                    sub = json.load(f)
                try:
                    r = S.run(terrain, sub)
                except Exception as exc:
                    r = {"status": "ERROR", "score": 0, "grade": "D",
                         "reasons": [str(exc)]}
                rows.append({
                    "file": os.path.basename(path),
                    "dir": os.path.basename(base),
                    "name": sub.get("metadata", {}).get("objective")
                            or os.path.basename(path),
                    "status": r.get("status"),
                    "score": r.get("score", 0),
                    "grade": r.get("grade", "D"),
                    "axes": r.get("axes", {}),
                    "reasons": r.get("reasons", []),
                })
            rows.sort(key=lambda x: (x["status"] != "OK", -x["score"]))
            return self._send_json({"terrain": terrain.get("name", ""),
                                    "objective": terrain.get("objective", ""),
                                    "rows": rows})
        if route == "/api/reference":
            path = _safe_terrain_path((qs.get("file") or [None])[0])
            if not path:
                return self._send_json({"error": "unknown terrain"}, 404)
            with open(path, encoding="utf-8") as f:
                terrain = json.load(f)
            try:
                sub = _reference_module().generate_reference_submission(terrain)
            except Exception as exc:                 # numpy missing, etc.
                return self._send_json({"error": f"reference unavailable: {exc}"}, 500)
            return self._send_json(sub)
        return self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/score":
            return self._send_json({"error": "not found"}, 404)
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as exc:
            return self._send_json({"error": f"bad JSON: {exc}"}, 400)

        path = _safe_terrain_path(payload.get("terrain_file"))
        if not path:
            return self._send_json({"error": "unknown terrain"}, 404)
        submission = payload.get("submission")
        if not isinstance(submission, dict):
            return self._send_json({"error": "submission must be an object"}, 400)
        with open(path, encoding="utf-8") as f:
            terrain = json.load(f)
        # Optional: the editor can override the scenario's events (add/move/remove)
        # so the user can see how event placement changes the score.
        if isinstance(payload.get("events"), list):
            terrain = dict(terrain)
            terrain["events"] = payload["events"]
        try:
            result = S.run(terrain, submission)
        except Exception as exc:
            return self._send_json({"error": f"scoring failed: {exc}"}, 400)
        return self._send_json(result)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"CityBench web UI on http://localhost:{port}  (Ctrl+C to stop)")
    print(f"  serving terrains from {ROOT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
        httpd.server_close()


if __name__ == "__main__":
    main()
