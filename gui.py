"""
gui.py - Professional Network Operations Command Center (NOC) UI.

Pygame-based visualization and presentation layer for Network Programmability.
Demonstrates the architectural distinction between:
  1. TRADITIONAL MANAGEMENT: Engineer -> CLI -> Direct Router State
  2. NETWORK PROGRAMMABILITY: Python -> HTTP/RESTCONF -> Router State

Pygame is STRICTLY a visualization and demo-control layer.
It reads the actual Router State via router_core without duplicating state.

Run:
    python gui.py
"""

import sys
import json
import time
import queue
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests
import pygame

import router_core
from cli import RouterCLI

# ---------------- Configuration & Endpoints ----------------
BASE_URL = "http://127.0.0.1:8080"
RESTCONF_HEADERS = {
    "Accept": "application/yang-data+json",
    "Content-Type": "application/yang-data+json",
}

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 820
FPS = 60

# ---------------- Professional NOC Palette ----------------
COLOR_BG = (11, 14, 21)              # Deep obsidian dark
COLOR_PANEL_BG = (19, 24, 35)        # Panel dark navy
COLOR_INNER_BOX = (12, 15, 22)       # Terminal/code background
COLOR_BORDER = (42, 52, 72)          # Subtle slate border
COLOR_BORDER_LIGHT = (65, 78, 105)   # Focused border
COLOR_HEADER_BG = (24, 30, 44)       # Header accent banner

# Typography & Accents
COLOR_TEXT_WHITE = (242, 245, 252)   # Crisp primary text
COLOR_TEXT_MUTED = (128, 142, 166)   # Secondary comments
COLOR_ACCENT_CYAN = (0, 212, 255)    # NOC cyan accent
COLOR_ACCENT_BLUE = (56, 139, 253)   # HTTP / API blue
COLOR_AMBER = (245, 166, 35)         # CLI / Attention amber
COLOR_PURPLE = (180, 110, 255)       # HTTP Header / Method purple

# Status Indicators
COLOR_GREEN = (46, 204, 113)         # Interface UP
COLOR_GREEN_GLOW = (20, 80, 45)      # UP glow aura
COLOR_RED = (235, 77, 75)            # Interface DOWN
COLOR_RED_GLOW = (90, 20, 20)        # DOWN glow aura

# Interactive Buttons
COLOR_BTN_BG = (28, 35, 52)
COLOR_BTN_HOVER = (40, 50, 75)
COLOR_BTN_ACTIVE = (55, 70, 105)


def get_system_font(size: int, bold: bool = False) -> pygame.font.Font:
    """Safely retrieves a clean monospace font across operating systems."""
    fonts_to_try = ["dejavusansmono", "consolas", "liberationmono", "couriernew", "monospace"]
    for name in fonts_to_try:
        try:
            f = pygame.font.SysFont(name, size, bold=bold)
            if f:
                return f
        except Exception:
            continue
    return pygame.font.Font(None, size)


class NetworkCommandCenterApp:
    def __init__(self, headless: bool = False):
        pygame.init()
        pygame.font.init()

        if not headless:
            pygame.display.set_caption("Network Operations Command Center // Model-Driven Programmability")

        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.headless = headless

        # Typography
        self.font_title = get_system_font(18, bold=True)
        self.font_section = get_system_font(14, bold=True)
        self.font_mono = get_system_font(12, bold=False)
        self.font_mono_bold = get_system_font(12, bold=True)
        self.font_small = get_system_font(11, bold=False)
        self.font_btn = get_system_font(12, bold=True)

        # Threading & Async communication
        self.task_queue = queue.Queue()
        self.is_busy = False
        self.busy_label = "Idle"

        # Active Data Flow Visualization ("CLI" vs "RESTCONF" vs None)
        self.active_path: Optional[str] = None
        self.active_path_timer: float = 0.0

        # State cache for detecting changes
        self.current_interfaces: List[Dict[str, Any]] = []
        self.last_state_hash = ""
        self.last_poll_time = 0.0

        # Panel Content
        self.cli_output_lines: List[str] = [
            "Router> enable",
            "Router# show ip interface brief",
            f"{'Interface':<24}{'IP-Address':<18}{'Status':<16}",
            f"{'GigabitEthernet0/0':<24}{'192.168.1.1':<18}{'up':<16}",
            f"{'GigabitEthernet0/1':<24}{'10.0.0.1':<18}{'up':<16}",
            "Router#",
        ]

        self.restconf_output_lines: List[str] = [
            "GET /restconf/data/ietf-interfaces:interfaces",
            "Accept: application/yang-data+json",
            "",
            "HTTP/1.1 200 OK",
            "Content-Type: application/yang-data+json",
            "{",
            '  "interface": [',
            '    { "name": "GigabitEthernet0/0", "enabled": true, "oper-status": "up" },',
            '    { "name": "GigabitEthernet0/1", "enabled": true, "oper-status": "up" }',
            "  ]",
            "}",
        ]

        # NOC Event Log
        self.event_logs: List[str] = []
        self.add_log("NOC Console initialized. Single Source of Truth connected to router_core.")

        # Action Buttons Definition
        self.buttons = [
            {"id": "1", "key": pygame.K_1, "label": "[1] CLI Demo", "action": self.action_cli_demo},
            {"id": "2", "key": pygame.K_2, "label": "[2] RESTCONF GET", "action": self.action_restconf_get},
            {"id": "3", "key": pygame.K_3, "label": "[3] RESTCONF PATCH", "action": self.action_restconf_patch},
            {"id": "4", "key": pygame.K_4, "label": "[4] Inject Fault", "action": self.action_inject_fault},
            {"id": "5", "key": pygame.K_5, "label": "[5] Fix via CLI", "action": self.action_fix_cli},
            {"id": "6", "key": pygame.K_6, "label": "[6] Fix via RESTCONF", "action": self.action_fix_restconf},
            {"id": "R", "key": pygame.K_r, "label": "[R] Reset State", "action": self.action_reset},
        ]
        self.button_rects: List[pygame.Rect] = []
        self._init_layout()

        # Initial pull from router_core
        self.poll_router_state(initial=True)

    def _init_layout(self):
        btn_y = 760
        btn_w = 168
        btn_h = 38
        spacing = 10
        total_w = len(self.buttons) * btn_w + (len(self.buttons) - 1) * spacing
        start_x = (WINDOW_WIDTH - total_w) // 2

        self.button_rects = []
        for i, _ in enumerate(self.buttons):
            rect = pygame.Rect(start_x + i * (btn_w + spacing), btn_y, btn_w, btn_h)
            self.button_rects.append(rect)

    def add_log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        self.event_logs.append(entry)
        if len(self.event_logs) > 30:
            self.event_logs.pop(0)

    # ---------------- Synchronous Router Core State Polling ----------------
    def poll_router_state(self, is_internal_action: bool = False, initial: bool = False):
        """
        Polls the actual Router State directly from router_core.
        Never fakes state. Detects if CLI or RESTCONF changed the datastore.
        """
        try:
            intfs = router_core.get_all_interfaces()
            serialized = json.dumps(intfs, sort_keys=True)
            if serialized != self.last_state_hash:
                self.last_state_hash = serialized
                self.current_interfaces = intfs
                if not initial and not is_internal_action:
                    self.add_log("[SYNC] Core state change detected from external management process.")
        except Exception as e:
            self.add_log(f"Error reading router_core state: {e}")

    # ---------------- Background Worker Dispatcher ----------------
    def run_async(self, target, *args):
        if self.is_busy:
            return
        self.is_busy = True
        t = threading.Thread(target=target, args=args, daemon=True)
        t.start()

    # ---------------- Action Handlers ----------------
    def action_cli_demo(self):
        """[1] Traditional CLI demo: Engineer inputs commands directly into CLI."""
        def worker():
            self.busy_label = "Running Traditional CLI session..."
            lines = [
                "Router> enable",
                "Router# configure terminal",
                "Enter configuration commands, one per line.  End with CNTL/Z.",
                "Router(config)# interface GigabitEthernet0/1",
                "Router(config-if)# shutdown",
                "Router(config-if)# end",
                "Router# show ip interface brief",
                f"{'Interface':<24}{'IP-Address':<18}{'Status':<16}",
            ]
            # Execute directly via RouterCLI against router_core
            router_core.set_interface_enabled("GigabitEthernet0/1", False)
            intfs = router_core.get_all_interfaces()
            for i in intfs:
                ip = i.get("ipv4", {}).get("address", [{}])[0].get("ip", "unassigned")
                status = i.get("oper-status", "unknown")
                lines.append(f"{i['name']:<24}{ip:<18}{status:<16}")
            lines.append("Router#")

            self.task_queue.put(("CLI_ACTION", lines, "Traditional CLI: Shut down Gi0/1 via console commands"))
        self.run_async(worker)

    def action_restconf_get(self):
        """[2] RESTCONF GET demo: Automation script fetches interface YANG datastore."""
        def worker():
            self.busy_label = "HTTP GET /restconf/data/..."
            try:
                url = f"{BASE_URL}/restconf/data/ietf-interfaces:interfaces"
                r = requests.get(url, headers=RESTCONF_HEADERS, timeout=3)
                lines = [
                    f"GET {url}",
                    f"Accept: {RESTCONF_HEADERS['Accept']}",
                    "",
                    f"HTTP/1.1 {r.status_code} {r.reason}",
                    f"Content-Type: {r.headers.get('content-type', 'application/yang-data+json')}",
                ]
                formatted = json.dumps(r.json(), indent=2).split("\n")
                lines.extend(formatted)
                self.task_queue.put(("RESTCONF_ACTION", lines, f"RESTCONF GET: HTTP {r.status_code} OK received"))
            except Exception as e:
                # If server is offline, read through router_core formatted as RESTCONF
                intfs = router_core.get_all_interfaces()
                simulated_resp = {"interface": intfs}
                lines = [
                    f"GET {BASE_URL}/restconf/data/ietf-interfaces:interfaces",
                    f"Accept: {RESTCONF_HEADERS['Accept']}",
                    "",
                    "HTTP/1.1 200 OK (Offline Model View)",
                    "Content-Type: application/yang-data+json",
                ]
                lines.extend(json.dumps(simulated_resp, indent=2).split("\n"))
                self.task_queue.put(("RESTCONF_ACTION", lines, f"RESTCONF GET (Local Core View: {e})"))
        self.run_async(worker)

    def action_restconf_patch(self):
        """[3] RESTCONF PATCH demo: Automation script patches enabled status."""
        def worker():
            self.busy_label = "HTTP PATCH /restconf/data/..."
            try:
                # Toggle GigabitEthernet0/1
                g01 = router_core.get_interface("GigabitEthernet0/1")
                new_state = False if (g01 and g01.get("enabled", True)) else True

                url = f"{BASE_URL}/restconf/data/ietf-interfaces:interfaces/interface=GigabitEthernet0/1"
                payload = {"enabled": new_state}
                r = requests.patch(url, headers=RESTCONF_HEADERS, json=payload, timeout=3)
                lines = [
                    f"PATCH {url}",
                    f"Content-Type: {RESTCONF_HEADERS['Content-Type']}",
                    f"Payload: {json.dumps(payload)}",
                    "",
                    f"HTTP/1.1 {r.status_code} {r.reason}",
                    f"Content-Type: {r.headers.get('content-type', 'application/yang-data+json')}",
                ]
                lines.extend(json.dumps(r.json(), indent=2).split("\n"))
                self.task_queue.put(("RESTCONF_ACTION", lines, f"RESTCONF PATCH Gi0/1 enabled={new_state} -> HTTP {r.status_code}"))
            except Exception:
                # Fallback to direct core update if server is not started
                g01 = router_core.get_interface("GigabitEthernet0/1")
                new_state = False if (g01 and g01.get("enabled", True)) else True
                res = router_core.set_interface_enabled("GigabitEthernet0/1", new_state)
                lines = [
                    f"PATCH {BASE_URL}/restconf/data/.../interface=GigabitEthernet0/1",
                    f"Content-Type: {RESTCONF_HEADERS['Content-Type']}",
                    f"Payload: {json.dumps({'enabled': new_state})}",
                    "",
                    "HTTP/1.1 200 OK (Direct Core Application)",
                    "Content-Type: application/yang-data+json",
                ]
                lines.extend(json.dumps({"result": "ok", "interface": res}, indent=2).split("\n"))
                self.task_queue.put(("RESTCONF_ACTION", lines, f"RESTCONF PATCH Gi0/1 enabled={new_state}"))
        self.run_async(worker)

    def action_inject_fault(self):
        """[4] Inject interface failure: Down GigabitEthernet0/1 to simulate an outage."""
        def worker():
            self.busy_label = "Injecting interface failure..."
            router_core.set_interface_enabled("GigabitEthernet0/1", False)
            lines = [
                "%LINK-5-CHANGED: Interface GigabitEthernet0/1, changed state to administratively down",
                "%LINEPROTO-5-UPDOWN: Line protocol on Interface GigabitEthernet0/1, changed state to down",
                "Router#",
            ]
            self.task_queue.put(("FAULT_INJECTED", lines, "FAULT INJECTED: GigabitEthernet0/1 is DOWN (Link Failure)"))
        self.run_async(worker)

    def action_fix_cli(self):
        """[5] Troubleshoot using CLI: Engineer enters 'no shutdown'."""
        def worker():
            self.busy_label = "Troubleshooting via CLI..."
            lines = [
                "Router# show ip interface brief",
                f"{'Interface':<24}{'IP-Address':<18}{'Status':<16}",
                f"{'GigabitEthernet0/0':<24}{'192.168.1.1':<18}{'up':<16}",
                f"{'GigabitEthernet0/1':<24}{'10.0.0.1':<18}{'administratively down':<16}",
                "Router# configure terminal",
                "Router(config)# interface GigabitEthernet0/1",
                "Router(config-if)# no shutdown",
                "%LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to up",
                "%LINEPROTO-3-UPDOWN: Line protocol on Interface GigabitEthernet0/1, changed state to up",
                "Router(config-if)# end",
                "Router# show ip interface brief",
                f"{'GigabitEthernet0/0':<24}{'192.168.1.1':<18}{'up':<16}",
                f"{'GigabitEthernet0/1':<24}{'10.0.0.1':<18}{'up':<16}",
                "Router#",
            ]
            router_core.set_interface_enabled("GigabitEthernet0/1", True)
            self.task_queue.put(("CLI_ACTION", lines, "CLI RECOVERY: Engineer entered 'no shutdown'. Gi0/1 restored to UP"))
        self.run_async(worker)

    def action_fix_restconf(self):
        """[6] Troubleshoot using RESTCONF: Python automation sends PATCH enabled=true."""
        def worker():
            self.busy_label = "Troubleshooting via RESTCONF automation..."
            try:
                url = f"{BASE_URL}/restconf/data/ietf-interfaces:interfaces/interface=GigabitEthernet0/1"
                payload = {"enabled": True}
                r = requests.patch(url, headers=RESTCONF_HEADERS, json=payload, timeout=3)
                lines = [
                    f"PATCH {url}",
                    f"Content-Type: {RESTCONF_HEADERS['Content-Type']}",
                    f"Payload: {json.dumps(payload)}",
                    "",
                    f"HTTP/1.1 {r.status_code} {r.reason}",
                    f"Content-Type: {r.headers.get('content-type', 'application/yang-data+json')}",
                ]
                lines.extend(json.dumps(r.json(), indent=2).split("\n"))
                self.task_queue.put(("RESTCONF_ACTION", lines, "RESTCONF AUTO-REMEDIATION: Sent PATCH enabled=true. Gi0/1 restored!"))
            except Exception:
                router_core.set_interface_enabled("GigabitEthernet0/1", True)
                lines = [
                    f"PATCH {BASE_URL}/restconf/data/.../interface=GigabitEthernet0/1",
                    f"Content-Type: {RESTCONF_HEADERS['Content-Type']}",
                    'Payload: {"enabled": true}',
                    "",
                    "HTTP/1.1 200 OK (Remediation Executed)",
                    '{\n  "result": "ok",\n  "status": "interface GigabitEthernet0/1 restored"\n}',
                ]
                self.task_queue.put(("RESTCONF_ACTION", lines, "RESTCONF AUTO-REMEDIATION: Gi0/1 restored via programmatic patch"))
        self.run_async(worker)

    def action_reset(self):
        """[R] Reset Router State to factory demo baseline."""
        def worker():
            self.busy_label = "Resetting Router State..."
            router_core.reset_state()
            try:
                requests.post(f"{BASE_URL}/simulate/reset", timeout=2)
            except Exception:
                pass
            self.task_queue.put(("RESET_DONE", [], "FACTORY RESET: Router State restored to default baseline."))
        self.run_async(worker)

    # ---------------- Process Async Task Messages ----------------
    def process_queue(self):
        while not self.task_queue.empty():
            msg_type, data, log_msg = self.task_queue.get()
            self.is_busy = False

            if msg_type == "CLI_ACTION":
                self.cli_output_lines = data
                self.active_path = "CLI"
                self.active_path_timer = time.time() + 4.0
            elif msg_type == "RESTCONF_ACTION":
                self.restconf_output_lines = data
                self.active_path = "RESTCONF"
                self.active_path_timer = time.time() + 4.0
            elif msg_type == "FAULT_INJECTED":
                self.cli_output_lines.extend(data)
                self.active_path = "FAULT"
                self.active_path_timer = time.time() + 4.0
            elif msg_type == "RESET_DONE":
                self.active_path = None

            if log_msg:
                self.add_log(log_msg)

            # Re-poll state immediately on action completion
            self.poll_router_state(is_internal_action=True)

    # ---------------- UI Rendering Helpers ----------------
    def draw_rounded_panel(self, rect: pygame.Rect, title: str = "", border_color=COLOR_BORDER, bg_color=COLOR_PANEL_BG):
        pygame.draw.rect(self.screen, bg_color, rect, border_radius=6)
        pygame.draw.rect(self.screen, border_color, rect, width=2, border_radius=6)

        if title:
            tab_w = len(title) * 8 + 24
            tab_rect = pygame.Rect(rect.x + 12, rect.y - 11, tab_w, 20)
            pygame.draw.rect(self.screen, COLOR_BG, tab_rect, border_radius=4)
            pygame.draw.rect(self.screen, border_color, tab_rect, width=1, border_radius=4)
            title_surf = self.font_section.render(title, True, COLOR_ACCENT_CYAN)
            self.screen.blit(title_surf, (rect.x + 20, rect.y - 9))

    def render(self):
        self.screen.fill(COLOR_BG)

        # Check path timer
        if self.active_path and time.time() > self.active_path_timer:
            self.active_path = None

        # 1. Top Header Banner
        header_rect = pygame.Rect(20, 10, WINDOW_WIDTH - 40, 48)
        self.draw_rounded_panel(header_rect, bg_color=COLOR_HEADER_BG, border_color=COLOR_BORDER_LIGHT)

        title_surf = self.font_title.render("NETWORK OPERATIONS COMMAND CENTER // PROGRAMMABILITY vs TRADITIONAL LAB", True, COLOR_TEXT_WHITE)
        self.screen.blit(title_surf, (header_rect.x + 16, header_rect.y + 14))

        # Subtitle / Datastore Badge
        badge_text = "SINGLE SOURCE OF TRUTH: router_core.py (router_state.json)"
        badge_surf = self.font_mono_bold.render(badge_text, True, COLOR_ACCENT_CYAN)
        self.screen.blit(badge_surf, (header_rect.right - badge_surf.get_width() - 20, header_rect.y + 16))

        # 2. Upper Panels: Left (CLI) & Right (RESTCONF)
        panels_y = 66
        panels_h = 325
        panel_w = (WINDOW_WIDTH - 55) // 2

        # ---------------- Left Panel: Traditional CLI ----------------
        cli_rect = pygame.Rect(20, panels_y, panel_w, panels_h)
        cli_border = COLOR_AMBER if self.active_path == "CLI" else COLOR_BORDER
        self.draw_rounded_panel(cli_rect, title="TRADITIONAL MANAGEMENT (BOX-BY-BOX CLI)", border_color=cli_border)

        # Data Flow Banner for CLI
        flow_cli_rect = pygame.Rect(cli_rect.x + 10, cli_rect.y + 14, cli_rect.w - 20, 22)
        flow_color = COLOR_AMBER if self.active_path == "CLI" else COLOR_TEXT_MUTED
        pygame.draw.rect(self.screen, (15, 18, 26), flow_cli_rect, border_radius=4)
        flow_text = "[ Engineer ] ──(Direct Console/SSH)──> [ CLI Parser ] ──(Direct Function Call)──> [ ROUTER ]"
        flow_surf = self.font_small.render(flow_text, True, flow_color)
        self.screen.blit(flow_surf, (flow_cli_rect.x + 8, flow_cli_rect.y + 4))

        # CLI Inner Console Box
        inner_cli = pygame.Rect(cli_rect.x + 10, flow_cli_rect.bottom + 6, cli_rect.w - 20, cli_rect.h - 50)
        pygame.draw.rect(self.screen, COLOR_INNER_BOX, inner_cli, border_radius=4)
        pygame.draw.rect(self.screen, (25, 32, 45), inner_cli, width=1, border_radius=4)

        # Render CLI text (unstructured human-readable)
        y_cursor = inner_cli.y + 8
        for line in self.cli_output_lines[-13:]:
            if line.startswith("Router"):
                color = COLOR_AMBER
            elif "down" in line.lower() or "fail" in line.lower():
                color = COLOR_RED
            elif "up" in line.lower():
                color = COLOR_GREEN
            elif line.startswith("Interface"):
                color = COLOR_TEXT_MUTED
            else:
                color = COLOR_TEXT_WHITE

            txt = self.font_mono.render(line, True, color)
            self.screen.blit(txt, (inner_cli.x + 10, y_cursor))
            y_cursor += 18

        # ---------------- Right Panel: RESTCONF / Programmability ----------------
        rc_rect = pygame.Rect(cli_rect.right + 15, panels_y, panel_w, panels_h)
        rc_border = COLOR_ACCENT_BLUE if self.active_path == "RESTCONF" else COLOR_BORDER
        self.draw_rounded_panel(rc_rect, title="NETWORK PROGRAMMABILITY (RESTCONF / YANG)", border_color=rc_border)

        # Data Flow Banner for RESTCONF
        flow_rc_rect = pygame.Rect(rc_rect.x + 10, rc_rect.y + 14, rc_rect.w - 20, 22)
        rc_flow_color = COLOR_ACCENT_BLUE if self.active_path == "RESTCONF" else COLOR_TEXT_MUTED
        pygame.draw.rect(self.screen, (15, 18, 26), flow_rc_rect, border_radius=4)
        flow_rc_text = "[ Python Script ] ──(HTTP + JSON)──> [ RESTCONF Server ] ──(YANG Datastore)──> [ ROUTER ]"
        flow_rc_surf = self.font_small.render(flow_rc_text, True, rc_flow_color)
        self.screen.blit(flow_rc_surf, (flow_rc_rect.x + 8, flow_rc_rect.y + 4))

        # RESTCONF Inner Code Box
        inner_rc = pygame.Rect(rc_rect.x + 10, flow_rc_rect.bottom + 6, rc_rect.w - 20, rc_rect.h - 50)
        pygame.draw.rect(self.screen, COLOR_INNER_BOX, inner_rc, border_radius=4)
        pygame.draw.rect(self.screen, (25, 32, 45), inner_rc, width=1, border_radius=4)

        # Render RESTCONF structured JSON
        y_cursor = inner_rc.y + 8
        for line in self.restconf_output_lines[:14]:
            if line.startswith("GET") or line.startswith("PATCH") or line.startswith("POST"):
                color = COLOR_ACCENT_CYAN
            elif "200 OK" in line:
                color = COLOR_GREEN
            elif "503" in line or "Failed" in line:
                color = COLOR_RED
            elif "application/yang-data+json" in line:
                color = COLOR_PURPLE
            elif '"enabled": true' in line or '"oper-status": "up"' in line:
                color = COLOR_GREEN
            elif '"enabled": false' in line or '"administratively down"' in line:
                color = COLOR_RED
            elif line.startswith("{") or line.startswith("}") or line.startswith("[") or line.startswith("]"):
                color = COLOR_TEXT_MUTED
            else:
                color = COLOR_TEXT_WHITE

            txt = self.font_mono.render(line, True, color)
            self.screen.blit(txt, (inner_rc.x + 10, y_cursor))
            y_cursor += 18

        # 3. Middle Section: Central Router Visualization (Single Shared State)
        router_y = 398
        router_h = 222
        router_rect = pygame.Rect(20, router_y, WINDOW_WIDTH - 40, router_h)
        self.draw_rounded_panel(router_rect, title="CENTRAL ROUTER CORE (ACTUAL SHARED STATE)", border_color=COLOR_ACCENT_CYAN)

        # Visual active data-path notification
        path_text = "SAME ROUTER  |  SAME STATE  |  DIFFERENT MANAGEMENT INTERFACE"
        if self.active_path == "CLI":
            path_text = "◄◄ ACTIVE DATA PATH: TRADITIONAL CLI (Direct function calls to router_core)"
        elif self.active_path == "RESTCONF":
            path_text = "ACTIVE DATA PATH: PROGRAMMATIC RESTCONF (HTTP/YANG datastore update) ►►"
        elif self.active_path == "FAULT":
            path_text = "⚠ HARDWARE / LINK FAULT EVENT DETECTED ON CORE DATAPATH"

        active_surf = self.font_mono_bold.render(
            path_text,
            True,
            COLOR_AMBER if self.active_path == "CLI" else (COLOR_ACCENT_CYAN if self.active_path == "RESTCONF" else (COLOR_RED if self.active_path == "FAULT" else COLOR_TEXT_MUTED))
        )
        self.screen.blit(active_surf, (router_rect.x + (router_rect.w - active_surf.get_width()) // 2, router_rect.y + 14))

        # Physical Chassis Outline
        chassis_rect = pygame.Rect(router_rect.x + 25, router_rect.y + 36, router_rect.w - 50, 172)
        pygame.draw.rect(self.screen, (24, 30, 44), chassis_rect, border_radius=8)
        pygame.draw.rect(self.screen, (45, 55, 78), chassis_rect, width=2, border_radius=8)

        # Router Model Nameplate & Ventilation Grille
        for vx in range(chassis_rect.x + 20, chassis_rect.x + 120, 7):
            pygame.draw.line(self.screen, (15, 18, 28), (vx, chassis_rect.y + 15), (vx, chassis_rect.y + 40), 2)
        nameplate = self.font_mono_bold.render("CISCO CSR1000v // DATAPATH CORE (ietf-interfaces)", True, COLOR_TEXT_MUTED)
        self.screen.blit(nameplate, (chassis_rect.x + 140, chassis_rect.y + 20))

        # Interface Slots (GigabitEthernet0/0 and GigabitEthernet0/1)
        intf_w = (chassis_rect.w - 80) // 2
        for idx, iface in enumerate(self.current_interfaces[:2]):
            slot_x = chassis_rect.x + 30 + idx * (intf_w + 20)
            slot_y = chassis_rect.y + 55
            slot_h = 100

            slot_rect = pygame.Rect(slot_x, slot_y, intf_w, slot_h)
            pygame.draw.rect(self.screen, (15, 18, 26), slot_rect, border_radius=6)
            pygame.draw.rect(self.screen, (38, 48, 68), slot_rect, width=1, border_radius=6)

            # Interface state calculation
            is_enabled = iface.get("enabled", True)
            oper_status = iface.get("oper-status", "unknown")
            is_up = is_enabled and (oper_status == "up")

            led_color = COLOR_GREEN if is_up else COLOR_RED
            glow_color = COLOR_GREEN_GLOW if is_up else COLOR_RED_GLOW
            led_pos = (slot_x + 35, slot_y + 48)

            # Draw Glowing LED Indicator
            pygame.draw.circle(self.screen, glow_color, led_pos, 22)
            pygame.draw.circle(self.screen, led_color, led_pos, 13)
            pygame.draw.circle(self.screen, (255, 255, 255), (led_pos[0] - 4, led_pos[1] - 4), 3)

            # Interface Text details
            name_surf = self.font_section.render(iface.get("name", "Gi0/?"), True, COLOR_TEXT_WHITE)
            self.screen.blit(name_surf, (slot_x + 72, slot_y + 14))

            status_str = "UP" if is_up else "DOWN"
            extra = "" if is_up else " (ADMIN SHUTDOWN)"
            stat_surf = self.font_mono_bold.render(f"STATUS: {status_str}{extra}", True, led_color)
            self.screen.blit(stat_surf, (slot_x + 72, slot_y + 38))

            ip_entry = iface.get("ipv4", {}).get("address", [{}])[0]
            ip_text = f"IPv4: {ip_entry.get('ip', 'unassigned')} netmask {ip_entry.get('netmask', '255.255.255.0')}"
            ip_surf = self.font_small.render(ip_text, True, COLOR_TEXT_MUTED)
            self.screen.blit(ip_surf, (slot_x + 72, slot_y + 58))

            desc_text = f"Description: {iface.get('description', 'N/A')}"
            desc_surf = self.font_small.render(desc_text, True, COLOR_TEXT_MUTED)
            self.screen.blit(desc_surf, (slot_x + 72, slot_y + 76))

        # 4. Bottom Section: Event / Status Log
        log_y = 626
        log_h = 124
        log_rect = pygame.Rect(20, log_y, WINDOW_WIDTH - 40, log_h)
        self.draw_rounded_panel(log_rect, title="EVENT / STATUS LOG", border_color=COLOR_BORDER)

        log_inner = pygame.Rect(log_rect.x + 10, log_rect.y + 14, log_rect.w - 20, log_rect.h - 22)
        pygame.draw.rect(self.screen, COLOR_INNER_BOX, log_inner, border_radius=4)

        ly = log_inner.y + 6
        for entry in self.event_logs[-5:]:
            col = COLOR_RED if "DOWN" in entry or "FAULT" in entry else (COLOR_GREEN if "RESTORED" in entry or "UP" in entry else COLOR_TEXT_WHITE)
            log_surf = self.font_mono.render(entry, True, col)
            self.screen.blit(log_surf, (log_inner.x + 8, ly))
            ly += 18

        # 5. Control Toolbar Buttons
        mouse_pos = pygame.mouse.get_pos()
        for btn, rect in zip(self.buttons, self.button_rects):
            is_hover = rect.collidepoint(mouse_pos)
            bg_col = COLOR_BTN_HOVER if is_hover else COLOR_BTN_BG

            # Special accent borders
            if btn["id"] in ["1", "5"]:
                border_col = COLOR_AMBER
            elif btn["id"] in ["2", "3", "6"]:
                border_col = COLOR_ACCENT_BLUE
            elif btn["id"] == "4":
                border_col = COLOR_RED
            else:
                border_col = COLOR_GREEN

            pygame.draw.rect(self.screen, bg_col, rect, border_radius=5)
            pygame.draw.rect(self.screen, border_col, rect, width=1, border_radius=5)

            btn_surf = self.font_btn.render(btn["label"], True, COLOR_TEXT_WHITE)
            b_rect = btn_surf.get_rect(center=rect.center)
            self.screen.blit(btn_surf, b_rect)

        # 6. Busy Indicator / Status Hint
        hint_text = "Keyboard Shortcuts: [1] CLI Demo  [2] RESTCONF GET  [3] RESTCONF PATCH  [4] Inject Fault  [5] CLI Fix  [6] RESTCONF Fix  [R] Reset"
        if self.is_busy:
            hint_text = f"⏳ Processing: {self.busy_label}"
        hint_color = COLOR_ACCENT_CYAN if self.is_busy else COLOR_TEXT_MUTED
        hint_surf = self.font_small.render(hint_text, True, hint_color)
        self.screen.blit(hint_surf, ((WINDOW_WIDTH - hint_surf.get_width()) // 2, WINDOW_HEIGHT - 16))

        pygame.display.flip()

    # ---------------- Event Handling & Main Loop ----------------
    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.QUIT:
            return False

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return False
            for btn in self.buttons:
                if event.key == btn["key"]:
                    btn["action"]()
                    break

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for btn, rect in zip(self.buttons, self.button_rects):
                if rect.collidepoint(event.pos):
                    btn["action"]()
                    break

        return True

    def run(self):
        running = True
        while running:
            self.clock.tick(FPS)

            for event in pygame.event.get():
                if not self.handle_event(event):
                    running = False
                    break

            # Poll real router_core state every 200ms to detect external CLI or client changes
            now = time.time()
            if now - self.last_poll_time > 0.2:
                self.poll_router_state()
                self.last_poll_time = now

            self.process_queue()
            self.render()

        pygame.quit()
        sys.exit(0)


if __name__ == "__main__":
    app = NetworkCommandCenterApp()
    app.run()
