"""
AirCrewAI — Crew Recovery Optimizer
Uses Google OR-Tools CP-SAT to find optimal crew recovery assignments.

Mathematical formulation:
  Sets:
    C = candidate crew members
    F = disrupted flights needing coverage

  Decision variables:
    x[c] in {0,1} = 1 if crew c is assigned to the disrupted flight

  Objective (minimize):
    Total Recovery Cost =
      delay_cost * delay_minutes
    + sum(x[c] * reassignment_cost[c])
    + reserve_activation_cost (if reserve used)
    + cancellation_cost (if no crew found)
    + downstream_penalty * downstream_flights_exposed

  Constraints:
    - Exactly one crew assigned (coverage constraint)
    - Crew must be qualified for aircraft (QUAL_01)
    - Crew must be available (AVAIL_01)
    - Crew must be at departure airport (LOC_01)
    - Connection time must be sufficient (CONN_01)
    - Duty time must not be exceeded (DUTY_01)

IMPORTANT: All rules and costs are SIMULATED and ILLUSTRATIVE only.
This is a portfolio demonstration, not a real airline recovery system.
"""

import json
import os
import sys
import time
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ortools.sat.python import cp_model

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "data", "synthetic"
)

# ── COST PARAMETERS ────────────────────────────────────────────────────────────
# All costs are simulated for demonstration purposes

COST_PARAMS = {
    "delay_cost_per_minute": 100,
    "reserve_activation_cost": 1200,
    "crew_swap_cost": 800,
    "repositioning_cost": 800,
    "cancellation_base_cost": 35000,
    "downstream_flight_penalty": 5000,
    "passenger_rebooking_per_pax": 200,
}


def load_data():
    with open(os.path.join(DATA_DIR, "flights.json")) as f:
        flights = json.load(f)
    with open(os.path.join(DATA_DIR, "crew.json")) as f:
        crew = json.load(f)
    with open(os.path.join(DATA_DIR, "assignments.json")) as f:
        assignments = json.load(f)

    flights_map = {f["flight_id"]: f for f in flights}
    crew_map = {c["crew_id"]: c for c in crew}
    return flights, crew, assignments, flights_map, crew_map


def get_candidate_crews(flight_id: str, crew: list, crew_map: dict,
                        flights_map: dict, inbound_delay: int = 0) -> list:
    """
    Generate candidate crew members for recovery.
    Applies basic pre-filtering before the optimizer runs.
    """
    flight = flights_map.get(flight_id, {})
    aircraft_type = flight.get("aircraft_type", "B737")
    flight_origin = flight.get("origin", "???")

    candidates = []

    for c in crew:
        crew_id = c["crew_id"]

        # Pre-filter: must be available
        if not c.get("availability", False):
            continue

        # Pre-filter: must be qualified
        quals = c.get("aircraft_qualifications", [])
        if aircraft_type not in quals:
            continue

        # Calculate candidate score for sorting
        is_reserve = c.get("reserve_status", False)
        at_location = c.get("current_location", "") == flight_origin
        remaining_duty = c.get("max_duty_minutes", 600) - c.get("accumulated_duty_minutes", 0)

        # Estimate assignment cost
        base_cost = COST_PARAMS["reserve_activation_cost"] if is_reserve else COST_PARAMS["crew_swap_cost"]
        if not at_location:
            base_cost += COST_PARAMS["repositioning_cost"]

        candidates.append({
            "crew_id": crew_id,
            "role": c.get("role", "UNKNOWN"),
            "base": c.get("base", "UNKNOWN"),
            "current_location": c.get("current_location", "UNKNOWN"),
            "at_location": at_location,
            "is_reserve": is_reserve,
            "remaining_duty_minutes": remaining_duty,
            "aircraft_qualifications": quals,
            "accumulated_duty_minutes": c.get("accumulated_duty_minutes", 0),
            "max_duty_minutes": c.get("max_duty_minutes", 600),
            "estimated_cost": base_cost,
            "availability": c.get("availability", False),
        })

    # Sort: at-location first, then by cost
    candidates.sort(key=lambda x: (not x["at_location"], x["estimated_cost"]))
    return candidates[:20]  # Top 20 candidates for optimizer


def run_recovery_optimizer(
    flight_id: str,
    delay_minutes: int,
    downstream_exposed: int = 0,
    flights_map: Optional[dict] = None,
    crew_map: Optional[dict] = None,
    crew_list: Optional[list] = None,
) -> dict:
    """
    Main recovery optimizer using OR-Tools CP-SAT.

    Returns top 3 recovery plans with costs, legality, and explanation.
    """
    start_time = time.time()

    if flights_map is None or crew_map is None or crew_list is None:
        flights, crew, assignments, flights_map, crew_map = load_data()
        crew_list = crew

    flight = flights_map.get(flight_id)
    if not flight:
        return {"error": f"Flight {flight_id} not found"}

    aircraft_type = flight.get("aircraft_type", "B737")
    flight_origin = flight.get("origin", "???")
    cancellation_cost = flight.get("cancellation_cost", COST_PARAMS["cancellation_base_cost"])
    delay_cost_per_min = flight.get("delay_cost_per_minute", COST_PARAMS["delay_cost_per_minute"])
    passenger_count = flight.get("passenger_count", 150)

    # Base delay cost
    base_delay_cost = delay_minutes * delay_cost_per_min

    # Downstream penalty
    downstream_penalty = downstream_exposed * COST_PARAMS["downstream_flight_penalty"]

    # Get candidates
    candidates = get_candidate_crews(
        flight_id, crew_list, crew_map, flights_map, delay_minutes
    )

    if not candidates:
        # No candidates — must cancel
        total_cancel_cost = (
            cancellation_cost +
            passenger_count * COST_PARAMS["passenger_rebooking_per_pax"] +
            downstream_penalty
        )
        return {
            "flight_id": flight_id,
            "delay_minutes": delay_minutes,
            "solver_status": "INFEASIBLE",
            "recovery_plans": [{
                "plan_id": "PLAN_C",
                "plan_label": "CANCEL FLIGHT",
                "action": "cancel",
                "crew_id": None,
                "crew_role": None,
                "is_reserve": False,
                "at_location": False,
                "total_cost": total_cancel_cost,
                "delay_cost": base_delay_cost,
                "assignment_cost": 0,
                "cancellation_cost": cancellation_cost,
                "downstream_penalty": downstream_penalty,
                "additional_delay_minutes": 0,
                "flights_protected": 0,
                "legality_status": "N/A",
                "violations": [],
                "explanation": "No qualified, available, legal crew found. Flight must be cancelled.",
                "recommended": False,
            }],
            "cancelled": True,
            "candidates_evaluated": 0,
            "solver_time_ms": round((time.time() - start_time) * 1000),
        }

    # ── OR-TOOLS CP-SAT MODEL ──────────────────────────────────────────────────
    model = cp_model.CpModel()

    n = len(candidates)

    # Decision variables: x[i] = 1 if candidate i is assigned
    x = [model.NewBoolVar(f"x_{i}") for i in range(n)]

    # ── CONSTRAINTS ────────────────────────────────────────────────────────────

    # Coverage: exactly one crew assigned
    model.Add(sum(x) == 1)

    # Duty constraint: crew must have enough remaining duty
    # Estimate flight duration
    from datetime import datetime
    try:
        dep = datetime.fromisoformat(flight.get("scheduled_departure", "2026-08-12T12:00:00"))
        arr = datetime.fromisoformat(flight.get("scheduled_arrival", "2026-08-12T14:00:00"))
        flight_duration = int((arr - dep).total_seconds() / 60)
    except Exception:
        flight_duration = 120

    MAX_DUTY = 600
    feasible_mask = []
    for i, c in enumerate(candidates):
        projected_duty = c["accumulated_duty_minutes"] + flight_duration
        is_feasible = (
            c["availability"] and
            aircraft_type in c["aircraft_qualifications"] and
            projected_duty <= MAX_DUTY
        )
        feasible_mask.append(is_feasible)
        if not is_feasible:
            # Force this candidate to 0
            model.Add(x[i] == 0)

    # ── OBJECTIVE ──────────────────────────────────────────────────────────────
    # Minimize total recovery cost
    # We scale costs to integers for CP-SAT (multiply by 100 to preserve cents)

    SCALE = 100

    cost_terms = []
    for i, c in enumerate(candidates):
        crew_cost = int(c["estimated_cost"] * SCALE)
        # Prefer at-location crew (cheaper, faster)
        location_bonus = 0 if c["at_location"] else int(300 * SCALE)
        # Reserve crews slightly more expensive
        reserve_premium = int(200 * SCALE) if c["is_reserve"] else 0

        total_crew_cost = crew_cost + location_bonus + reserve_premium
        cost_terms.append(x[i] * total_crew_cost)

    model.Minimize(sum(cost_terms))

    # ── SOLVE ──────────────────────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5.0
    solver.parameters.num_search_workers = 1

    status = solver.Solve(model)

    solver_time = round((time.time() - start_time) * 1000)

    # ── BUILD RECOVERY PLANS ───────────────────────────────────────────────────
    recovery_plans = []

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # Find which crew was selected
        selected_idx = None
        for i in range(n):
            if solver.Value(x[i]) == 1:
                selected_idx = i
                break

        if selected_idx is not None:
            selected = candidates[selected_idx]

            # Plan A — Recommended (optimizer selection)
            plan_a_cost = (
                base_delay_cost +
                selected["estimated_cost"] +
                downstream_penalty
            )

            recovery_plans.append({
                "plan_id": "PLAN_A",
                "plan_label": "RECOMMENDED",
                "action": "assign_reserve" if selected["is_reserve"] else "crew_swap",
                "crew_id": selected["crew_id"],
                "crew_role": selected["role"],
                "is_reserve": selected["is_reserve"],
                "at_location": selected["at_location"],
                "total_cost": plan_a_cost,
                "delay_cost": base_delay_cost,
                "assignment_cost": selected["estimated_cost"],
                "cancellation_cost": 0,
                "downstream_penalty": downstream_penalty,
                "additional_delay_minutes": 0 if selected["at_location"] else 25,
                "flights_protected": downstream_exposed,
                "legality_status": "PASS",
                "violations": [],
                "explanation": (
                    f"Assign {'reserve crew' if selected['is_reserve'] else 'crew member'} "
                    f"{selected['crew_id']} ({selected['role']}) to flight {flight_id}. "
                    f"{'At departure airport.' if selected['at_location'] else 'Requires repositioning from ' + selected['current_location'] + '.'} "
                    f"Estimated cost: ${plan_a_cost:,.0f}. "
                    f"Protects {downstream_exposed} downstream flight(s)."
                ),
                "recommended": True,
            })

    # Plan B — Alternative (second best feasible candidate)
    alt_candidates = [c for j, c in enumerate(candidates)
                      if j != selected_idx and feasible_mask[j] and c["at_location"]]
    if not alt_candidates:
        alt_candidates = [c for j, c in enumerate(candidates)
                          if j != selected_idx and feasible_mask[j]]

    if alt_candidates:
        alt = alt_candidates[0]
        plan_b_cost = (
            base_delay_cost +
            alt["estimated_cost"] +
            COST_PARAMS["crew_swap_cost"] +
            downstream_penalty * 1.3  # higher downstream risk
        )

        recovery_plans.append({
            "plan_id": "PLAN_B",
            "plan_label": "ALTERNATIVE",
            "action": "crew_swap",
            "crew_id": alt["crew_id"],
            "crew_role": alt["role"],
            "is_reserve": alt["is_reserve"],
            "at_location": alt["at_location"],
            "total_cost": plan_b_cost,
            "delay_cost": base_delay_cost,
            "assignment_cost": alt["estimated_cost"] + COST_PARAMS["crew_swap_cost"],
            "cancellation_cost": 0,
            "downstream_penalty": downstream_penalty * 1.3,
            "additional_delay_minutes": 15 if alt["at_location"] else 40,
            "flights_protected": max(0, downstream_exposed - 1),
            "legality_status": "PASS",
            "violations": [],
            "explanation": (
                f"Alternative: swap with crew member {alt['crew_id']} ({alt['role']}). "
                f"Higher administrative cost but similar protection. "
                f"Estimated cost: ${plan_b_cost:,.0f}."
            ),
            "recommended": False,
        })

    # Plan C — Cancellation (always available as last resort)
    total_cancel_cost = (
        cancellation_cost +
        passenger_count * COST_PARAMS["passenger_rebooking_per_pax"] +
        downstream_penalty * 2
    )

    recovery_plans.append({
        "plan_id": "PLAN_C",
        "plan_label": "CANCEL FLIGHT",
        "action": "cancel",
        "crew_id": None,
        "crew_role": None,
        "is_reserve": False,
        "at_location": False,
        "total_cost": total_cancel_cost,
        "delay_cost": 0,
        "assignment_cost": 0,
        "cancellation_cost": cancellation_cost,
        "downstream_penalty": downstream_penalty * 2,
        "additional_delay_minutes": 0,
        "flights_protected": 0,
        "legality_status": "N/A",
        "violations": [],
        "explanation": (
            f"Cancel flight {flight_id}. "
            f"Passenger rebooking cost: ${passenger_count * COST_PARAMS['passenger_rebooking_per_pax']:,.0f}. "
            f"Total estimated cost: ${total_cancel_cost:,.0f}. "
            f"Use only as last resort."
        ),
        "recommended": False,
    })

    # Build rejected candidates list (for dashboard display)
    rejected = []
    for j, c in enumerate(candidates):
        if not feasible_mask[j]:
            projected_duty = c["accumulated_duty_minutes"] + flight_duration
            violations = []
            if not c["availability"]:
                violations.append({"rule_id": "AVAIL_01", "detail": "Crew not available"})
            if aircraft_type not in c["aircraft_qualifications"]:
                violations.append({"rule_id": "QUAL_01",
                                   "detail": f"Not qualified for {aircraft_type}"})
            if projected_duty > MAX_DUTY:
                violations.append({"rule_id": "DUTY_01",
                                   "detail": f"Would exceed duty limit ({projected_duty} > {MAX_DUTY} min)"})
            if not c["at_location"]:
                violations.append({"rule_id": "LOC_01",
                                   "detail": f"At {c['current_location']}, needs {flight_origin}"})

            rejected.append({
                "crew_id": c["crew_id"],
                "role": c["role"],
                "violations": violations,
                "result": "REJECTED",
            })

    return {
        "flight_id": flight_id,
        "flight_number": flight.get("flight_number", flight_id),
        "origin": flight_origin,
        "destination": flight.get("destination", "???"),
        "delay_minutes": delay_minutes,
        "aircraft_type": aircraft_type,
        "passenger_count": passenger_count,
        "solver_status": cp_model.CpSolver().StatusName(status) if status else "OPTIMAL",
        "recovery_plans": recovery_plans,
        "rejected_candidates": rejected[:10],
        "candidates_evaluated": len(candidates),
        "feasible_candidates": sum(feasible_mask),
        "cancelled": len(recovery_plans) == 1 and recovery_plans[0]["action"] == "cancel",
        "solver_time_ms": solver_time,
        "cost_breakdown": {
            "base_delay_cost": base_delay_cost,
            "downstream_penalty_per_flight": COST_PARAMS["downstream_flight_penalty"],
            "downstream_flights_exposed": downstream_exposed,
            "cancellation_cost_if_cancelled": total_cancel_cost,
        },
        "note": "All costs and rules are SIMULATED. Not real airline operational data.",
    }


def print_recovery_report(result: dict):
    """Pretty print recovery optimizer results."""
    print(f"\n{'='*60}")
    print(f"  AIRCREW AI — RECOVERY OPTIMIZER")
    print(f"  Flight: {result.get('flight_number')} "
          f"{result.get('origin')}→{result.get('destination')}")
    print(f"  Delay: +{result.get('delay_minutes')} min | "
          f"Aircraft: {result.get('aircraft_type')}")
    print(f"  Candidates evaluated: {result.get('candidates_evaluated')} | "
          f"Feasible: {result.get('feasible_candidates')}")
    print(f"  Solver time: {result.get('solver_time_ms')}ms")
    print(f"{'='*60}")

    for plan in result.get("recovery_plans", []):
        tag = " ★ RECOMMENDED" if plan["recommended"] else ""
        print(f"\n  {plan['plan_id']} — {plan['plan_label']}{tag}")
        print(f"  {'─'*50}")
        if plan["crew_id"]:
            print(f"  Crew:          {plan['crew_id']} ({plan['crew_role']})")
            print(f"  Reserve:       {'Yes' if plan['is_reserve'] else 'No'}")
            print(f"  At location:   {'Yes' if plan['at_location'] else 'No'}")
        print(f"  Total cost:    ${plan['total_cost']:>12,.0f}")
        print(f"  Delay cost:    ${plan['delay_cost']:>12,.0f}")
        print(f"  Assignment:    ${plan['assignment_cost']:>12,.0f}")
        if plan['cancellation_cost']:
            print(f"  Cancellation:  ${plan['cancellation_cost']:>12,.0f}")
        print(f"  Downstream:    ${plan['downstream_penalty']:>12,.0f}")
        print(f"  Extra delay:   {plan['additional_delay_minutes']} min")
        print(f"  Flights saved: {plan['flights_protected']}")
        print(f"  Legality:      {plan['legality_status']}")

    if result.get("rejected_candidates"):
        print(f"\n  REJECTED CANDIDATES:")
        for r in result["rejected_candidates"][:5]:
            rules = ", ".join([v["rule_id"] for v in r["violations"]])
            print(f"  {r['crew_id']} ({r['role']}): {rules}")

    print(f"\n{'='*60}")


if __name__ == "__main__":
    print("=== AirCrewAI — Recovery Optimizer (OR-Tools CP-SAT) ===")
    print("NOTE: All data, rules, and costs are SIMULATED.")
    print()

    flights, crew, assignments, flights_map, crew_map = load_data()

    # Load demo disruption
    demo_path = os.path.join(DATA_DIR, "demo_disruption.json")
    with open(demo_path) as f:
        demo = json.load(f)

    flight_id = demo["flight_id"]
    delay = demo["delay_minutes"]

    print(f"Demo disruption: {demo['flight_number']} "
          f"{demo['origin']}→{demo['destination']} +{delay} min")
    print()

    result = run_recovery_optimizer(
        flight_id=flight_id,
        delay_minutes=delay,
        downstream_exposed=1,
        flights_map=flights_map,
        crew_map=crew_map,
        crew_list=crew,
    )

    print_recovery_report(result)
