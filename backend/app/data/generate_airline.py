"""
AirCrewAI — Synthetic Airline Data Generator
Generates a realistic but completely fictional airline operation for one simulated day.
All data is synthetic. No real airline crew, schedules, or operational data is used.
Seed = 42 for full reproducibility.
"""

import random
import json
import csv
import os
from datetime import datetime, timedelta

random.seed(42)

# ── AIRPORTS ──────────────────────────────────────────────────────────────────
AIRPORTS = [
    {"code": "ORD", "city": "Chicago",       "state": "IL", "lat": 41.97, "lon": -87.90, "congestion_index": 0.85, "is_hub": True},
    {"code": "DFW", "city": "Dallas",        "state": "TX", "lat": 32.89, "lon": -97.04, "congestion_index": 0.80, "is_hub": True},
    {"code": "CLT", "city": "Charlotte",     "state": "NC", "lat": 35.21, "lon": -80.94, "congestion_index": 0.70, "is_hub": True},
    {"code": "MIA", "city": "Miami",         "state": "FL", "lat": 25.79, "lon": -80.29, "congestion_index": 0.72, "is_hub": True},
    {"code": "PHX", "city": "Phoenix",       "state": "AZ", "lat": 33.43, "lon": -112.01, "congestion_index": 0.60, "is_hub": False},
    {"code": "LAX", "city": "Los Angeles",   "state": "CA", "lat": 33.94, "lon": -118.41, "congestion_index": 0.78, "is_hub": False},
    {"code": "JFK", "city": "New York",      "state": "NY", "lat": 40.64, "lon": -73.78, "congestion_index": 0.88, "is_hub": False},
    {"code": "BOS", "city": "Boston",        "state": "MA", "lat": 42.36, "lon": -71.01, "congestion_index": 0.75, "is_hub": False},
    {"code": "DEN", "city": "Denver",        "state": "CO", "lat": 39.85, "lon": -104.67, "congestion_index": 0.65, "is_hub": False},
    {"code": "SEA", "city": "Seattle",       "state": "WA", "lat": 47.45, "lon": -122.31, "congestion_index": 0.62, "is_hub": False},
    {"code": "ATL", "city": "Atlanta",       "state": "GA", "lat": 33.64, "lon": -84.43, "congestion_index": 0.82, "is_hub": False},
    {"code": "LGA", "city": "New York LGA",  "state": "NY", "lat": 40.77, "lon": -73.87, "congestion_index": 0.90, "is_hub": False},
]

AIRPORT_CODES = [a["code"] for a in AIRPORTS]
HUB_CODES = [a["code"] for a in AIRPORTS if a["is_hub"]]

# ── AIRCRAFT TYPES ─────────────────────────────────────────────────────────────
AIRCRAFT_TYPES = {
    "B737": {"name": "Boeing 737-800",  "capacity": 162, "belly_lbs": 45000, "min_crew": 2, "fa_count": 3},
    "B787": {"name": "Boeing 787-9",    "capacity": 296, "belly_lbs": 82000, "min_crew": 2, "fa_count": 6},
    "A320": {"name": "Airbus A320",     "capacity": 150, "belly_lbs": 38000, "min_crew": 2, "fa_count": 3},
    "A321": {"name": "Airbus A321",     "capacity": 185, "belly_lbs": 51000, "min_crew": 2, "fa_count": 4},
}

# ── CREW BASES ─────────────────────────────────────────────────────────────────
CREW_BASES = ["ORD", "DFW", "CLT", "MIA"]

# ── SIMULATED DAY ──────────────────────────────────────────────────────────────
SIM_DATE = datetime(2026, 8, 12, 0, 0, 0)


def minutes_to_time(base: datetime, minutes: int) -> str:
    return (base + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:00")


def generate_airports() -> list:
    return AIRPORTS


def generate_flights(n_flights: int = 150) -> list:
    flights = []
    flight_counter = 100

    # Route pairs — hub to hub and hub to spoke
    route_pairs = []
    for hub in HUB_CODES:
        for dest in AIRPORT_CODES:
            if dest != hub:
                route_pairs.append((hub, dest))
                route_pairs.append((dest, hub))

    random.shuffle(route_pairs)
    selected_routes = route_pairs[:n_flights]

    for i, (origin, dest) in enumerate(selected_routes):
        flight_id = f"F{flight_counter + i}"
        flight_num = f"AA{1000 + i}"

        # Departure spread across the day in minutes from midnight
        dep_minute = random.randint(5 * 60, 22 * 60)  # 5am to 10pm

        # Flight duration based on distance (simplified)
        duration = random.randint(90, 360)

        arr_minute = dep_minute + duration

        aircraft = random.choice(list(AIRCRAFT_TYPES.keys()))
        ac_info = AIRCRAFT_TYPES[aircraft]

        passenger_count = random.randint(
            int(ac_info["capacity"] * 0.65),
            int(ac_info["capacity"] * 0.95)
        )

        flights.append({
            "flight_id": flight_id,
            "flight_number": flight_num,
            "origin": origin,
            "destination": dest,
            "scheduled_departure": minutes_to_time(SIM_DATE, dep_minute),
            "scheduled_arrival": minutes_to_time(SIM_DATE, arr_minute),
            "actual_departure": None,
            "actual_arrival": None,
            "delay_minutes": 0,
            "aircraft_type": aircraft,
            "passenger_count": passenger_count,
            "status": "SCHEDULED",
            "cancellation_cost": random.randint(18000, 55000),
            "delay_cost_per_minute": random.randint(80, 150),
        })

    # Sort by departure time
    flights.sort(key=lambda x: x["scheduled_departure"])
    return flights


def generate_crew(n_crew: int = 250) -> list:
    crew = []
    crew_counter = 1

    roles = ["CAPTAIN", "FIRST_OFFICER", "FLIGHT_ATTENDANT"]
    role_weights = [0.25, 0.25, 0.50]

    for i in range(n_crew):
        crew_id = f"C{str(crew_counter + i).zfill(3)}"
        role = random.choices(roles, weights=role_weights)[0]
        base = random.choice(CREW_BASES)

        # Crew starts at their base or a nearby airport
        start_locations = [base] + random.sample(AIRPORT_CODES, 2)
        current_location = random.choice(start_locations)

        # Aircraft qualifications
        if role == "FLIGHT_ATTENDANT":
            qualifications = random.sample(list(AIRCRAFT_TYPES.keys()), random.randint(2, 4))
        else:
            qualifications = random.sample(list(AIRCRAFT_TYPES.keys()), random.randint(1, 2))

        # Duty tracking
        duty_start_minute = random.randint(4 * 60, 10 * 60)
        accumulated_duty = random.randint(0, 180)
        max_duty = 600  # 10 hours simulated max duty

        is_reserve = random.random() < 0.20  # 20% are reserve crew
        is_available = random.random() < 0.90  # 90% available

        crew.append({
            "crew_id": crew_id,
            "role": role,
            "base": base,
            "current_location": current_location,
            "aircraft_qualifications": qualifications,
            "duty_start": minutes_to_time(SIM_DATE, duty_start_minute),
            "accumulated_duty_minutes": accumulated_duty,
            "max_duty_minutes": max_duty,
            "min_rest_minutes": 480,  # 8 hours simulated minimum rest
            "reserve_status": is_reserve,
            "availability": is_available,
            "pairing_id": None,
        })

    return crew


def generate_assignments(flights: list, crew: list) -> list:
    assignments = []
    assignment_id = 1

    # Group crew by role
    captains = [c for c in crew if c["role"] == "CAPTAIN" and c["availability"] and not c["reserve_status"]]
    first_officers = [c for c in crew if c["role"] == "FIRST_OFFICER" and c["availability"] and not c["reserve_status"]]
    flight_attendants = [c for c in crew if c["role"] == "FLIGHT_ATTENDANT" and c["availability"] and not c["reserve_status"]]

    random.shuffle(captains)
    random.shuffle(first_officers)
    random.shuffle(flight_attendants)

    cap_idx = 0
    fo_idx = 0
    fa_idx = 0

    for flight in flights:
        ac_type = flight["aircraft_type"]
        ac_info = AIRCRAFT_TYPES[ac_type]
        dep_time = flight["scheduled_departure"]
        arr_time = flight["scheduled_arrival"]

        # Assign captain
        if cap_idx < len(captains):
            c = captains[cap_idx]
            cap_idx += 1
            report_time = (datetime.fromisoformat(dep_time) - timedelta(minutes=60)).strftime("%Y-%m-%dT%H:%M:00")
            assignments.append({
                "assignment_id": f"A{assignment_id}",
                "crew_id": c["crew_id"],
                "flight_id": flight["flight_id"],
                "role": "CAPTAIN",
                "report_time": report_time,
                "scheduled_release": arr_time,
                "connection_minutes": random.randint(35, 120),
                "sequence": 1,
            })
            assignment_id += 1

        # Assign first officer
        if fo_idx < len(first_officers):
            c = first_officers[fo_idx]
            fo_idx += 1
            report_time = (datetime.fromisoformat(dep_time) - timedelta(minutes=60)).strftime("%Y-%m-%dT%H:%M:00")
            assignments.append({
                "assignment_id": f"A{assignment_id}",
                "crew_id": c["crew_id"],
                "flight_id": flight["flight_id"],
                "role": "FIRST_OFFICER",
                "report_time": report_time,
                "scheduled_release": arr_time,
                "connection_minutes": random.randint(35, 120),
                "sequence": 1,
            })
            assignment_id += 1

        # Assign flight attendants
        for _ in range(ac_info["fa_count"]):
            if fa_idx < len(flight_attendants):
                c = flight_attendants[fa_idx]
                fa_idx += 1
                report_time = (datetime.fromisoformat(dep_time) - timedelta(minutes=45)).strftime("%Y-%m-%dT%H:%M:00")
                assignments.append({
                    "assignment_id": f"A{assignment_id}",
                    "crew_id": c["crew_id"],
                    "flight_id": flight["flight_id"],
                    "role": "FLIGHT_ATTENDANT",
                    "report_time": report_time,
                    "scheduled_release": arr_time,
                    "connection_minutes": random.randint(30, 90),
                    "sequence": 1,
                })
                assignment_id += 1

    return assignments


def generate_demo_disruption(flights: list, assignments: list, crew: list) -> dict:
    """
    The canonical demo scenario used during interviews.
    F102: ORD -> DFW, +105 minute delay.
    Always deterministic — does not depend on random state.
    """
    # Find the first ORD->DFW flight
    demo_flight = None
    for f in flights:
        if f["origin"] == "ORD" and f["destination"] == "DFW":
            demo_flight = f
            break

    if not demo_flight:
        # Fallback: use first flight
        demo_flight = flights[0]

    # Find crew assigned to this flight
    assigned = [a for a in assignments if a["flight_id"] == demo_flight["flight_id"]]
    assigned_crew_ids = [a["crew_id"] for a in assigned]

    return {
        "disruption_id": "DEMO_001",
        "flight_id": demo_flight["flight_id"],
        "flight_number": demo_flight["flight_number"],
        "origin": demo_flight["origin"],
        "destination": demo_flight["destination"],
        "delay_minutes": 105,
        "disruption_type": "WEATHER_DELAY",
        "description": "Severe weather at ORD causing significant ground delay",
        "scheduled_departure": demo_flight["scheduled_departure"],
        "assigned_crew_ids": assigned_crew_ids,
        "status": "ACTIVE",
    }


def save_data(output_dir: str, airports: list, flights: list,
              crew: list, assignments: list, disruption: dict):
    os.makedirs(output_dir, exist_ok=True)

    def save_json(data, filename):
        path = os.path.join(output_dir, filename)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Saved {filename} ({len(data) if isinstance(data, list) else 1} records)")

    def save_csv(data, filename):
        if not data:
            return
        path = os.path.join(output_dir, filename)
        keys = list(data[0].keys())
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for row in data:
                # Convert lists to strings for CSV
                row_copy = {}
                for k, v in row.items():
                    row_copy[k] = json.dumps(v) if isinstance(v, list) else v
                writer.writerow(row_copy)
        print(f"Saved {filename} ({len(data)} records)")

    save_json(airports, "airports.json")
    save_json(flights, "flights.json")
    save_json(crew, "crew.json")
    save_json(assignments, "assignments.json")
    save_json(disruption, "demo_disruption.json")

    save_csv(airports, "airports.csv")
    save_csv(flights, "flights.csv")
    save_csv(crew, "crew.csv")
    save_csv(assignments, "assignments.csv")


def generate_all(output_dir: str = None):
    if output_dir is None:
        # Works from both backend/ and root
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        output_dir = os.path.join(base, "data", "synthetic")

    print("=== AirCrewAI Synthetic Data Generator ===")
    print(f"Seed: 42 | Simulated date: {SIM_DATE.date()}")
    print()

    airports = generate_airports()
    print(f"Airports: {len(airports)}")

    flights = generate_flights(150)
    print(f"Flights: {len(flights)}")

    crew = generate_crew(250)
    reserves = sum(1 for c in crew if c["reserve_status"])
    print(f"Crew: {len(crew)} ({reserves} reserve)")

    assignments = generate_assignments(flights, crew)
    print(f"Assignments: {len(assignments)}")

    disruption = generate_demo_disruption(flights, assignments, crew)
    print(f"Demo disruption: {disruption['flight_id']} {disruption['origin']} -> {disruption['destination']} +{disruption['delay_minutes']} min")

    save_data(output_dir, airports, flights, crew, assignments, disruption)

    print()
    print("=== Summary ===")
    print(f"Airports: {len(airports)}")
    print(f"Flights:  {len(flights)}")
    print(f"Crew:     {len(crew)} ({reserves} reserve, {len(crew)-reserves} active)")
    print(f"Assignments: {len(assignments)}")
    print(f"Demo flight: {disruption['flight_number']} {disruption['origin']}→{disruption['destination']}")
    print()
    print("All files saved to data/synthetic/")
    return airports, flights, crew, assignments, disruption


if __name__ == "__main__":
    generate_all()