#!/usr/bin/env python3
"""Collect, verify, rank and track public Indonesian HTTP CONNECT proxies."""
import concurrent.futures
import ipaddress
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SOURCES = (
    ("ProxyScrape", "https://raw.githubusercontent.com/proxyscrape/free-proxy-list/main/proxies/countries/id/http/data.json"),
    ("ProxMint", "https://raw.githubusercontent.com/proxmint/free-proxy-list/main/proxies/all.json"),
)
OUTPUT = Path("proxyList-ID.txt")
METRICS = Path("proxyList-ID-metrics.json")
MAX_CANDIDATES_PER_SOURCE = 80
MAX_OUTPUT = 60
HISTORY_SIZE = 48  # 24 hours when refreshed every 30 minutes
TIMEOUT_SECONDS = 5
WORKERS = 30
USER_AGENT = "Nautica-ProxyBank/2.0"


def fetch_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError(f"Feed returned HTTP {response.status}: {url}")
        raw = response.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise RuntimeError("Feed response exceeds 4 MiB limit")
        return json.loads(raw.decode("utf-8"))


def extract_candidates(source_name, payload):
    rows = payload if isinstance(payload, list) else payload.get("proxies", [])
    candidates = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        country = str(row.get("country_code") or row.get("country") or "").strip().upper()
        if country not in ("ID", "INDONESIA") or str(row.get("protocol", "")).lower() != "http":
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
            "ip": ip, "port": port, "source": source_name,
            "isp": " ".join(str(row.get("isp") or row.get("asn") or source_name).replace(",", " ").split())[:120],
        })
    return candidates[:MAX_CANDIDATES_PER_SOURCE]


def verify_proxy(candidate):
    """Require two independent HTTPS checks to confirm an Indonesian exit."""
    proxy = f"http://{candidate['ip']}:{candidate['port']}"
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    )
    checks = (
        ("ipwho", "https://ipwho.is/?fields=success,country_code"),
        ("cloudflare", "https://www.cloudflare.com/cdn-cgi/trace"),
    )
    latencies = []
    for name, url in checks:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        started = time.monotonic()
        try:
            with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
                if response.status != 200:
                    return {"online": False, "latency_ms": None, "checks_passed": 0}
                body = response.read(8192).decode("utf-8", errors="replace")
            elapsed_ms = round((time.monotonic() - started) * 1000)
            if name == "ipwho":
                result = json.loads(body)
                passed = (
                    result.get("success") is True
                    and str(result.get("country_code", "")).upper() == "ID"
                )
            else:
                fields = dict(
                    line.split("=", 1) for line in body.splitlines() if "=" in line
                )
                passed = fields.get("loc", "").upper() == "ID"
            if not passed:
                return {"online": False, "latency_ms": None, "checks_passed": len(latencies)}
            latencies.append(elapsed_ms)
        except (OSError, ValueError, urllib.error.URLError, TimeoutError):
            return {"online": False, "latency_ms": None, "checks_passed": len(latencies)}
    return {
        "online": True,
        "latency_ms": round(sum(latencies) / len(latencies)),
        "checks_passed": len(latencies),
    }


def load_previous():
    try:
        data = json.loads(METRICS.read_text(encoding="utf-8"))
        return {f"{p['ip']}:{p['port']}": p for p in data.get("proxies", [])}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def main():
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    candidates = []
    for source_name, url in SOURCES:
        try:
            loaded = extract_candidates(source_name, fetch_json(url))
            candidates.extend(loaded)
            print(f"{source_name}: {len(loaded)} Indonesian HTTP candidates loaded")
        except Exception as exc:
            print(f"{source_name}: feed unavailable: {exc}")

    unique = {}
    for candidate in candidates:
        unique[(candidate["ip"], candidate["port"])] = candidate
    candidates = list(unique.values())
    if not candidates:
        raise SystemExit("No Indonesian candidates loaded; preserving previous proxy bank.")

    previous = load_previous()
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        future_map = {pool.submit(verify_proxy, item): item for item in candidates}
        for future in concurrent.futures.as_completed(future_map):
            candidate = future_map[future]
            try:
                result = future.result()
            except Exception:
                result = {"online": False, "latency_ms": None}
            key = f"{candidate['ip']}:{candidate['port']}"
            old = previous.get(key, {})
            old_history = old.get("history", [])
            history = [value is True for value in old_history if isinstance(value, bool)] if isinstance(old_history, list) else []
            history.append(bool(result and result["online"]))
            history = history[-HISTORY_SIZE:]
            success_count = sum(history)
            uptime = round(100 * success_count / len(history), 1) if history else 0.0
            # Bayesian smoothing prevents a proxy with only one successful check
            # from tying an established proxy with a longer clean history.
            reliability_score = round(
                100 * (success_count + 1) / (len(history) + 2), 1
            ) if history else 0.0
            results[key] = {
                "ip": candidate["ip"], "port": candidate["port"],
                "country": "ID", "source": candidate["source"],
                "isp": candidate["isp"],
                "online": bool(result and result["online"]),
                "latency_ms": result["latency_ms"] if result else None,
                "endpoint_checks_passed": result.get("checks_passed", 0) if result else 0,
                "uptime_percent": uptime,
                "reliability_score": reliability_score,
                "checks": len(history), "history": history,
                "last_checked": checked_at,
            }

    active = [p for p in results.values() if p["online"]]
    verified_count = len(active)
    # Rank by reliability first, then current measured latency.
    active.sort(key=lambda p: (
        -p["reliability_score"], -p["checks"],
        p["latency_ms"] if p["latency_ms"] is not None else 999999
    ))
    active = active[:MAX_OUTPUT]
    if not active:
        raise SystemExit("No proxy passed live verification; preserving previous proxy bank.")

    lines = [f"{p['ip']},{p['port']},ID,{p['isp']}" for p in active]
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    metrics = {
        "checked_at": checked_at,
        "refresh_interval_minutes": 30,
        "history_window_hours": 24,
        "candidate_count": len(candidates),
        "verified_count": verified_count,
        "output_count": len(active),
        "proxies": sorted(results.values(), key=lambda p: (
            not p["online"], -p["reliability_score"], -p["checks"],
            p["latency_ms"] if p["latency_ms"] is not None else 999999
        )),
    }
    METRICS.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(f"Candidates checked: {len(candidates)}")
    print(f"Verified Indonesian HTTP CONNECT proxies: {verified_count}")
    print(f"Published to proxy bank (max {MAX_OUTPUT}): {len(active)}")
    print("Verification: both ipwho.is and Cloudflare trace must confirm an Indonesian exit.")
    print("Ranking: smoothed reliability (24h history), observation count, then average two-target latency.")
    for proxy in active[:10]:
        print(f"  {proxy['ip']}:{proxy['port']} - {proxy['latency_ms']} ms, uptime {proxy['uptime_percent']}%")


if __name__ == "__main__":
    main()
