"""
demo_client.py - Modern Python RESTCONF Client.

Communicates ONLY through standard RESTCONF HTTP endpoints using requests.
Demonstrates Model-Driven Programmability (YANG datastore over HTTP).
Prints HTTP method, endpoint, status code, and JSON response.

Usage:
    python demo_client.py get
    python demo_client.py get g0/1
    python demo_client.py enable g0/1
    python demo_client.py disable g0/1
    python demo_client.py patch g0/1 '{"description": "Branch Office Link"}'
    python demo_client.py down          # Act VII: simulate connection failure
    python demo_client.py up            # Act VII: restore connection
    python demo_client.py reset         # Reset to initial demo state
"""
import sys
import json
import requests

BASE = "http://127.0.0.1:8080"
RESTCONF_HEADERS = {
    "Accept": "application/yang-data+json",
    "Content-Type": "application/yang-data+json",
}

IFMAP = {
    "g0/0": "GigabitEthernet0/0",
    "gi0/0": "GigabitEthernet0/0",
    "g0/1": "GigabitEthernet0/1",
    "gi0/1": "GigabitEthernet0/1",
}


def _resolve_name(short_name: str) -> str:
    return IFMAP.get(short_name.lower(), short_name)


def print_response(method: str, endpoint: str, response: requests.Response) -> None:
    """Helper to clearly print HTTP transaction for students/audience."""
    print("=" * 60)
    print(f"HTTP METHOD:  {method}")
    print(f"ENDPOINT:     {endpoint}")
    print(f"STATUS CODE:  {response.status_code} {response.reason}")
    print("-" * 60)
    try:
        body = response.json()
        print("RESPONSE (JSON / YANG Data):")
        print(json.dumps(body, indent=2))
    except Exception:
        print("RESPONSE (Raw Text):")
        print(response.text)
    print("=" * 60)


def get_interfaces(short_name: str = None) -> None:
    """GET operation: retrieve all interfaces or a specific interface."""
    if short_name:
        name = _resolve_name(short_name)
        url = f"{BASE}/restconf/data/ietf-interfaces:interfaces/interface={name}"
    else:
        url = f"{BASE}/restconf/data/ietf-interfaces:interfaces"

    r = requests.get(url, headers={"Accept": RESTCONF_HEADERS["Accept"]}, timeout=5)
    print_response("GET", url, r)


def patch_interface(short_name: str, payload: dict) -> None:
    """PATCH operation: update specific attributes on an interface."""
    name = _resolve_name(short_name)
    url = f"{BASE}/restconf/data/ietf-interfaces:interfaces/interface={name}"

    r = requests.patch(url, headers=RESTCONF_HEADERS, json=payload, timeout=5)
    print_response("PATCH", url, r)


def set_enabled(short_name: str, enabled: bool) -> None:
    """Convenience helper to patch the 'enabled' state of an interface."""
    patch_interface(short_name, {"enabled": enabled})


def toggle_chaos(down: bool) -> None:
    """Simulate device outage for Act VII demo."""
    action = "down" if down else "up"
    url = f"{BASE}/simulate/{action}"
    r = requests.post(url, timeout=5)
    print_response("POST", url, r)


def reset_demo() -> None:
    """Reset the server state back to demo defaults."""
    url = f"{BASE}/simulate/reset"
    r = requests.post(url, timeout=5)
    print_response("POST", url, r)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1].lower()

    try:
        if cmd == "get":
            target = sys.argv[2] if len(sys.argv) > 2 else None
            get_interfaces(target)

        elif cmd == "enable" and len(sys.argv) > 2:
            set_enabled(sys.argv[2], True)

        elif cmd == "disable" and len(sys.argv) > 2:
            set_enabled(sys.argv[2], False)

        elif cmd == "patch" and len(sys.argv) > 3:
            target = sys.argv[2]
            payload = json.loads(sys.argv[3])
            patch_interface(target, payload)

        elif cmd == "down":
            toggle_chaos(True)

        elif cmd == "up":
            toggle_chaos(False)

        elif cmd == "reset":
            reset_demo()

        else:
            print(f"Unknown command or missing arguments: {' '.join(sys.argv[1:])}\n")
            print(__doc__)

    except requests.exceptions.RequestException as e:
        print("=" * 60)
        print("RESTCONF CONNECTION FAILED:")
        print(f"Error: {e}")
        print("=" * 60)


if __name__ == "__main__":
    main()
