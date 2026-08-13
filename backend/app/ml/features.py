"""
AirCrewAI — Feature Engineering for Crew Misconnect Prediction
Generates training data and extracts features from the synthetic airline schedule.
All data is synthetic. Labels are generated using realistic operational thresholds.
"""

import json
import os
import random
import numpy as np
import pandas as pd
from datetime import datetime

random.seed(42)
np.random.seed(42)

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "data", "synthetic"
)


def load_synthetic_data():
    """Load all synthetic airline data files."""
    with open(os.path.join(DATA_DIR, "flights.json")) as f:
        flights = json.load(f)
    with open(os.path.join(DATA_DIR, "crew.json")) as f:
        crew = json.load(f)
    with open(os.path.join(DATA_DIR, "assignments.json")) as f:
        assignments = json.load(f)
    with open(os.path.join(DATA_DIR, "airports.json")) as f:
        airports = json.load(f)

    flights_map = {f["flight_id"]: f for f in flights}
    crew_map = {c["crew_id"]: c for c in crew}
    airports_map = {a["code"]: a for a in airports}

    return flights, crew, assignments, airports, flights_map, crew_map, airports_map


def extract_hour(time_str: str) -> int:
    """Extract hour of day from ISO datetime string."""
    try:
        return datetime.fromisoformat(time_str).hour
    except Exception:
        return 12


def generate_training_data(n_samples: int = 5000) -> pd.DataFrame:
    """
    Generate synthetic training data for crew misconnect prediction.

    Each row represents one crew connection scenario.
    Label (misconnect=1) is generated using realistic operational thresholds:
    - High inbound delay + short connection time = high misconnect probability
    - We add noise to make the problem non-trivial

    This is synthetic training data. No real airline operational data is used.
    """
    flights, crew, assignments, airports, flights_map, crew_map, airports_map = load_synthetic_data()

    rows = []

    for _ in range(n_samples):
        # Sample a random crew member
        c = random.choice(crew)
        crew_id = c["crew_id"]

        # Sample a random inbound flight
        inbound = random.choice(list(flights_map.values()))
        # Sample a random outbound flight (next assignment)
        outbound = random.choice(list(flights_map.values()))

        if inbound["flight_id"] == outbound["flight_id"]:
            continue

        # Features
        inbound_delay = random.choices(
            [0, random.randint(1, 30), random.randint(31, 90), random.randint(91, 180)],
            weights=[0.55, 0.20, 0.15, 0.10]
        )[0]

        scheduled_connection_minutes = random.randint(25, 150)
        effective_connection_minutes = max(0, scheduled_connection_minutes - inbound_delay)

        airport_code = inbound["destination"]
        airport_info = airports_map.get(airport_code, {})
        congestion_index = airport_info.get("congestion_index", 0.5)
        is_hub = 1 if airport_info.get("is_hub", False) else 0

        hour_of_day = extract_hour(outbound["scheduled_departure"])
        # Peak hours: 6-9am and 4-7pm are busier
        is_peak_hour = 1 if (6 <= hour_of_day <= 9 or 16 <= hour_of_day <= 19) else 0

        accumulated_duty = c["accumulated_duty_minutes"]
        max_duty = c["max_duty_minutes"]
        remaining_duty = max_duty - accumulated_duty

        legs_flown_today = random.randint(0, 4)

        # Aircraft type match
        outbound_aircraft = outbound["aircraft_type"]
        crew_quals = c.get("aircraft_qualifications", [])
        aircraft_qualified = 1 if outbound_aircraft in crew_quals else 0

        # Turnaround time proxy (gate-to-gate)
        turnaround_time = random.randint(30, 90)

        # Weather severity at origin (simulated)
        weather_severity = random.choices(
            [0, 1, 2, 3],
            weights=[0.60, 0.20, 0.12, 0.08]
        )[0]

        # Network congestion (how many other flights are delayed)
        network_congestion = random.uniform(0, 1)

        # ── LABEL GENERATION ──────────────────────────────────────────────
        # Misconnect probability based on realistic operational factors
        # This is a deterministic function with noise, not real airline data

        base_prob = 0.05  # baseline 5% misconnect rate

        # Inbound delay is the strongest driver
        if inbound_delay > 90:
            base_prob += 0.60
        elif inbound_delay > 60:
            base_prob += 0.40
        elif inbound_delay > 30:
            base_prob += 0.20
        elif inbound_delay > 15:
            base_prob += 0.10

        # Short connection time increases risk dramatically
        if effective_connection_minutes < 20:
            base_prob += 0.45
        elif effective_connection_minutes < 35:
            base_prob += 0.25
        elif effective_connection_minutes < 50:
            base_prob += 0.10

        # Airport congestion
        base_prob += congestion_index * 0.15

        # Hub airports are more complex to navigate
        base_prob += is_hub * 0.05

        # Peak hours add complexity
        base_prob += is_peak_hour * 0.05

        # High duty accumulation increases fatigue risk
        if remaining_duty < 120:
            base_prob += 0.10
        elif remaining_duty < 60:
            base_prob += 0.20

        # Many legs today increases risk
        base_prob += min(legs_flown_today * 0.04, 0.15)

        # Not qualified for aircraft = certain misconnect (can't legally operate)
        if not aircraft_qualified:
            base_prob += 0.50

        # Weather severity
        base_prob += weather_severity * 0.08

        # Network congestion
        base_prob += network_congestion * 0.08

        # Add noise
        base_prob += random.uniform(-0.05, 0.05)
        base_prob = max(0.0, min(1.0, base_prob))

        # Convert to binary label
        misconnect = 1 if random.random() < base_prob else 0

        rows.append({
            "crew_id": crew_id,
            "inbound_flight_id": inbound["flight_id"],
            "outbound_flight_id": outbound["flight_id"],
            "inbound_delay_minutes": inbound_delay,
            "scheduled_connection_minutes": scheduled_connection_minutes,
            "effective_connection_minutes": effective_connection_minutes,
            "airport_congestion_index": congestion_index,
            "is_hub_airport": is_hub,
            "hour_of_day": hour_of_day,
            "is_peak_hour": is_peak_hour,
            "accumulated_duty_minutes": accumulated_duty,
            "remaining_duty_minutes": remaining_duty,
            "legs_flown_today": legs_flown_today,
            "aircraft_qualified": aircraft_qualified,
            "turnaround_time": turnaround_time,
            "weather_severity": weather_severity,
            "network_congestion": network_congestion,
            "misconnect": misconnect,
        })

    df = pd.DataFrame(rows)
    print(f"Generated {len(df)} training samples")
    print(f"Misconnect rate: {df['misconnect'].mean():.1%}")
    print(f"Features: {[c for c in df.columns if c not in ['crew_id', 'inbound_flight_id', 'outbound_flight_id', 'misconnect']]}")
    return df


def get_feature_columns() -> list:
    """Return the list of feature columns used for training."""
    return [
        "inbound_delay_minutes",
        "scheduled_connection_minutes",
        "effective_connection_minutes",
        "airport_congestion_index",
        "is_hub_airport",
        "hour_of_day",
        "is_peak_hour",
        "accumulated_duty_minutes",
        "remaining_duty_minutes",
        "legs_flown_today",
        "aircraft_qualified",
        "turnaround_time",
        "weather_severity",
        "network_congestion",
    ]


def build_crew_features(crew_id: str, inbound_delay: int,
                         connection_minutes: int, outbound_flight_id: str,
                         flights_map: dict, crew_map: dict, airports_map: dict) -> dict:
    """
    Build feature vector for a single crew connection at inference time.
    Used by the FastAPI prediction endpoint.
    """
    crew = crew_map.get(crew_id, {})
    outbound = flights_map.get(outbound_flight_id, {})

    airport_code = outbound.get("origin", "ORD")
    airport_info = airports_map.get(airport_code, {})
    congestion_index = airport_info.get("congestion_index", 0.5)
    is_hub = 1 if airport_info.get("is_hub", False) else 0

    dep_time = outbound.get("scheduled_departure", "2026-08-12T12:00:00")
    hour_of_day = extract_hour(dep_time)
    is_peak_hour = 1 if (6 <= hour_of_day <= 9 or 16 <= hour_of_day <= 19) else 0

    accumulated_duty = crew.get("accumulated_duty_minutes", 0)
    max_duty = crew.get("max_duty_minutes", 600)
    remaining_duty = max_duty - accumulated_duty

    outbound_aircraft = outbound.get("aircraft_type", "B737")
    crew_quals = crew.get("aircraft_qualifications", [])
    aircraft_qualified = 1 if outbound_aircraft in crew_quals else 0

    effective_connection = max(0, connection_minutes - inbound_delay)

    return {
        "inbound_delay_minutes": inbound_delay,
        "scheduled_connection_minutes": connection_minutes,
        "effective_connection_minutes": effective_connection,
        "airport_congestion_index": congestion_index,
        "is_hub_airport": is_hub,
        "hour_of_day": hour_of_day,
        "is_peak_hour": is_peak_hour,
        "accumulated_duty_minutes": accumulated_duty,
        "remaining_duty_minutes": remaining_duty,
        "legs_flown_today": 2,  # default assumption
        "aircraft_qualified": aircraft_qualified,
        "turnaround_time": 45,  # default assumption
        "weather_severity": 2 if inbound_delay > 60 else 1 if inbound_delay > 20 else 0,
        "network_congestion": min(inbound_delay / 120.0, 1.0),
    }


if __name__ == "__main__":
    df = generate_training_data(5000)
    print()
    print(df.describe())
    print()
    print("Class distribution:")
    print(df["misconnect"].value_counts())
