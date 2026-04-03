#!/usr/bin/env python3
import argparse
import json
import os
import select
import signal
import sys
import termios
import threading
import time
import tty
from dataclasses import dataclass
from shutil import get_terminal_size
from urllib.parse import parse_qs, urlparse

import requests
import websocket
from websocket import WebSocketConnectionClosedException, WebSocketTimeoutException


@dataclass
class JupyterTarget:
    base_http: str
    base_ws: str
    token: str


def parse_target(url: str) -> JupyterTarget:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http/https URLs are supported")
    if not parsed.netloc:
        raise ValueError("URL must include host:port")

    query = parse_qs(parsed.query)
    token = ""
    if "token" in query and query["token"]:
        token = query["token"][0]
    if not token:
        raise ValueError("token is required in URL query, e.g. ?token=xxxx")

    base_http = f"{parsed.scheme}://{parsed.netloc}"
    ws_scheme = "wss" if parsed.scheme == "https" else "ws"
    base_ws = f"{ws_scheme}://{parsed.netloc}"
    return JupyterTarget(base_http=base_http, base_ws=base_ws, token=token)


class JTermClient:
    def __init__(
        self,
        target: JupyterTarget,
        verify_ssl: bool = True,
        keep_remote: bool = False,
        ping_interval: float = 15.0,
    ):
        self.target = target
        self.verify_ssl = verify_ssl
        self.keep_remote = keep_remote
        self.ping_interval = ping_interval
        self.session = requests.Session()
        self.stop_event = threading.Event()
        self.ws = None
        self.term_name = None

    def _api(self, path: str) -> str:
        return f"{self.target.base_http}{path}"

    def _ws(self, path: str) -> str:
        return f"{self.target.base_ws}{path}"

    def _auth_params(self):
        return {"token": self.target.token}

    def create_terminal(self) -> str:
        # Validate server/token before creating a terminal.
        health = self.session.get(self._api("/api"), params=self._auth_params(), timeout=15, verify=self.verify_ssl)
        health.raise_for_status()

        resp = self.session.post(
            self._api("/api/terminals"),
            params=self._auth_params(),
            json={},
            timeout=15,
            verify=self.verify_ssl,
        )
        resp.raise_for_status()
        data = resp.json()
        name = data.get("name")
        if not name:
            raise RuntimeError(f"Unexpected /api/terminals response: {data}")
        self.term_name = name
        return name

    def connect_ws(self, term_name: str):
        ws_url = self._ws(f"/terminals/websocket/{term_name}?token={self.target.token}")
        self.ws = websocket.create_connection(ws_url, timeout=5, enable_multithread=True)
        # Keep recv responsive while treating timeout as a normal idle state.
        self.ws.settimeout(1)

    def send_resize(self):
        if not self.ws:
            return
        size = get_terminal_size(fallback=(80, 24))
        payload = json.dumps(["set_size", size.lines, size.columns])
        try:
            self.ws.send(payload)
        except Exception:
            self.stop_event.set()

    def reader_loop(self):
        while not self.stop_event.is_set():
            try:
                msg = self.ws.recv()
            except WebSocketTimeoutException:
                continue
            except WebSocketConnectionClosedException:
                self.stop_event.set()
                break
            except Exception:
                self.stop_event.set()
                break

            if msg is None:
                self.stop_event.set()
                break

            try:
                decoded = json.loads(msg)
            except Exception:
                continue

            if not isinstance(decoded, list) or len(decoded) < 2:
                continue

            event = decoded[0]
            if event == "stdout":
                text = decoded[1]
                if text:
                    sys.stdout.write(text)
                    sys.stdout.flush()
            elif event == "disconnect":
                self.stop_event.set()
                break

    def keepalive_loop(self):
        while not self.stop_event.is_set():
            if self.stop_event.wait(self.ping_interval):
                break
            try:
                self.ws.ping("jterm")
            except Exception:
                self.stop_event.set()
                break

    def writer_loop(self):
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while not self.stop_event.is_set():
                r, _, _ = select.select([fd], [], [], 0.1)
                if not r:
                    continue
                data = os.read(fd, 4096)
                if not data:
                    self.stop_event.set()
                    break
                try:
                    self.ws.send(json.dumps(["stdin", data.decode(errors="ignore")]))
                except Exception:
                    self.stop_event.set()
                    break
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def cleanup(self):
        try:
            if self.ws is not None:
                self.ws.close()
        except Exception:
            pass

        if self.term_name and not self.keep_remote:
            try:
                self.session.delete(
                    self._api(f"/api/terminals/{self.term_name}"),
                    params=self._auth_params(),
                    timeout=10,
                    verify=self.verify_ssl,
                )
            except Exception:
                pass

    def run(self):
        term_name = self.create_terminal()
        self.connect_ws(term_name)
        self.send_resize()

        def _on_winch(_signum, _frame):
            self.send_resize()

        signal.signal(signal.SIGWINCH, _on_winch)

        reader = threading.Thread(target=self.reader_loop, daemon=True)
        keeper = threading.Thread(target=self.keepalive_loop, daemon=True)
        reader.start()
        keeper.start()

        try:
            self.writer_loop()
        except KeyboardInterrupt:
            self.stop_event.set()
        finally:
            self.stop_event.set()
            time.sleep(0.05)
            self.cleanup()


def main():
    parser = argparse.ArgumentParser(
        prog="jterm",
        description="Connect local terminal to a remote Jupyter built-in terminal over HTTP/WebSocket.",
    )
    parser.add_argument("url", help='Jupyter URL with token, e.g. "http://localhost:8848/?token=4628"')
    parser.add_argument("--insecure", action="store_true", help="Disable SSL certificate verification")
    parser.add_argument("--keep", action="store_true", help="Do not delete remote terminal when exiting")
    parser.add_argument("--ping-interval", type=float, default=15.0, help="WebSocket ping interval in seconds")
    args = parser.parse_args()

    try:
        target = parse_target(args.url)
        client = JTermClient(
            target=target,
            verify_ssl=not args.insecure,
            keep_remote=args.keep,
            ping_interval=args.ping_interval,
        )
        client.run()
    except requests.HTTPError as e:
        body = ""
        try:
            body = f" Response body: {e.response.text}"
        except Exception:
            pass
        print(f"HTTP error: {e}{body}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
