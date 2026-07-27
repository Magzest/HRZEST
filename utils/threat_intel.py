"""SOC Threat Intelligence Feed & Automated Boundary IP Auto-blocking Service.

Periodically polls threat feeds (CISA KEV and malicious IP blocklists),
stores threat indicators in PostgreSQL, and enforces automated IP auto-blocking
at the application boundary.
"""
import time
import json
import threading
import urllib.request
from database import get_db_connection, transaction
from extensions import app_log, log_security_event

_POLL_INTERVAL_SECONDS = 7200  # Poll feeds every 2 hours


def fetch_cisa_kev():
    """Fetch Known Exploited Vulnerabilities (KEV) from CISA open JSON feed."""
    url = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    req = urllib.request.Request(url, headers={"User-Agent": "HRMS-DevSecOps-ThreatIntel/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # nosec B310
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                vulnerabilities = data.get("vulnerabilities", [])
                app_log.info("Fetched %d CVE records from CISA KEV feed.", len(vulnerabilities))
                _store_cve_threats(vulnerabilities)
    except Exception as exc:
        app_log.warning("CISA KEV threat intel fetch failed: %s", exc)


def _store_cve_threats(vulnerabilities):
    """Store CVE indicators into threat_intel_cve table."""
    try:
        db = get_db_connection()
        with transaction(db):
            cur = db.cursor()
            for item in vulnerabilities[:100]:  # Limit top 100 recent
                cve_id = item.get("cveID", "")
                vendor = item.get("vendorProject", "")
                product = item.get("product", "")
                name = item.get("vulnerabilityName", "")
                date_added = item.get("dateAdded", "")
                due_date = item.get("dueDate", "")
                notes = item.get("shortDescription", "")

                cur.execute(
                    "INSERT INTO threat_intel_cve (cve_id, vendor, product, vulnerability_name, date_added, due_date, notes) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (cve_id) DO UPDATE SET vulnerability_name=EXCLUDED.vulnerability_name, due_date=EXCLUDED.due_date, fetched_at=NOW()",
                    (cve_id, vendor, product, name, date_added, due_date, notes[:500])
                )
            cur.close()
    except Exception as exc:
        app_log.error("Failed to persist CVE threat indicators: %s", exc)


def fetch_malicious_ips():
    """Fetch malicious IP blocklists from threat intelligence feeds and enforce boundary auto-blocking."""
    url = "https://raw.githubusercontent.com/stamparm/ipsum/master/ipsum.txt"
    req = urllib.request.Request(url, headers={"User-Agent": "HRMS-DevSecOps-ThreatIntel/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # nosec B310
            if resp.status == 200:
                lines = resp.read().decode("utf-8").splitlines()
                threat_ips = []
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split()
                        if len(parts) >= 2:
                            ip, count = parts[0], int(parts[1])
                            if count >= 3:  # High severity (seen across 3+ feeds)
                                threat_ips.append((ip, count))
                
                app_log.info("Fetched %d high-confidence malicious IPs from Ipsum threat feed.", len(threat_ips))
                _store_and_autoblock_ips(threat_ips[:200])
    except Exception as exc:
        app_log.warning("Malicious IP threat feed fetch failed: %s", exc)


def _store_and_autoblock_ips(threat_ips):
    """Store IP indicators in threat_intel_ips and insert high-confidence matches into banned_ips."""
    try:
        db = get_db_connection()
        with transaction(db):
            cur = db.cursor()
            autoblocked_count = 0
            for ip, score in threat_ips:
                cur.execute(
                    "INSERT INTO threat_intel_ips (ip, threat_score, source) VALUES (%s, %s, 'Ipsum Feed') "
                    "ON CONFLICT (ip) DO UPDATE SET threat_score=EXCLUDED.threat_score, fetched_at=NOW()",
                    (ip, score)
                )

                # Boundary Auto-Blocking Rule: Automatically add to banned_ips table
                cur.execute(
                    "INSERT INTO banned_ips (ip, reason, banned_at) VALUES (%s, 'Threat Intel Auto-Block (Score ' || %s || ')', NOW()) "
                    "ON CONFLICT (ip) DO NOTHING",
                    (ip, str(score))
                )
                if cur.rowcount > 0:
                    autoblocked_count += 1
            cur.close()

            if autoblocked_count > 0:
                log_security_event(
                    "secops.threat_intel_autoblock",
                    f"Automated threat boundary engine auto-blocked {autoblocked_count} high-risk IP address(es)",
                    level="WARNING",
                    count=autoblocked_count
                )
    except Exception as exc:
        app_log.error("Failed to store and auto-block threat IPs: %s", exc)


def _threat_intel_worker():
    """Background worker thread polling external threat intel feeds."""
    app_log.info("Starting Threat Intelligence background polling worker.")
    while True:
        try:
            fetch_cisa_kev()
            fetch_malicious_ips()
        except Exception as exc:
            app_log.error("Threat intelligence worker error: %s", exc)
        time.sleep(_POLL_INTERVAL_SECONDS)


def start_threat_intel_service():
    """Launch the threat intel service daemon thread."""
    t = threading.Thread(target=_threat_intel_worker, daemon=True, name="threat-intel-worker")
    t.start()
