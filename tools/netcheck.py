#!/usr/bin/env python3
"""netcheck — Server & network health checks from the terminal.

TCP port checks, TLS certificate expiry warnings, DNS resolution and
latency probes — for hosts and servers you own or administer.

Zero dependencies — pure standard library.

Usage:
    python netcheck.py ping example.com
    python netcheck.py port myserver.example --ports 22,80,443
    python netcheck.py tls api.example.com            # cert expiry + details
    python netcheck.py dns example.com
"""

from __future__ import annotations

import argparse
import os
import socket
import ssl
import subprocess
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

if os.name == "nt":
    os.system("")

COLOR = {"green": "\033[92m", "yellow": "\033[93m", "red": "\033[91m",
         "cyan": "\033[96m", "dim": "\033[2m", "bold": "\033[1m", "end": "\033[0m"}


def c(text: str, *styles: str) -> str:
    if sys.stdout.isatty() and os.environ.get("NO_COLOR") is None:
        return "".join(COLOR[s] for s in styles) + text + COLOR["end"]
    return text


def parse_ports(spec: str) -> list[int]:
    ports: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            ports.extend(range(int(start), int(end) + 1))
        elif part:
            ports.append(int(part))
    return ports


def tcp_open(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def cmd_ping(args) -> int:
    flag = "-n" if os.name == "nt" else "-c"
    cmd = ["ping", flag, str(args.count), args.host]
    print(c(f"$ {' '.join(cmd)}", "dim"))
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stdout.strip()
    if output:
        print(output)
    if result.returncode != 0 and result.stderr.strip():
        print(c(result.stderr.strip(), "red"))
    return result.returncode


def cmd_port(args) -> int:
    host = args.host
    print(c(f"\n  Scanning {host} — {len(args.ports)} port(s), timeout {args.timeout}s\n",
            "bold", "cyan"))
    open_count = 0
    for port in args.ports:
        service = ""
        try:
            service = socket.getservbyport(port)
            service = f" ({service})"
        except OSError:
            pass
        if tcp_open(host, port, args.timeout):
            open_count += 1
            print(f"  {c('OPEN ', 'green')}  {port}/tcp{service}")
        else:
            print(c(f"  closed  {port}/tcp{service}", "dim"))
    print(c(f"\n  {open_count}/{len(args.ports)} open\n", "bold"))
    return 0


def cmd_tls(args) -> int:
    host = args.host
    port = args.port
    context = ssl.create_default_context()
    if args.insecure:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((host, port), timeout=args.timeout) as sock:
            with context.wrap_socket(sock, server_hostname=host) as tls:
                cert = tls.getpeercert()
                version = tls.version()
    except ssl.SSLCertVerificationError as exc:
        print(c(f"✗ certificate verification failed: {exc.verify_message or exc}", "red"))
        print(c("  (self-signed or expired? inspect with --insecure)", "yellow"))
        return 2
    except OSError as exc:
        print(c(f"✗ connection failed: {exc}", "red"))
        return 2

    expires = ssl.cert_time_to_seconds(cert["notAfter"])
    days_left = (datetime.fromtimestamp(expires, tz=timezone.utc) -
                 datetime.now(timezone.utc)).days
    style = "green" if days_left > 30 else ("yellow" if days_left > 14 else "red")
    issuer = dict(x[0] for x in cert.get("issuer", ())).get("organizationName", "?")
    subject = dict(x[0] for x in cert.get("subject", ())).get("commonName", host)

    print(c(f"\n  TLS  {host}:{port}", "bold", "cyan"))
    print(f"  protocol   {version}")
    print(f"  subject    {subject}")
    print(f"  issuer     {issuer}")
    print(f"  valid to   {cert['notAfter']}  "
          + c(f"({days_left} days left)", style, "bold"))
    sans = [v for kind, v in cert.get("subjectAltName", ()) if kind == "DNS"]
    if sans:
        shown = ", ".join(sans[:6]) + (" …" if len(sans) > 6 else "")
        print(f"  SANs       {shown}")
    if days_left <= 14:
        print(c("\n  ⚠  Certificate expires soon — renew it!", "red", "bold"))
    print()
    return 0


def cmd_dns(args) -> int:
    print(c(f"\n  DNS  {args.host}\n", "bold", "cyan"))
    try:
        infos = socket.getaddrinfo(args.host, None)
    except socket.gaierror as exc:
        print(c(f"✗ resolution failed: {exc}", "red"))
        return 2
    seen: set[str] = set()
    for family, _, _, _, sockaddr in infos:
        ip = sockaddr[0]
        if ip in seen:
            continue
        seen.add(ip)
        kind = "IPv4" if family == socket.AF_INET else "IPv6"
        print(f"  {kind}  {ip}")
    print()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="netcheck",
        description="Network & TLS health checks for hosts you own or administer.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ping", help="ICMP ping via the system tool")
    p.add_argument("host")
    p.add_argument("--count", type=int, default=4)
    p.set_defaults(func=cmd_ping)

    p = sub.add_parser("port", help="TCP port check")
    p.add_argument("host")
    p.add_argument("--ports", type=parse_ports, default="80,443",
                   help="e.g. 22,80,443 or 8000-8010")
    p.add_argument("--timeout", type=float, default=2.0)
    p.set_defaults(func=cmd_port)

    p = sub.add_parser("tls", help="TLS certificate inspection & expiry warning")
    p.add_argument("host")
    p.add_argument("--port", type=int, default=443)
    p.add_argument("--timeout", type=float, default=5.0)
    p.add_argument("--insecure", action="store_true",
                   help="skip verification (for self-signed certs)")
    p.set_defaults(func=cmd_tls)

    p = sub.add_parser("dns", help="resolve A/AAAA records")
    p.add_argument("host")
    p.set_defaults(func=cmd_dns)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
