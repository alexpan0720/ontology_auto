"""Drive the debug Edge window over CDP to take 2x screenshots of the running app.

python cdp.py goto <url>
python cdp.py eval <js>
python cdp.py shot <name> [x y w h]     # clip in CSS px of a 1440x900 viewport
"""
import base64
import itertools
import json
import os
import pathlib
import sys
import time
import urllib.request

import websocket

OUT = pathlib.Path(__file__).resolve().parent.parent / "images"
W, H = int(os.environ.get("CDP_W", 1440)), 900


def connect() -> websocket.WebSocket:
    tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9333/json"))
    page = next(t for t in tabs if t["type"] == "page" and t["url"].startswith("http://localhost:3000"))
    return websocket.create_connection(page["webSocketDebuggerUrl"], max_size=None, suppress_origin=True)


ids = itertools.count(1)


def call(ws: websocket.WebSocket, method: str, **params: object) -> dict:
    i = next(ids)
    ws.send(json.dumps({"id": i, "method": method, "params": params}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == i:
            if "error" in msg:
                raise RuntimeError(msg["error"])
            return msg["result"]


def evaluate(ws: websocket.WebSocket, js: str) -> object:
    r = call(ws, "Runtime.evaluate", expression=js, awaitPromise=True, returnByValue=True)
    return r["result"].get("value", r["result"].get("description"))


def main() -> None:
    cmd, *args = sys.argv[1:]
    ws = connect()
    call(ws, "Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=2, mobile=False)
    if cmd == "goto":
        call(ws, "Page.navigate", url=args[0])
        time.sleep(4)
        print(evaluate(ws, "location.href"))
    elif cmd == "eval":
        print(json.dumps(evaluate(ws, args[0]), ensure_ascii=False)[:4000])
    elif cmd == "ask":
        evaluate(ws, "document.querySelector('textarea, input[placeholder*=问题]').focus()")
        call(ws, "Input.insertText", text=args[0])
        for kind in ("keyDown", "keyUp"):
            call(ws, "Input.dispatchKeyEvent", type=kind, key="Enter", code="Enter", windowsVirtualKeyCode=13,
                 text="\r" if kind == "keyDown" else "")
        print("asked")
    elif cmd == "shot":
        time.sleep(1.5)
        params: dict = {"format": "png"}
        if len(args) == 5:
            x, y, w, h = map(float, args[1:])
            params["clip"] = {"x": x, "y": y, "width": w, "height": h, "scale": 1}
        data = call(ws, "Page.captureScreenshot", **params)["data"]
        (OUT / f"{args[0]}.png").write_bytes(base64.b64decode(data))
        print("saved", OUT / f"{args[0]}.png")
    ws.close()


if __name__ == "__main__":
    main()
