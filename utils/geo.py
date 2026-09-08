# -*- coding: utf-8 -*-
"""Shared geo math -- single source of truth for the haversine great-circle
distance formula, used both by attendance geofencing (utils/attendance_utils.py)
and by GeoIP impossible-travel detection (utils/geoip.py), which previously
each carried their own copy in different units."""
import math

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two lat/lon points, in kilometers."""
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c
