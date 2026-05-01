#!/usr/bin/env python3
"""
Career Ops Web Dashboard — editable version.

Run:  python3 dashboard-web/serve.py
Then open: http://localhost:8765
"""
import http.server
import json
import os
import re
import socketserver
import sys
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPS_PATH = ROOT / "data" / "applications.md"
PIPELINE_PATH = ROOT / "data" / "pipeline.md"
REPORTS_DIR = ROOT / "reports"
OUTPUT_DIR = ROOT / "output"
INDEX_PATH = Path(__file__).resolve().parent / "index.html"
PORT = 8765


def parse_apps() -> list[dict]:
    if not APPS_PATH.exists():
        return []
    text = APPS_PATH.read_text(encoding="utf-8")
    rows, headers, in_table = [], [], False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|") and not in_table:
            headers = [c.strip() for c in s.strip("|").split("|")]
            in_table = True
            continue
        if in_table and re.match(r"^\|[\s\-|]+\|$", s):
            continue
        if in_table and s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) == len(headers):
                rows.append(dict(zip(headers, cells)))
        elif in_table and not s.startswith("|"):
            in_table = False
    return rows


def collect_reports() -> dict[str, str]:
    out = {}
    if not REPORTS_DIR.exists():
        return out
    for path in sorted(REPORTS_DIR.glob("*.md")):
        if path.name.startswith("."):
            continue
        out[path.name] = path.read_text(encoding="utf-8")
    return out


def collect_pdfs() -> list[str]:
    if not OUTPUT_DIR.exists():
        return []
    return sorted(p.name for p in OUTPUT_DIR.glob("*.pdf"))


def collect_pipeline_count() -> int:
    if not PIPELINE_PATH.exists():
        return 0
    return len(re.findall(r"^- \[ \]", PIPELINE_PATH.read_text(encoding="utf-8"), re.MULTILINE))


def extract_apply_url(report_md: str) -> str | None:
    m = re.search(r"\*\*Apply:\*\*\s*(\S+)", report_md)
    if m:
        return m.group(1)
    m = re.search(r"\*\*URL:\*\*\s*(\S+)", report_md)
    if m:
        return m.group(1)
    return None


def get_data() -> dict:
    apps = parse_apps()
    reports = collect_reports()
    # attach apply URL per row by looking up report
    for r in apps:
        report_link = r.get("Report") or ""
        m = re.search(r"\(reports/([^)]+)\)", report_link)
        if m and m.group(1) in reports:
            r["__apply_url"] = extract_apply_url(reports[m.group(1)])
            r["__report_file"] = m.group(1)
        else:
            r["__apply_url"] = None
            r["__report_file"] = None
    return {
        "apps": apps,
        "reports": reports,
        "pdfs": collect_pdfs(),
        "pipeline_count": collect_pipeline_count(),
        "root": str(ROOT),
    }


def update_app(num: str, status: str | None = None, notes: str | None = None) -> dict:
    """Rewrite the row whose # column equals `num`."""
    if not APPS_PATH.exists():
        return {"ok": False, "error": "applications.md not found"}

    text = APPS_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    out_lines: list[str] = []
    headers: list[str] = []
    in_table = False
    updated = False

    for line in lines:
        s = line.strip()
        if s.startswith("|") and not in_table and not headers:
            headers = [c.strip() for c in s.strip("|").split("|")]
            in_table = True
            out_lines.append(line)
            continue
        if in_table and re.match(r"^\|[\s\-|]+\|$", s):
            out_lines.append(line)
            continue
        if in_table and s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) == len(headers) and cells[0] == str(num):
                # update this row
                row = dict(zip(headers, cells))
                if status is not None:
                    row["Status"] = status
                if notes is not None:
                    row["Notes"] = notes
                rebuilt = "| " + " | ".join(row[h] for h in headers) + " |"
                out_lines.append(rebuilt)
                updated = True
                continue
            out_lines.append(line)
        elif in_table and not s.startswith("|"):
            in_table = False
            out_lines.append(line)
        else:
            out_lines.append(line)

    if not updated:
        return {"ok": False, "error": f"row #{num} not found"}

    APPS_PATH.write_text("\n".join(out_lines) + ("\n" if text.endswith("\n") else ""), encoding="utf-8")
    return {"ok": True}


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stdout.write(f"  → {fmt % args}\n")

    def _send(self, status: int, body: bytes, ctype: str):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self._send(status, body, "application/json")

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html"):
            html = INDEX_PATH.read_text(encoding="utf-8")
            self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/api/data":
            self._send_json(get_data())
        elif path.startswith("/output/"):
            fname = path[len("/output/"):]
            target = OUTPUT_DIR / fname
            if target.exists() and target.is_file():
                ctype = "application/pdf" if fname.endswith(".pdf") else "application/octet-stream"
                self._send(200, target.read_bytes(), ctype)
            else:
                self._send(404, b"not found", "text/plain")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/update":
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            res = update_app(
                num=str(data.get("num", "")),
                status=data.get("status"),
                notes=data.get("notes"),
            )
            self._send_json(res, status=200 if res.get("ok") else 400)
        elif path == "/api/refresh":
            self._send_json({"ok": True, "data": get_data()})
        else:
            self._send(404, b"not found", "text/plain")


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def main():
    os.chdir(ROOT)
    print(f"Career Ops Dashboard")
    print(f"  Root:   {ROOT}")
    print(f"  Apps:   {APPS_PATH}")
    print(f"  Server: http://localhost:{PORT}")
    print()
    if "--no-open" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    with ReusableTCPServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down…")


if __name__ == "__main__":
    main()
