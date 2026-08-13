"""
AirCrewAI — Monte Carlo Recovery Robustness Simulation
Runs N simulations to estimate recovery plan robustness under uncertainty.

For each recovery plan, simulates random variations in:
  - Additional inbound delay
  - Crew connection time variability
  - Airport congestion
  - Turnaround time variation

Outputs:
  - Expected cost
  - P50 / P90 cost (median and 90th percentile)
  - Recovery success probability
  - Downstream cancellation probability

This helps distinguish between:
  - CHEAPEST expected cost plan (may be fragile)
  - MOST ROBUST plan (higher expected cost but lower tail risk)

All data and rules are SIMULATED for portfolio demonstration purposes.
"""

import numpy as np
import json
import os
import sys
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

np.random.seed(42)

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "data", "synthetic"
)

# ── SIMULATION PARAMETERS ──────────────────────────────────────────────────────

SIMULATION_PARAMS = {
    # Additional delay uncertainty (minutes)
    "additional_delay_mean": 15,
    "additional_delay_std": 20,
    "additional_delay_max": 90,

    # Connection time variability (minutes)
    "connection_variability_std": 8,

    # Turnaround time variability (minutes)
    "turnaround_variability_std": 10,

    # Airport congestion multiplier variability
    "congestion_variability_std": 0.1,

    # Probability of crew becoming unavailable mid-recovery
    "crew_unavailability_prob": 0.03,

    # Probability of additional downstream disruption
    "downstream_cascade_prob": 0.15,

    # Cost parameters
    "delay_cost_per_minute": 100,
    "cancellation_cost_base": 35000,
    "downstream_flight_penalty": 5000,
    "passenger_rebooking_per_pax": 200,
}


def simulate_single_recovery(
    plan: dict,
    base_delay: int,
    passenger_count: int,
    downstream_exposed: int,
    rng: np.random.Generator,
) -> dict:
    """
    Simulate one realization of a recovery plan under uncertainty.

    Returns whether the recovery was successful and the realized cost.
    """
    params = SIMULATION_PARAMS

    # ── SAMPLE UNCERTAINTY ─────────────────────────────────────────────────────

    # Additional delay beyond what we know about
    extra_delay = max(0, rng.normal(params["additional_delay_mean"],
                                    params["additional_delay_std"]))
    extra_delay = min(extra_delay, params["additional_delay_max"])
    total_delay = base_delay + extra_delay

    # Connection time variability
    connection_variation = rng.normal(0, params["connection_variability_std"])

    # Crew becomes unavailable?
    crew_unavailable = rng.random() < params["crew_unavailability_prob"]

    # Additional downstream cascade?
    extra_downstream = 1 if rng.random() < params["downstream_cascade_prob"] else 0
    total_downstream = downstream_exposed + extra_downstream

    # ── DETERMINE RECOVERY SUCCESS ─────────────────────────────────────────────

    action = plan.get("action", "crew_swap")
    at_location = plan.get("at_location", True)
    base_connection = 45 if at_location else 20  # less time if repositioning

    effective_connection = base_connection + connection_variation - extra_delay * 0.3
    MIN_CONNECTION = 30

    # Recovery fails if:
    # 1. Crew becomes unavailable
    # 2. Connection time falls below minimum
    # 3. Action is cancel (always fails to protect flights)

    if action == "cancel":
        recovery_success = False
        downstream_cancelled = total_downstream
    elif crew_unavailable:
        recovery_success = False
        downstream_cancelled = total_downstream
    elif effective_connection < MIN_CONNECTION:
        recovery_success = False
        downstream_cancelled = total_downstream
    else:
        recovery_success = True
        downstream_cancelled = extra_downstream  # only the extra cascade

    # ── CALCULATE REALIZED COST ────────────────────────────────────────────────

    delay_cost = total_delay * params["delay_cost_per_minute"]
    assignment_cost = plan.get("assignment_cost", 0)
    cancellation_cost = plan.get("cancellation_cost", 0)

    if not recovery_success and action != "cancel":
        # Recovery failed — must cancel
        cancellation_cost = params["cancellation_cost_base"]
        passenger_cost = passenger_count * params["passenger_rebooking_per_pax"]
        downstream_cost = downstream_cancelled * params["downstream_flight_penalty"] * 2
        total_cost = delay_cost + cancellation_cost + passenger_cost + downstream_cost
    else:
        downstream_cost = downstream_cancelled * params["downstream_flight_penalty"]
        passenger_cost = 0
        if action == "cancel":
            passenger_cost = passenger_count * params["passenger_rebooking_per_pax"]
        total_cost = delay_cost + assignment_cost + cancellation_cost + passenger_cost + downstream_cost

    return {
        "success": recovery_success,
        "total_cost": total_cost,
        "realized_delay": total_delay,
        "downstream_cancelled": downstream_cancelled,
        "crew_unavailable": crew_unavailable,
    }


def run_monte_carlo(
    recovery_plans: list,
    base_delay: int,
    passenger_count: int = 150,
    downstream_exposed: int = 1,
    n_simulations: int = 1000,
) -> list:
    """
    Run Monte Carlo simulation for each recovery plan.

    Args:
        recovery_plans: List of recovery plans from optimizer
        base_delay: Known inbound delay in minutes
        passenger_count: Passengers on the flight
        downstream_exposed: Number of downstream flights at risk
        n_simulations: Number of Monte Carlo trials

    Returns:
        List of plans with robustness statistics added
    """
    rng = np.random.default_rng(seed=42)
    results = []

    for plan in recovery_plans:
        costs = []
        successes = []
        downstream_cancellations = []

        for _ in range(n_simulations):
            sim = simulate_single_recovery(
                plan=plan,
                base_delay=base_delay,
                passenger_count=passenger_count,
                downstream_exposed=downstream_exposed,
                rng=rng,
            )
            costs.append(sim["total_cost"])
            successes.append(1 if sim["success"] else 0)
            downstream_cancellations.append(sim["downstream_cancelled"])

        costs_arr = np.array(costs)
        success_arr = np.array(successes)
        downstream_arr = np.array(downstream_cancellations)

        plan_result = {
            **plan,
            "monte_carlo": {
                "n_simulations": n_simulations,
                "expected_cost": round(float(np.mean(costs_arr)), 0),
                "median_cost": round(float(np.median(costs_arr)), 0),
                "p90_cost": round(float(np.percentile(costs_arr, 90)), 0),
                "p95_cost": round(float(np.percentile(costs_arr, 95)), 0),
                "min_cost": round(float(np.min(costs_arr)), 0),
                "max_cost": round(float(np.max(costs_arr)), 0),
                "cost_std": round(float(np.std(costs_arr)), 0),
                "recovery_success_probability": round(float(np.mean(success_arr)), 4),
                "downstream_cancellation_probability": round(
                    float(np.mean(downstream_arr > 0)), 4),
                "expected_downstream_cancellations": round(
                    float(np.mean(downstream_arr)), 2),
                "robustness_score": round(
                    float(np.mean(success_arr)) * 100 -
                    (np.percentile(costs_arr, 90) - np.mean(costs_arr)) / 1000,
                    1
                ),
            }
        }

        results.append(plan_result)

    # Sort by robustness score (not just expected cost)
    results.sort(key=lambda x: -x["monte_carlo"]["robustness_score"])

    return results


def compare_plans(mc_results: list) -> str:
    """
    Generate a plain-English comparison of recovery plans
    based on Monte Carlo results.
    """
    if not mc_results:
        return "No plans to compare."

    lines = []
    lines.append("MONTE CARLO ROBUSTNESS ANALYSIS")
    lines.append("=" * 50)
    lines.append(f"Simulations per plan: {mc_results[0]['monte_carlo']['n_simulations']:,}")
    lines.append("")

    for plan in mc_results:
        mc = plan["monte_carlo"]
        lines.append(f"{plan['plan_id']} — {plan['plan_label']}")
        lines.append(f"  Expected cost:     ${mc['expected_cost']:>10,.0f}")
        lines.append(f"  Median cost:       ${mc['median_cost']:>10,.0f}")
        lines.append(f"  P90 cost:          ${mc['p90_cost']:>10,.0f}  (worst 10% of scenarios)")
        lines.append(f"  Success prob:      {mc['recovery_success_probability']:.1%}")
        lines.append(f"  Downstream cancel: {mc['downstream_cancellation_probability']:.1%}")
        lines.append(f"  Robustness score:  {mc['robustness_score']:.1f}")
        lines.append("")

    # Key insight
    if len(mc_results) >= 2:
        plan_a = mc_results[0]
        plan_b = mc_results[1]
        mc_a = plan_a["monte_carlo"]
        mc_b = plan_b["monte_carlo"]

        if mc_a["expected_cost"] > mc_b["expected_cost"]:
            cost_diff = mc_a["expected_cost"] - mc_b["expected_cost"]
            p90_diff = mc_b["p90_cost"] - mc_a["p90_cost"]
            lines.append(f"KEY INSIGHT: {plan_b['plan_id']} has lower expected cost")
            lines.append(f"(${cost_diff:,.0f} cheaper on average) but {plan_a['plan_id']}")
            lines.append(f"is more robust — P90 cost is ${p90_diff:,.0f} lower in bad scenarios.")
            lines.append(f"Success rate: {plan_a['plan_id']} {mc_a['recovery_success_probability']:.1%} "
                        f"vs {plan_b['plan_id']} {mc_b['recovery_success_probability']:.1%}")
        else:
            lines.append(f"KEY INSIGHT: {plan_a['plan_id']} is both cheaper AND more robust.")
            lines.append(f"Clear recommendation: {plan_a['plan_id']}.")

    return "\n".join(lines)


if __name__ == "__main__":
    print("=== AirCrewAI — Monte Carlo Recovery Robustness Simulation ===")
    print("NOTE: All data is SIMULATED for portfolio demonstration.")
    print()

    # Load demo disruption
    demo_path = os.path.join(DATA_DIR, "demo_disruption.json")
    with open(demo_path) as f:
        demo = json.load(f)

    # Import optimizer
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from optimization.recovery_optimizer import run_recovery_optimizer, load_data

    flights, crew, assignments, flights_map, crew_map = load_data()

    print(f"Running optimizer for {demo['flight_number']} +{demo['delay_minutes']} min...")
    optimizer_result = run_recovery_optimizer(
        flight_id=demo["flight_id"],
        delay_minutes=demo["delay_minutes"],
        downstream_exposed=1,
        flights_map=flights_map,
        crew_map=crew_map,
        crew_list=crew,
    )

    plans = optimizer_result.get("recovery_plans", [])
    passenger_count = optimizer_result.get("passenger_count", 150)

    print(f"Running Monte Carlo (1000 simulations per plan)...")
    print()

    mc_results = run_monte_carlo(
        recovery_plans=plans,
        base_delay=demo["delay_minutes"],
        passenger_count=passenger_count,
        downstream_exposed=1,
        n_simulations=1000,
    )

    print(compare_plans(mc_results))
