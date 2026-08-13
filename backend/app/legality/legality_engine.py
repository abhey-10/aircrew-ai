"""
AirCrewAI — Crew Legality Engine
Deterministic rule-based checker for simulated crew operating constraints.

IMPORTANT: These rules are SIMULATED and ILLUSTRATIVE only.
They do NOT represent real FAA regulations, any airline's actual operating rules,
or American Airlines policy. They exist solely to demonstrate the concept of
deterministic legality validation in a portfolio project.

The legality engine is AUTHORITATIVE within the simulated environment.
The LLM may explain its output but must NEVER override it.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "data", "synthetic"
)

# ── SIMULATED CREW RULES ───────────────────────────────────────────────────────
# These are illustrative rules for demonstration purposes only.

SIMULATED_RULES = {
    "QUAL_01": {
        "description": "Crew must hold qualification for the assigned aircraft type",
        "category": "qualification",
    },
    "AVAIL_01": {
        "description": "Crew must be marked as available and not on another assignment",
        "category": "availability",
    },
    "LOC_01": {
        "description": "Crew must be physically located at the departure airport",
        "category": "location",
    },
    "CONN_01": {
        "description": "Minimum simulated connection time of 30 minutes must be satisfied",
        "category": "connection",
        "threshold_minutes": 30,
    },
    "DUTY_01": {
        "description": "Simulated maximum duty time of 600 minutes must not be exceeded",
        "category": "duty",
        "max_duty_minutes": 600,
    },
    "REST_01": {
        "description": "Simulated minimum rest of 480 minutes must be observed between duty periods",
        "category": "rest",
        "min_rest_minutes": 480,
    },
    "ROLE_01": {
        "description": "Crew role must match flight requirements (CAPTAIN or FIRST_OFFICER for flight deck)",
        "category": "role",
    },
    "RESERVE_01": {
        "description": "Reserve crew can only be activated when flagged as available",
        "category": "reserve",
    },
}


def load_data():
    with open(os.path.join(DATA_DIR, "flights.json")) as f:
        flights = json.load(f)
    with open(os.path.join(DATA_DIR, "crew.json")) as f:
        crew = json.load(f)
    flights_map = {f["flight_id"]: f for f in flights}
    crew_map = {c["crew_id"]: c for c in crew}
    return flights_map, crew_map


def check_crew_legality(
    crew_id: str,
    flight_id: str,
    inbound_delay: int = 0,
    connection_minutes: int = 45,
    flights_map: Optional[dict] = None,
    crew_map: Optional[dict] = None,
) -> dict:
    """
    Deterministic legality check for a crew-flight assignment.

    Args:
        crew_id: The crew member to check
        flight_id: The flight to assign them to
        inbound_delay: How many minutes their inbound flight was delayed
        connection_minutes: Scheduled connection time available
        flights_map: Optional pre-loaded flights dict
        crew_map: Optional pre-loaded crew dict

    Returns:
        dict with legal bool, violations list, passed rules list, explanation
    """
    if flights_map is None or crew_map is None:
        flights_map, crew_map = load_data()

    crew = crew_map.get(crew_id)
    flight = flights_map.get(flight_id)

    violations = []
    passed = []
    warnings = []

    if not crew:
        return {
            "crew_id": crew_id,
            "flight_id": flight_id,
            "legal": False,
            "violations": [{"rule_id": "DATA_01", "description": f"Crew {crew_id} not found"}],
            "passed_rules": [],
            "warnings": [],
            "explanation": f"Crew member {crew_id} does not exist in the simulated roster.",
        }

    if not flight:
        return {
            "crew_id": crew_id,
            "flight_id": flight_id,
            "legal": False,
            "violations": [{"rule_id": "DATA_02", "description": f"Flight {flight_id} not found"}],
            "passed_rules": [],
            "warnings": [],
            "explanation": f"Flight {flight_id} does not exist in the simulated schedule.",
        }

    aircraft_type = flight.get("aircraft_type", "B737")
    crew_quals = crew.get("aircraft_qualifications", [])
    crew_role = crew.get("role", "UNKNOWN")
    crew_location = crew.get("current_location", "UNKNOWN")
    flight_origin = flight.get("origin", "UNKNOWN")
    crew_available = crew.get("availability", False)
    crew_is_reserve = crew.get("reserve_status", False)
    accumulated_duty = crew.get("accumulated_duty_minutes", 0)
    max_duty = crew.get("max_duty_minutes", 600)

    # Estimate flight duration from scheduled times
    try:
        dep = datetime.fromisoformat(flight.get("scheduled_departure", "2026-08-12T12:00:00"))
        arr = datetime.fromisoformat(flight.get("scheduled_arrival", "2026-08-12T14:00:00"))
        flight_duration = int((arr - dep).total_seconds() / 60)
    except Exception:
        flight_duration = 120

    # ── RULE: QUAL_01 ─────────────────────────────────────────────────────────
    if aircraft_type in crew_quals:
        passed.append({
            "rule_id": "QUAL_01",
            "description": SIMULATED_RULES["QUAL_01"]["description"],
            "detail": f"Crew qualified for {aircraft_type}",
        })
    else:
        violations.append({
            "rule_id": "QUAL_01",
            "description": SIMULATED_RULES["QUAL_01"]["description"],
            "detail": f"Crew qualified for {crew_quals} but flight requires {aircraft_type}",
        })

    # ── RULE: AVAIL_01 ────────────────────────────────────────────────────────
    if crew_available:
        passed.append({
            "rule_id": "AVAIL_01",
            "description": SIMULATED_RULES["AVAIL_01"]["description"],
            "detail": "Crew marked as available",
        })
    else:
        violations.append({
            "rule_id": "AVAIL_01",
            "description": SIMULATED_RULES["AVAIL_01"]["description"],
            "detail": "Crew not available (on another assignment or unavailable)",
        })

    # ── RULE: LOC_01 ──────────────────────────────────────────────────────────
    if crew_location == flight_origin:
        passed.append({
            "rule_id": "LOC_01",
            "description": SIMULATED_RULES["LOC_01"]["description"],
            "detail": f"Crew at {crew_location}, flight departs from {flight_origin}",
        })
    else:
        violations.append({
            "rule_id": "LOC_01",
            "description": SIMULATED_RULES["LOC_01"]["description"],
            "detail": f"Crew at {crew_location}, flight departs from {flight_origin} — repositioning required",
        })

    # ── RULE: CONN_01 ─────────────────────────────────────────────────────────
    min_connection = SIMULATED_RULES["CONN_01"]["threshold_minutes"]
    effective_connection = connection_minutes - inbound_delay

    if effective_connection >= min_connection:
        passed.append({
            "rule_id": "CONN_01",
            "description": SIMULATED_RULES["CONN_01"]["description"],
            "detail": f"Effective connection time: {effective_connection} min (minimum: {min_connection} min)",
        })
    else:
        violations.append({
            "rule_id": "CONN_01",
            "description": SIMULATED_RULES["CONN_01"]["description"],
            "detail": f"Effective connection: {effective_connection} min after {inbound_delay} min delay (minimum: {min_connection} min)",
        })

    # ── RULE: DUTY_01 ─────────────────────────────────────────────────────────
    projected_duty = accumulated_duty + flight_duration
    max_duty_rule = SIMULATED_RULES["DUTY_01"]["max_duty_minutes"]

    if projected_duty <= max_duty_rule:
        passed.append({
            "rule_id": "DUTY_01",
            "description": SIMULATED_RULES["DUTY_01"]["description"],
            "detail": f"Projected duty: {projected_duty} min (maximum: {max_duty_rule} min)",
        })
    else:
        violations.append({
            "rule_id": "DUTY_01",
            "description": SIMULATED_RULES["DUTY_01"]["description"],
            "detail": f"Projected duty: {projected_duty} min would exceed simulated maximum of {max_duty_rule} min",
            "current_duty": accumulated_duty,
            "flight_duration": flight_duration,
            "max_duty": max_duty_rule,
            "overage": projected_duty - max_duty_rule,
        })

    # ── RULE: ROLE_01 ─────────────────────────────────────────────────────────
    valid_roles = ["CAPTAIN", "FIRST_OFFICER", "FLIGHT_ATTENDANT"]
    if crew_role in valid_roles:
        passed.append({
            "rule_id": "ROLE_01",
            "description": SIMULATED_RULES["ROLE_01"]["description"],
            "detail": f"Crew role: {crew_role}",
        })
    else:
        violations.append({
            "rule_id": "ROLE_01",
            "description": SIMULATED_RULES["ROLE_01"]["description"],
            "detail": f"Unknown crew role: {crew_role}",
        })

    # ── RULE: RESERVE_01 ──────────────────────────────────────────────────────
    if crew_is_reserve:
        if crew_available:
            passed.append({
                "rule_id": "RESERVE_01",
                "description": SIMULATED_RULES["RESERVE_01"]["description"],
                "detail": "Reserve crew is available for activation",
            })
        else:
            violations.append({
                "rule_id": "RESERVE_01",
                "description": SIMULATED_RULES["RESERVE_01"]["description"],
                "detail": "Reserve crew is not available for activation",
            })
    else:
        passed.append({
            "rule_id": "RESERVE_01",
            "description": "Not applicable — crew is not on reserve status",
            "detail": "Active crew member",
        })

    # ── ADD WARNINGS ──────────────────────────────────────────────────────────
    if effective_connection < 45 and effective_connection >= min_connection:
        warnings.append({
            "rule_id": "CONN_WARN",
            "detail": f"Connection time {effective_connection} min is tight — above minimum but below recommended 45 min",
        })

    remaining_duty = max_duty_rule - projected_duty
    if remaining_duty < 60:
        warnings.append({
            "rule_id": "DUTY_WARN",
            "detail": f"Only {remaining_duty} min of simulated duty remaining after this assignment",
        })

    is_legal = len(violations) == 0

    # Build explanation
    if is_legal:
        explanation = (
            f"Crew {crew_id} is LEGAL to operate flight {flight_id}. "
            f"All {len(passed)} simulated rules passed. "
            f"Aircraft qualification: {aircraft_type}. "
            f"Effective connection: {effective_connection} min. "
            f"Projected duty: {projected_duty} min."
        )
    else:
        violation_summary = "; ".join([v["rule_id"] for v in violations])
        explanation = (
            f"Crew {crew_id} is ILLEGAL for flight {flight_id}. "
            f"Violated simulated rules: {violation_summary}. "
            f"{violations[0]['detail']}"
        )

    return {
        "crew_id": crew_id,
        "flight_id": flight_id,
        "legal": is_legal,
        "violations": violations,
        "passed_rules": passed,
        "warnings": warnings,
        "explanation": explanation,
        "summary": {
            "aircraft_type": aircraft_type,
            "crew_location": crew_location,
            "flight_origin": flight_origin,
            "effective_connection_minutes": effective_connection,
            "projected_duty_minutes": projected_duty,
            "is_reserve": crew_is_reserve,
        },
        "note": "All rules are SIMULATED and ILLUSTRATIVE only. Not real airline regulations.",
    }


def check_multiple_candidates(candidates: list, flight_id: str,
                               inbound_delay: int = 0,
                               flights_map: Optional[dict] = None,
                               crew_map: Optional[dict] = None) -> list:
    """
    Check legality for multiple candidate crew members.
    Returns sorted list with legal candidates first.
    """
    if flights_map is None or crew_map is None:
        flights_map, crew_map = load_data()

    results = []
    for crew_id in candidates:
        crew = crew_map.get(crew_id, {})
        connection_mins = 45  # default
        result = check_crew_legality(
            crew_id=crew_id,
            flight_id=flight_id,
            inbound_delay=inbound_delay,
            connection_minutes=connection_mins,
            flights_map=flights_map,
            crew_map=crew_map,
        )
        result["crew_role"] = crew.get("role", "UNKNOWN")
        result["crew_base"] = crew.get("base", "UNKNOWN")
        result["is_reserve"] = crew.get("reserve_status", False)
        results.append(result)

    results.sort(key=lambda x: (not x["legal"], len(x["violations"])))
    return results


if __name__ == "__main__":
    print("=== AirCrewAI — Crew Legality Engine ===")
    print("NOTE: All rules are SIMULATED and ILLUSTRATIVE only.")
    print()

    flights_map, crew_map = load_data()

    # Load demo disruption
    demo_path = os.path.join(DATA_DIR, "demo_disruption.json")
    with open(demo_path) as f:
        demo = json.load(f)

    flight_id = demo["flight_id"]
    delay = demo["delay_minutes"]
    assigned_crew = demo.get("assigned_crew_ids", [])

    print(f"Demo flight: {demo['flight_number']} {demo['origin']}→{demo['destination']} +{delay} min")
    print()

    # Test legality for assigned crew
    if assigned_crew:
        crew_id = assigned_crew[0]
        print(f"Checking legality: {crew_id} for flight {flight_id}")
        result = check_crew_legality(
            crew_id=crew_id,
            flight_id=flight_id,
            inbound_delay=delay,
            connection_minutes=45,
            flights_map=flights_map,
            crew_map=crew_map,
        )

        print(f"Legal: {result['legal']}")
        if result["violations"]:
            print("Violations:")
            for v in result["violations"]:
                print(f"  FAIL {v['rule_id']}: {v['detail']}")
        print("Passed rules:")
        for p in result["passed_rules"]:
            print(f"  PASS {p['rule_id']}: {p['detail']}")
        print()
        print(f"Explanation: {result['explanation']}")
    else:
        print("No assigned crew found in demo disruption.")

    # Test a few random crew members
    print()
    print("Checking 5 random crew members against the demo flight:")
    import random
    random.seed(42)
    sample_crew = random.sample(list(crew_map.keys()), 5)

    for crew_id in sample_crew:
        result = check_crew_legality(
            crew_id=crew_id,
            flight_id=flight_id,
            inbound_delay=0,
            connection_minutes=60,
            flights_map=flights_map,
            crew_map=crew_map,
        )
        status = "LEGAL" if result["legal"] else f"ILLEGAL ({', '.join([v['rule_id'] for v in result['violations']])})"
        print(f"  {crew_id}: {status}")
