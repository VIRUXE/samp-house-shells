"""Send one command to the blender-mcp add-on's socket in a running Blender (port 9876) and print the reply.

usage: python tools/blender_call.py <command> ['<json params>']
e.g.   python tools/blender_call.py get_viewport_screenshot '{"filepath": "C:/tmp/v.png", "max_size": 1280}'
       python tools/blender_call.py execute_code '{"code": "bpy.context.scene[\"night\"] = 1"}'
"""

import json
import socket
import sys


def call(command: str, params: dict, port: int = 9876) -> dict:
    with socket.create_connection(("localhost", port), timeout=60) as conn:
        conn.sendall(json.dumps({"type": command, "params": params}).encode())
        buf = b""
        while True:
            chunk = conn.recv(65536)
            if not chunk:
                break
            buf += chunk
            try:
                return json.loads(buf)
            except json.JSONDecodeError:
                continue
    return json.loads(buf)


if __name__ == "__main__":
    print(json.dumps(call(sys.argv[1], json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}), indent=1)[:2000])
