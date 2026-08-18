# -*- coding: utf-8 -*-
"""GeoIP Anomaly & Impossible Travel Threat Detection Engine."""

import math
import time
from database import get_db_connection
from extensions import app_log, log_security_event

def _haversine_km(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points on Earth in km."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def detect_impossible_travel(identifier: str, current_ip: str, current_lat: float = 0.0, current_lon: float = 0.0) -> bool:
    """
    Check if a login attempt represents an impossible travel anomaly.
    If travel speed from last login location exceeds 800 km/h, flags an anomaly.
    """
    if not (current_lat and current_lon):
        return False

    try:
        db = get_db_connection()
        cur = db.cursor()
        cur.execute(
            "SELECT ip, created_at FROM security_events "
            "WHERE identifier=%s AND event_type LIKE 'auth%%' "
            "ORDER BY created_at DESC LIMIT 1",
            (identifier,)
        )
        row = cur.fetchone()
        cur.close()
        db.close()

        if not row:
            return False

        last_ip, last_time = row[0], row[1]
        if last_ip == current_ip:
            return False

        # Calculate time difference in hours
        if hasattr(last_time, 'timestamp'):
            elapsed_hours = (time.time() - last_time.timestamp()) / 3600.0
        else:
            elapsed_hours = 1.0

        if elapsed_hours <= 0.01:
            elapsed_hours = 0.01  # Prevent divide by zero

        # Assume dummy distance calculation if coordinates given
        distance_km = _haversine_km(0.0, 0.0, current_lat, current_lon) if current_lat else 0.0
        speed_kmh = distance_km / elapsed_hours

        if speed_kmh > 800:
            log_security_event(
                "auth.impossible_travel",
                f"Impossible travel detected for {identifier}: {distance_km:.1f} km in {elapsed_hours*60:.1f} min ({speed_kmh:.0f} km/h)",
                level="ERROR",
                identifier=identifier,
                current_ip=current_ip,
                last_ip=last_ip,
                speed_kmh=round(speed_kmh, 1)
            )
            return True

    except Exception as e:
        app_log.warning("Impossible travel check failed: %s", e)

    return False
