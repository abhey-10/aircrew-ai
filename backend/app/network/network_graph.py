"""
AirCrewAI — Network Disruption Propagation Engine
Uses NetworkX to model flight-crew dependencies and trace downstream impact.
When a flight is delayed, this engine determines which crew connections fail
and which downstream flights become exposed.
"""

import json
import os
import networkx as nx
from typing import Optional
from datetime import datetime, timedelta

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "data", "synthetic"
)


def load_data():
    with open(os.path.join(DATA_DIR, "flights.json")) as f:
        flights = json.load(f)
    with open(os.path.join(DATA_DIR, "crew.json")) as f:
        crew = json.load(f)
    with open(os.path.join(DATA_DIR, "assignments.json")) as f:
        assignments = json.load(f)
    return flights, crew, assignments


def build_network_graph(flights: list, crew: list, assignments: list) -> nx.DiGraph:
    """
    Build a directed graph representing flight-crew dependencies.

    Nodes:
      - Flight nodes: flight_id
      - Crew nodes: crew_id

    Edges:
      - crew -> flight: crew is assigned to this flight
      - flight -> crew: crew is released from this flight (and available for next)
      - crew -> crew_next_flight: crew continuation dependency
    """
    G = nx.DiGraph()

    # Add flight nodes
    for f in flights:
        G.add_node(f["flight_id"], type="flight", data=f)

    # Add crew nodes
    for c in crew:
        G.add_node(c["crew_id"], type="crew", data=c)

    # Add assignment edges
    # crew -> flight (crew is assigned to this flight)
    flight_map = {f["flight_id"]: f for f in flights}
    crew_assignments = {}

    for a in assignments:
        crew_id = a["crew_id"]
        flight_id = a["flight_id"]

        G.add_edge(crew_id, flight_id,
                   edge_type="assignment",
                   connection_minutes=a.get("connection_minutes", 45))

        if crew_id not in crew_assignments:
            crew_assignments[crew_id] = []
        crew_assignments[crew_id].append(a)

    # Add crew continuation edges (flight -> next flight via crew)
    # This is the cascade dependency: if flight A delays, crew misses flight B
    for crew_id, crew_assign in crew_assignments.items():
        sorted_assign = sorted(crew_assign, key=lambda x: x.get("report_time", ""))
        for i in range(len(sorted_assign) - 1):
            current_flight = sorted_assign[i]["flight_id"]
            next_flight = sorted_assign[i + 1]["flight_id"]
            connection_mins = sorted_assign[i].get("connection_minutes", 45)

            G.add_edge(current_flight, next_flight,
                       edge_type="crew_continuation",
                       crew_id=crew_id,
                       connection_minutes=connection_mins)

    return G


def get_downstream_impact(flight_id: str, delay_minutes: int,
                           G: Optional[nx.DiGraph] = None,
                           flights: Optional[list] = None,
                           crew: Optional[list] = None,
                           assignments: Optional[list] = None) -> dict:
    """
    Given a delayed flight, trace all downstream flights that become exposed.

    Logic:
    1. Find all crew assigned to the delayed flight
    2. For each crew, check if delay causes them to miss their next connection
    3. If connection is missed, mark next flight as exposed
    4. Recursively check downstream from exposed flights

    Returns structured impact report.
    """
    if G is None:
        flights, crew, assignments = load_data()
        G = build_network_graph(flights, crew, assignments)

    if flights is None:
        flights, crew, assignments = load_data()

    flights_map = {f["flight_id"]: f for f in flights}
    crew_map = {c["crew_id"]: c for c in crew}

    if flight_id not in G.nodes:
        return {
            "error": f"Flight {flight_id} not found in network graph",
            "flight_id": flight_id,
        }

    affected_crew = []
    immediately_exposed = []
    downstream_exposed = []
    visited = set()

    def traverse(fid: str, current_delay: int, depth: int = 0):
        if depth > 3 or fid in visited:
            return
        visited.add(fid)

        # Find crew continuation edges from this flight
        for successor in G.successors(fid):
            edge_data = G.edges[fid, successor]
            if edge_data.get("edge_type") != "crew_continuation":
                continue

            crew_id = edge_data.get("crew_id")
            connection_mins = edge_data.get("connection_minutes", 45)
            MIN_CONNECTION = 30

            effective_connection = connection_mins - current_delay

            if effective_connection < MIN_CONNECTION:
                # This crew misses the connection
                if crew_id and crew_id not in [c["crew_id"] for c in affected_crew]:
                    crew_info = crew_map.get(crew_id, {})
                    affected_crew.append({
                        "crew_id": crew_id,
                        "role": crew_info.get("role", "UNKNOWN"),
                        "base": crew_info.get("base", "UNKNOWN"),
                        "connection_minutes": connection_mins,
                        "effective_connection": effective_connection,
                        "misconnect_certain": effective_connection < 0,
                    })

                # This successor flight is now exposed
                successor_flight = flights_map.get(successor, {})
                if depth == 0:
                    if successor not in [f["flight_id"] for f in immediately_exposed]:
                        immediately_exposed.append({
                            "flight_id": successor,
                            "flight_number": successor_flight.get("flight_number", successor),
                            "origin": successor_flight.get("origin", "???"),
                            "destination": successor_flight.get("destination", "???"),
                            "scheduled_departure": successor_flight.get("scheduled_departure"),
                            "crew_id": crew_id,
                            "severity": "CRITICAL" if effective_connection < 0 else "HIGH",
                        })
                else:
                    if successor not in [f["flight_id"] for f in downstream_exposed]:
                        downstream_exposed.append({
                            "flight_id": successor,
                            "flight_number": successor_flight.get("flight_number", successor),
                            "origin": successor_flight.get("origin", "???"),
                            "destination": successor_flight.get("destination", "???"),
                            "scheduled_departure": successor_flight.get("scheduled_departure"),
                            "crew_id": crew_id,
                            "severity": "MODERATE",
                        })

                # Continue traversal downstream
                cascade_delay = max(0, current_delay - connection_mins)
                traverse(successor, cascade_delay, depth + 1)

    traverse(flight_id, delay_minutes)

    # Calculate estimated cascade cost
    base_flight = flights_map.get(flight_id, {})
    delay_cost = delay_minutes * base_flight.get("delay_cost_per_minute", 100)
    exposed_cancellation_cost = sum(
        flights_map.get(f["flight_id"], {}).get("cancellation_cost", 25000)
        for f in immediately_exposed + downstream_exposed
    )
    estimated_cascade_cost = delay_cost + exposed_cancellation_cost

    return {
        "flight_id": flight_id,
        "flight_number": base_flight.get("flight_number", flight_id),
        "origin": base_flight.get("origin", "???"),
        "destination": base_flight.get("destination", "???"),
        "delay_minutes": delay_minutes,
        "affected_crew": affected_crew,
        "immediately_exposed": immediately_exposed,
        "downstream_exposed": downstream_exposed,
        "total_exposed_flights": len(immediately_exposed) + len(downstream_exposed),
        "total_affected_crew": len(affected_crew),
        "estimated_cascade_cost": estimated_cascade_cost,
        "severity": "CRITICAL" if len(immediately_exposed) > 2 else "HIGH" if len(immediately_exposed) > 0 else "LOW",
    }


def get_network_summary(G: Optional[nx.DiGraph] = None) -> dict:
    """Return summary statistics about the network graph."""
    if G is None:
        flights, crew, assignments = load_data()
        G = build_network_graph(flights, crew, assignments)

    flight_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "flight"]
    crew_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "crew"]
    continuation_edges = [(u, v) for u, v, d in G.edges(data=True)
                          if d.get("edge_type") == "crew_continuation"]

    return {
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "flight_nodes": len(flight_nodes),
        "crew_nodes": len(crew_nodes),
        "crew_continuation_edges": len(continuation_edges),
        "is_dag": nx.is_directed_acyclic_graph(G),
    }


if __name__ == "__main__":
    print("=== AirCrewAI — Network Disruption Propagation Engine ===")
    print()

    flights, crew, assignments = load_data()
    G = build_network_graph(flights, crew, assignments)

    summary = get_network_summary(G)
    print("Network Graph Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print()

    # Load demo disruption
    demo_path = os.path.join(DATA_DIR, "demo_disruption.json")
    with open(demo_path) as f:
        demo = json.load(f)

    flight_id = demo["flight_id"]
    delay = demo["delay_minutes"]

    print(f"Demo Disruption: {demo['flight_number']} {demo['origin']} -> {demo['destination']} +{delay} min")
    print()

    impact = get_downstream_impact(flight_id, delay, G, flights, crew, assignments)

    print(f"Affected crew: {impact['total_affected_crew']}")
    for c in impact["affected_crew"]:
        print(f"  {c['crew_id']} ({c['role']}) — effective connection: {c['effective_connection']} min")

    print(f"\nImmediately exposed flights: {len(impact['immediately_exposed'])}")
    for f in impact["immediately_exposed"]:
        print(f"  {f['flight_number']} {f['origin']}→{f['destination']} [{f['severity']}]")

    print(f"\nDownstream exposed flights: {len(impact['downstream_exposed'])}")
    for f in impact["downstream_exposed"]:
        print(f"  {f['flight_number']} {f['origin']}→{f['destination']} [{f['severity']}]")

    print(f"\nTotal exposed: {impact['total_exposed_flights']} flights")
    print(f"Estimated cascade cost: ${impact['estimated_cascade_cost']:,.0f}")
    print(f"Severity: {impact['severity']}")
