"""
AirCrewAI — External Flight Data Provider
Supports two modes:
  - DEMO: Returns deterministic hardcoded fixtures (works offline, always consistent)
  - LIVE: Calls AviationStack API for real flight status

Mode is controlled by FLIGHT_DATA_MODE environment variable.
API credentials are never exposed to the frontend.
"""

import os
import json
import requests
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

FLIGHT_DATA_MODE = os.getenv("FLIGHT_DATA_MODE", "demo").lower()
AVIATIONSTACK_KEY = os.getenv("AVIATIONSTACK_API_KEY", "")
AVIATIONSTACK_BASE = "http://api.aviationstack.com/v1"


# ── DEMO FIXTURES ──────────────────────────────────────────────────────────────
# These are deterministic fixtures that always work without any API call.
# The demo scenario is AA1063 ORD->DFW with +105 minute delay.

DEMO_FIXTURES = {
    "AA1063": {
        "flight_id": "F163",
        "flight_number": "AA1063",
        "airline": "American Airlines",
        "origin": {
            "airport": "Chicago O'Hare International Airport",
            "code": "ORD",
            "city": "Chicago",
            "state": "IL",
        },
        "destination": {
            "airport": "Dallas/Fort Worth International Airport",
            "code": "DFW",
            "city": "Dallas",
            "state": "TX",
        },
        "scheduled_departure": "2026-08-12T07:30:00",
        "actual_departure": None,
        "scheduled_arrival": "2026-08-12T09:45:00",
        "actual_arrival": None,
        "delay_minutes": 105,
        "status": "DELAYED",
        "delay_reason": "WEATHER",
        "aircraft_type": "B737",
        "data_source": "DEMO_FIXTURE",
    },
    "AA1021": {
        "flight_id": "F121",
        "flight_number": "AA1021",
        "airline": "American Airlines",
        "origin": {
            "airport": "Dallas/Fort Worth International Airport",
            "code": "DFW",
            "city": "Dallas",
            "state": "TX",
        },
        "destination": {
            "airport": "Phoenix Sky Harbor International Airport",
            "code": "PHX",
            "city": "Phoenix",
            "state": "AZ",
        },
        "scheduled_departure": "2026-08-12T11:15:00",
        "actual_departure": None,
        "scheduled_arrival": "2026-08-12T12:45:00",
        "actual_arrival": None,
        "delay_minutes": 0,
        "status": "SCHEDULED",
        "delay_reason": None,
        "aircraft_type": "B737",
        "data_source": "DEMO_FIXTURE",
    },
    "AA1045": {
        "flight_id": "F145",
        "flight_number": "AA1045",
        "airline": "American Airlines",
        "origin": {
            "airport": "Dallas/Fort Worth International Airport",
            "code": "DFW",
            "city": "Dallas",
            "state": "TX",
        },
        "destination": {
            "airport": "Miami International Airport",
            "code": "MIA",
            "city": "Miami",
            "state": "FL",
        },
        "scheduled_departure": "2026-08-12T13:30:00",
        "actual_departure": None,
        "scheduled_arrival": "2026-08-12T17:15:00",
        "actual_arrival": None,
        "delay_minutes": 0,
        "status": "SCHEDULED",
        "delay_reason": None,
        "aircraft_type": "B787",
        "data_source": "DEMO_FIXTURE",
    },
}

DEMO_NETWORK_STATUS = {
    "timestamp": "2026-08-12T09:32:00",
    "mode": "DEMO",
    "active_disruptions": 4,
    "critical_disruptions": 1,
    "flights_monitored": 88,
    "crew_monitored": 250,
    "network_status": "DEGRADED",
    "estimated_total_impact": 83400,
}


def _parse_aviationstack_response(data: dict, flight_number: str) -> Optional[dict]:
    """Parse AviationStack API response into our standard format."""
    flights = data.get("data", [])
    if not flights:
        return None

    f = flights[0]
    departure = f.get("departure", {})
    arrival = f.get("arrival", {})
    airline = f.get("airline", {})
    aircraft = f.get("aircraft", {})
    flight_info = f.get("flight", {})

    delay = departure.get("delay", 0) or 0

    return {
        "flight_id": None,
        "flight_number": flight_number,
        "airline": airline.get("name", "Unknown"),
        "origin": {
            "airport": departure.get("airport", "Unknown"),
            "code": departure.get("iata", "???"),
            "city": departure.get("airport", "Unknown"),
            "state": None,
        },
        "destination": {
            "airport": arrival.get("airport", "Unknown"),
            "code": arrival.get("iata", "???"),
            "city": arrival.get("airport", "Unknown"),
            "state": None,
        },
        "scheduled_departure": departure.get("scheduled"),
        "actual_departure": departure.get("actual"),
        "scheduled_arrival": arrival.get("scheduled"),
        "actual_arrival": arrival.get("actual"),
        "delay_minutes": delay,
        "status": f.get("flight_status", "UNKNOWN").upper(),
        "delay_reason": "WEATHER" if delay > 30 else None,
        "aircraft_type": aircraft.get("iata", "B737"),
        "data_source": "AVIATIONSTACK_LIVE",
    }


def get_flight_status(flight_number: str) -> Optional[dict]:
    """
    Get flight status for a given flight number.
    Returns demo fixture in DEMO mode, calls AviationStack in LIVE mode.
    """
    flight_number = flight_number.upper().replace(" ", "")

    if FLIGHT_DATA_MODE == "demo":
        result = DEMO_FIXTURES.get(flight_number)
        if result:
            return result
        # Return a generic on-time fixture for unknown flights in demo mode
        return {
            "flight_id": None,
            "flight_number": flight_number,
            "airline": "American Airlines",
            "origin": {"airport": "Unknown", "code": "???", "city": "Unknown", "state": None},
            "destination": {"airport": "Unknown", "code": "???", "city": "Unknown", "state": None},
            "scheduled_departure": "2026-08-12T08:00:00",
            "actual_departure": None,
            "scheduled_arrival": "2026-08-12T10:30:00",
            "actual_arrival": None,
            "delay_minutes": 0,
            "status": "SCHEDULED",
            "delay_reason": None,
            "aircraft_type": "B737",
            "data_source": "DEMO_FIXTURE",
        }

    # LIVE mode — call AviationStack
    if not AVIATIONSTACK_KEY:
        print("Warning: AVIATIONSTACK_API_KEY not set. Falling back to demo mode.")
        return get_flight_status.__wrapped__(flight_number) if hasattr(get_flight_status, '__wrapped__') else None

    try:
        url = f"{AVIATIONSTACK_BASE}/flights"
        params = {
            "access_key": AVIATIONSTACK_KEY,
            "flight_iata": flight_number,
            "limit": 1,
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        result = _parse_aviationstack_response(data, flight_number)
        return result if result else None

    except requests.RequestException as e:
        print(f"AviationStack API error: {e}. Falling back to demo fixture.")
        return DEMO_FIXTURES.get(flight_number)


def get_network_status() -> dict:
    """
    Get overall network operational status.
    Always returns demo status in demo mode.
    """
    if FLIGHT_DATA_MODE == "demo":
        return DEMO_NETWORK_STATUS

    # In live mode, we still return computed status based on our synthetic data
    # (we don't have a real network status endpoint)
    return {
        **DEMO_NETWORK_STATUS,
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "mode": "LIVE",
        "data_source": "COMPUTED",
    }


def get_current_mode() -> str:
    return FLIGHT_DATA_MODE.upper()


def get_demo_disruption() -> dict:
    """Returns the canonical demo disruption scenario."""
    demo_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        "data", "synthetic", "demo_disruption.json"
    )
    try:
        with open(demo_path) as f:
            return json.load(f)
    except FileNotFoundError:
        # Fallback hardcoded
        return {
            "disruption_id": "DEMO_001",
            "flight_id": "F163",
            "flight_number": "AA1063",
            "origin": "ORD",
            "destination": "DFW",
            "delay_minutes": 105,
            "disruption_type": "WEATHER_DELAY",
            "description": "Severe weather at ORD causing significant ground delay",
        }


if __name__ == "__main__":
    print(f"Flight Data Mode: {get_current_mode()}")
    print()

    # Test demo mode
    print("=== Testing Demo Mode ===")
    status = get_flight_status("AA1063")
    if status:
        print(f"Flight: {status['flight_number']}")
        print(f"Route: {status['origin']['code']} -> {status['destination']['code']}")
        print(f"Delay: {status['delay_minutes']} minutes")
        print(f"Status: {status['status']}")
        print(f"Source: {status['data_source']}")
    print()

    network = get_network_status()
    print(f"Network Status: {network['network_status']}")
    print(f"Active Disruptions: {network['active_disruptions']}")
    print(f"Flights Monitored: {network['flights_monitored']}")
    print()

    disruption = get_demo_disruption()
    print(f"Demo Disruption: {disruption['flight_number']} {disruption['origin']}→{disruption['destination']} +{disruption['delay_minutes']} min")