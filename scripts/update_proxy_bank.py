#!/usr/bin/env python3
"""Build Nautica's Indonesia HTTP CONNECT proxy bank from public feeds.

Only candidates labelled Indonesia by a source are considered. Each candidate
must then pass an HTTPS request through the proxy and report country_code=ID.
No proxy credentials or user traffic are used.
"""
import concurrent.futures
import ipaddress
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

SOURCES = (
    ("ProxyScrape", "https://raw.githubusercontent.com/proxyscrape/free-proxy-list/main/proxies/countries/id/http/data.json"),
    ("ProxMint", "https://raw.githubusercontent.com/proxmint/free-proxy-list/main/proxies/all.json"),
)
OUTPUT = Path("proxyList.txt")
MAX_CANDIDATES_PER_SOURCE = 50
MAX_OUTPUT = 60
TIMEOUT_SECONDS = 7


def fetch_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Nautica-ProxyBank/1.0"})
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError(f"Feed returned HTTP {response.status}: {url}")
        return json.loads(response.read().decode("utf-8"))


def extract_candidates(source_name, payload):
    rows = payload if isinstance(payload, list) else payload.get("proxies", [])
    candidates = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        country = str(row.get("country_code") or row.get("country") or "").strip().upper()
        if country not in ("ID", "INDONESIA"):
            continue
        if str(row.get("protocol", "")).lower() != "http":
            continue
        ip = str(row.get("ip", "")).strip()
        try:
            address = ipaddress.ip_address(ip)
            port = int(row.get("port"))
        except (ValueError, TypeError):
            continue
        if address.version != 4 or not address.is_global or not 1 <= port <= 65535:
            continue
        candidates.append({
            "ip": ip,
            "port": port,
            "source": source_name,
            "latency": float(row.get("latency_ms") or row.get("latencyMs") or 999999),
            "isp": str(row.get("isp") or row.get("asn") or source_name).replace(",", " ").strip(),
        })
    candidates.sort(key=lambda item: item["latency"])
    return candidates[:MAX_CANDIDATES_PER_SOURCE]


def verify_proxy(candidate):
    proxy = f"http://{candidate['ip']}:{candidate['port']}"
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    )
    request = urllib.request.Request(
        "https://ipwho.is/?fields=success,country_code",
        headers={"User-Agent": "Nautica-ProxyBank/1.0"},
    )
    started = time.monotonic()
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            if response.status != 200:
                return None
            result = json.loads(response.read(4096).decode("utf-8"))
        elapsed_ms = round((time.monotonic() - started) * 1000)
        if result.get("success") is True and str(result.get("country_code", "")).upper() == "ID":
            return (candidate["ip"], candidate["port"], "ID",
                    f"{candidate['source']} {candidate['isp']}"[:100], elapsed_ms)
    except (OSError, ValueError, urllib.error.URLError, TimeoutError):
        return None
    return None


def main():
    candidates = []
    for source_name, url in SOURCES:
        try:
            candidates.extend(extract_candidates(source_name, fetch_json(url)))
            print(f"{source_name}: candidates loaded")
        except Exception as exc:
            print(f"{source_name}: feed unavailable: {exc}")

    unique = {}
    for candidate in candidates:
        unique[(candidate["ip"], candidate["port"])] = candidate
    candidates = sorted(unique.values(), key=lambda item: item["latency"])

    verified = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(verify_proxy, item) for item in candidates]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                verified.append(result)

    verified.sort(key=lambda item: item[4])
    verified = verified[:MAX_OUTPUT]
    lines = [f"{ip},{port},{country},{org}" for ip, port, country, org, _ in verified]
    OUTPUT.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print(f"Verified Indonesian HTTP CONNECT proxies: {len(lines)}")
    if not lines:
        raise SystemExit("No proxy passed the live Indonesia exit-IP check; empty bank written.")


if __name__ == "__main__":
    main()
