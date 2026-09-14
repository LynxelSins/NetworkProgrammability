"""
cli.py - Traditional Cisco-style CLI Simulation.

Directly accesses the simulated Router State via router_core.py function calls.
Represents Traditional Network Management (Box-by-Box CLI).
MUST NOT import requests or talk to RESTCONF endpoints.

Run:
    python cli.py

Example session:
    Router> enable
    Router# configure terminal
    Router(config)# interface GigabitEthernet0/1
    Router(config-if)# shutdown
    Router(config-if)# end
    Router# show ip interface brief
"""
import cmd
import router_core


class RouterCLI(cmd.Cmd):
    intro = "Mock Router CLI -- type 'help' for commands, 'quit' to exit.\n"
    prompt = "Router> "

    def __init__(self):
        super().__init__()
        self.mode = "user"  # user -> priv -> config -> config-if
        self.current_if = None

    def _set_prompt(self):
        prompts = {
            "user": "Router> ",
            "priv": "Router# ",
            "config": "Router(config)# ",
            "config-if": "Router(config-if)# ",
        }
        self.prompt = prompts.get(self.mode, "Router> ")

    def do_enable(self, arg):
        """Enter privileged EXEC mode."""
        self.mode = "priv"
        self._set_prompt()

    def do_configure(self, arg):
        """configure terminal: Enter global configuration mode."""
        if arg.strip() == "terminal" and self.mode in ("priv", "config", "config-if"):
            self.mode = "config"
            self._set_prompt()
        else:
            print("% Invalid input. Use: configure terminal")

    def do_interface(self, arg):
        """interface <name>: Select an interface to configure (e.g. interface g0/0)."""
        if self.mode not in ("config", "config-if"):
            print("% Invalid input: Must be in configure mode")
            return
        ifname = arg.strip()
        if not ifname:
            print("% Interface name required")
            return
        intf = router_core.get_interface(ifname)
        if not intf:
            print(f"% Interface {ifname} not found")
            return
        self.current_if = intf["name"]
        self.mode = "config-if"
        self._set_prompt()

    def do_shutdown(self, arg):
        """Administratively shut down the current interface."""
        if self.mode != "config-if" or not self.current_if:
            print("% Command only valid in interface configuration mode")
            return
        res = router_core.set_interface_enabled(self.current_if, False)
        if not res:
            print("% Failed to update interface state")

    def do_no(self, arg):
        """Negate a command or set its defaults, e.g. 'no shutdown'."""
        if self.mode != "config-if" or not self.current_if:
            print("% Command only valid in interface configuration mode")
            return
        if arg.strip() == "shutdown":
            res = router_core.set_interface_enabled(self.current_if, True)
            if not res:
                print("% Failed to update interface state")
        else:
            print("% Invalid input. Try: no shutdown")

    def do_ip(self, arg):
        """ip address <ip> <mask>: Configure IP address on the interface."""
        if self.mode != "config-if" or not self.current_if:
            print("% Command only valid in interface configuration mode")
            return
        parts = arg.split()
        if len(parts) == 3 and parts[0] == "address":
            ip, mask = parts[1], parts[2]
            res = router_core.set_interface_ip(self.current_if, ip, mask)
            if not res:
                print("% Failed to configure IP address")
        else:
            print("% Invalid input. Syntax: ip address <ip> <mask>")

    def do_show(self, arg):
        """show ip interface brief | show running-config | show ip route"""
        arg = arg.strip()
        interfaces = router_core.get_all_interfaces()

        if arg == "ip interface brief":
            print(f"{'Interface':<24}{'IP-Address':<18}{'Status':<26}")
            for i in interfaces:
                ip = i.get("ipv4", {}).get("address", [{}])[0].get("ip", "unassigned")
                status = i.get("oper-status", "unknown")
                print(f"{i['name']:<24}{ip:<18}{status:<26}")

        elif arg == "running-config":
            print("Building configuration...\n")
            print("Current configuration : 1024 bytes")
            print("!")
            print("hostname Router")
            print("!")
            for i in interfaces:
                print(f"interface {i['name']}")
                if i.get("description"):
                    print(f" description {i['description']}")
                ip_addr = i.get("ipv4", {}).get("address", [{}])[0].get("ip")
                netmask = i.get("ipv4", {}).get("address", [{}])[0].get("netmask", "255.255.255.0")
                if ip_addr:
                    print(f" ip address {ip_addr} {netmask}")
                if not i.get("enabled", True):
                    print(" shutdown")
                print("!")

        elif arg == "ip route":
            print("Codes: C - connected, S - static, R - RIP, M - mobile, B - BGP\n")
            print("Gateway of last resort is not set\n")
            for i in interfaces:
                if i.get("oper-status") == "up":
                    ip_entry = i.get("ipv4", {}).get("address", [{}])[0]
                    ip = ip_entry.get("ip")
                    if ip:
                        # Extract network base assuming /24 for display
                        ip_parts = ip.split(".")
                        subnet = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"
                        print(f"C    {subnet} is directly connected, {i['name']}")
        else:
            print("% Unrecognized command. Available: ip interface brief / running-config / ip route")

    def do_exit(self, arg):
        """Exit current mode and return to previous mode."""
        if self.mode == "config-if":
            self.mode = "config"
            self.current_if = None
        elif self.mode == "config":
            self.mode = "priv"
        elif self.mode == "priv":
            self.mode = "user"
        elif self.mode == "user":
            return True
        self._set_prompt()

    def do_end(self, arg):
        """End configuration mode and return to privileged EXEC mode."""
        self.mode = "priv"
        self.current_if = None
        self._set_prompt()

    def do_quit(self, arg):
        """Exit the CLI."""
        return True

    do_EOF = do_quit


if __name__ == "__main__":
    RouterCLI().cmdloop()
