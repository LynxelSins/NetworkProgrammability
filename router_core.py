"""
router_core.py - Core Router State Engine.

Owns the simulated router state and provides direct Python API functions
for managing router interfaces. This acts as the internal control plane /
datastore of the virtual router, serving as the single source of truth
for both the Legacy CLI and the RESTCONF server.
"""

import json
from pathlib import Path
from typing import Optional, List, Dict, Any

STATE_FILE = Path(__file__).resolve().parent / "router_state.json"

DEFAULT_STATE = {
    "interface": [
        {
            "name": "GigabitEthernet0/0",
            "description": "Uplink to Core",
            "type": "iana-if-type:ethernetCsmacd",
            "enabled": True,
            "ipv4": {
                "address": [
                    {"ip": "192.168.1.1", "netmask": "255.255.255.0"}
                ]
            },
            "oper-status": "up",
        },
        {
            "name": "GigabitEthernet0/1",
            "description": "Link to Access Switch",
            "type": "iana-if-type:ethernetCsmacd",
            "enabled": True,
            "ipv4": {
                "address": [
                    {"ip": "10.0.0.1", "netmask": "255.255.255.0"}
                ]
            },
            "oper-status": "up",
        },
    ]
}


def normalize_interface_name(name: str) -> str:
    """
    Normalizes common Cisco interface abbreviations (e.g. g0/0, gi0/0)
    to full canonical names (e.g. GigabitEthernet0/0).
    """
    cleaned = name.strip()
    lower = cleaned.lower()
    if lower.startswith("gi") and not lower.startswith("gigabitethernet"):
        return "GigabitEthernet" + cleaned[2:]
    elif lower.startswith("g") and not lower.startswith("gigabitethernet"):
        return "GigabitEthernet" + cleaned[1:]
    return cleaned


def _load_state() -> Dict[str, Any]:
    """Loads state from router_state.json, or resets to default if missing/corrupt."""
    if not STATE_FILE.exists():
        _save_state(DEFAULT_STATE)
        return json.loads(json.dumps(DEFAULT_STATE))
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        _save_state(DEFAULT_STATE)
        return json.loads(json.dumps(DEFAULT_STATE))


def _save_state(state: Dict[str, Any]) -> None:
    """Atomically persists state to router_state.json."""
    temp_file = STATE_FILE.with_suffix(".tmp")
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    temp_file.replace(STATE_FILE)


def reset_state() -> List[Dict[str, Any]]:
    """Resets the router state back to factory demo defaults."""
    state = json.loads(json.dumps(DEFAULT_STATE))
    _save_state(state)
    return state["interface"]


def get_all_interfaces() -> List[Dict[str, Any]]:
    """Returns all interfaces in the router datastore."""
    state = _load_state()
    return state.get("interface", [])


def get_interface(name: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single interface by exact or abbreviated name."""
    norm_name = normalize_interface_name(name)
    state = _load_state()
    for intf in state.get("interface", []):
        if intf["name"].lower() == norm_name.lower():
            return intf
    return None


def set_interface_enabled(name: str, enabled: bool) -> Optional[Dict[str, Any]]:
    """
    Enables or disables an interface (admin status).
    Automatically updates operational status accordingly.
    """
    norm_name = normalize_interface_name(name)
    state = _load_state()
    target_intf = None
    for intf in state.get("interface", []):
        if intf["name"].lower() == norm_name.lower():
            intf["enabled"] = bool(enabled)
            intf["oper-status"] = "up" if enabled else "administratively down"
            target_intf = intf
            break

    if target_intf:
        _save_state(state)
    return target_intf


def set_interface_ip(name: str, ip: str, netmask: str = "255.255.255.0") -> Optional[Dict[str, Any]]:
    """Sets the primary IPv4 address and netmask for an interface."""
    norm_name = normalize_interface_name(name)
    state = _load_state()
    target_intf = None
    for intf in state.get("interface", []):
        if intf["name"].lower() == norm_name.lower():
            intf["ipv4"] = {"address": [{"ip": ip, "netmask": netmask}]}
            target_intf = intf
            break

    if target_intf:
        _save_state(state)
    return target_intf


def update_interface(name: str, patch_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Updates interface attributes using a dictionary payload (used by RESTCONF PATCH).
    Keeps oper-status consistent with enabled state.
    """
    norm_name = normalize_interface_name(name)
    state = _load_state()
    target_intf = None
    for intf in state.get("interface", []):
        if intf["name"].lower() == norm_name.lower():
            intf.update(patch_data)
            if "enabled" in patch_data:
                intf["oper-status"] = "up" if patch_data["enabled"] else "administratively down"
            target_intf = intf
            break

    if target_intf:
        _save_state(state)
    return target_intf
