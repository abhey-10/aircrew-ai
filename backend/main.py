"""
AirCrewAI — FastAPI Backend
Wires together all components:
  - Synthetic data
  - ML misconnect predictor
  - NetworkX cascade graph
  - Legality engine
  - RAG knowledge base
  - OR-Tools optimizer
  - Monte Carlo simulation
  - LLM agent (Claude API)

All data is SIMULATED. Not real airline operational data.
"""

import os
import sys
import json
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "ml"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "network"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "legality"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "rag"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "optimization"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "simulation"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "external"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "agents"))

from dotenv import load_dotenv
load_dotenv()

# ── GLOBAL STATE ───────────────────────────────────────────────────────────────
_flights = None
_crew = None
_assignments = None
_flights_map = None
_crew_map = None
_network_graph = None


def get_data():
    global _flights, _crew, _assignments, _flights_map, _crew_map
    if _flights is None:
        from optimization.recovery_optimizer import load_data
        _flights, _crew, _assignments, _flights_map, _crew_map = load_data()
    return _flights, _crew, _assignments, _flights_map, _crew_map


def get_graph():
    global _network_graph
    if _network_graph is None:
        flights, crew, assignments, _, _ = get_data()
        from network_graph import build_network_graph
        _network_graph = build_network_graph(flights, crew, assignments)
    return _network_graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: preload data and models."""
    print("AirCrewAI starting up...")
    try:
        get_data()
        print(f"Data loaded: {len(_flights)} flights, {len(_crew)} crew")
        get_graph()
        print("Network graph built")
        from predict import load_model
        load_model()
        print("ML model loaded")
    except Exception as e:
        print(f"Startup warning: {e}")
    yield
    print("AirCrewAI shutting down...")


# ── FASTAPI APP ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AirCrewAI API",
    description="Crew disruption recovery system — SIMULATED DATA ONLY",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── HEALTH ─────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "note": "All data is SIMULATED",
    }


# ── FLIGHTS ────────────────────────────────────────────────────────────────────
@app.get("/flights")
def get_flights():
    flights, _, _, _, _ = get_data()
    return {"flights": flights, "total": len(flights)}


@app.get("/flights/{flight_id}")
def get_flight(flight_id: str):
    _, _, _, flights_map, _ = get_data()
    flight = flights_map.get(flight_id)
    if not flight:
        raise HTTPException(status_code=404, detail=f"Flight {flight_id} not found")
    return flight


# ── CREW ───────────────────────────────────────────────────────────────────────
@app.get("/crew")
def get_crew():
    _, crew, _, _, _ = get_data()
    return {"crew": crew, "total": len(crew)}


@app.get("/crew/{crew_id}")
def get_crew_member(crew_id: str):
    _, _, _, _, crew_map = get_data()
    crew = crew_map.get(crew_id)
    if not crew:
        raise HTTPException(status_code=404, detail=f"Crew {crew_id} not found")
    return crew


# ── NETWORK STATUS ─────────────────────────────────────────────────────────────
@app.get("/network/status")
def get_network_status():
    from aviation_client import get_network_status
    return get_network_status()


@app.get("/network/summary")
def get_network_summary():
    G = get_graph()
    from network_graph import get_network_summary
    return get_network_summary(G)


# ── DISRUPTIONS ────────────────────────────────────────────────────────────────
@app.get("/disruptions/demo")
def get_demo_disruption():
    from aviation_client import get_demo_disruption
    return get_demo_disruption()


@app.get("/disruptions/active")
def get_active_disruptions():
    """Return simulated active disruptions for the Operations Overview page."""
    from aviation_client import get_demo_disruption
    demo = get_demo_disruption()

    _, _, _, flights_map, _ = get_data()

    disruptions = [
        {
            "disruption_id": "DEMO_001",
            "flight_id": demo["flight_id"],
            "flight_number": demo["flight_number"],
            "origin": demo["origin"],
            "destination": demo["destination"],
            "delay_minutes": demo["delay_minutes"],
            "disruption_type": demo["disruption_type"],
            "severity": "CRITICAL",
            "crews_at_risk": 1,
            "downstream_exposed": 1,
        },
        {
            "disruption_id": "SIM_002",
            "flight_id": "F183",
            "flight_number": "AA1083",
            "origin": "CLT",
            "destination": "MIA",
            "delay_minutes": 45,
            "disruption_type": "WEATHER_DELAY",
            "severity": "MODERATE",
            "crews_at_risk": 0,
            "downstream_exposed": 0,
        },
        {
            "disruption_id": "SIM_003",
            "flight_id": "F129",
            "flight_number": "AA1029",
            "origin": "DFW",
            "destination": "PHX",
            "delay_minutes": 30,
            "disruption_type": "LATE_AIRCRAFT",
            "severity": "LOW",
            "crews_at_risk": 0,
            "downstream_exposed": 0,
        },
    ]

    return {
        "disruptions": disruptions,
        "total": len(disruptions),
        "critical": sum(1 for d in disruptions if d["severity"] == "CRITICAL"),
        "note": "SIMULATED disruptions for demonstration",
    }


# ── FLIGHT STATUS ──────────────────────────────────────────────────────────────
@app.get("/flights/{flight_number}/status")
def get_flight_status(flight_number: str):
    from aviation_client import get_flight_status
    status = get_flight_status(flight_number)
    if not status:
        raise HTTPException(status_code=404, detail=f"Flight {flight_number} not found")
    return status


# ── ML PREDICTION ──────────────────────────────────────────────────────────────
class MisconnectRequest(BaseModel):
    inbound_delay_minutes: int
    scheduled_connection_minutes: int = 45
    airport_congestion_index: float = 0.75
    is_hub_airport: int = 1
    hour_of_day: int = 9
    is_peak_hour: int = 1
    accumulated_duty_minutes: int = 120
    remaining_duty_minutes: int = 480
    legs_flown_today: int = 1
    aircraft_qualified: int = 1
    turnaround_time: int = 45
    weather_severity: int = 1
    network_congestion: float = 0.5


@app.post("/predict/misconnect")
def predict_misconnect(request: MisconnectRequest):
    from predict import predict_misconnect
    features = request.model_dump()
    features["effective_connection_minutes"] = max(
        0, features["scheduled_connection_minutes"] - features["inbound_delay_minutes"]
    )
    return predict_misconnect(features)


@app.get("/predict/crew/{crew_id}")
def predict_crew_risk(crew_id: str, inbound_delay: int = 0, connection_minutes: int = 45):
    """Predict misconnect risk for a specific crew member."""
    flights, crew, _, flights_map, crew_map = get_data()

    crew_member = crew_map.get(crew_id)
    if not crew_member:
        raise HTTPException(status_code=404, detail=f"Crew {crew_id} not found")

    from features import build_crew_features, load_synthetic_data
    _, _, _, _, flights_map_loaded, crew_map_loaded, airports_map = load_synthetic_data()

    # Find next flight for this crew
    from optimization.recovery_optimizer import load_data as load_opt_data
    _, _, assignments, _, _ = load_opt_data()

    next_flight_id = None
    for a in assignments:
        if a["crew_id"] == crew_id:
            next_flight_id = a["flight_id"]
            break

    if not next_flight_id:
        return {"error": f"No flight assignment found for crew {crew_id}"}

    feat = build_crew_features(
        crew_id=crew_id,
        inbound_delay=inbound_delay,
        connection_minutes=connection_minutes,
        outbound_flight_id=next_flight_id,
        flights_map=flights_map_loaded,
        crew_map=crew_map_loaded,
        airports_map=airports_map,
    )

    from predict import predict_misconnect
    result = predict_misconnect(feat)
    result["crew_id"] = crew_id
    result["next_flight_id"] = next_flight_id
    return result


# ── NETWORK IMPACT ─────────────────────────────────────────────────────────────
class NetworkImpactRequest(BaseModel):
    flight_id: str
    delay_minutes: int


@app.post("/network/impact")
def get_network_impact(request: NetworkImpactRequest):
    flights, crew, assignments, _, _ = get_data()
    G = get_graph()
    from network_graph import get_downstream_impact
    return get_downstream_impact(
        request.flight_id, request.delay_minutes,
        G, flights, crew, assignments
    )


# ── LEGALITY CHECK ─────────────────────────────────────────────────────────────
class LegalityRequest(BaseModel):
    crew_id: str
    flight_id: str
    inbound_delay: int = 0
    connection_minutes: int = 45


@app.post("/legality/check")
def check_legality(request: LegalityRequest):
    _, _, _, flights_map, crew_map = get_data()
    from legality_engine import check_crew_legality
    return check_crew_legality(
        crew_id=request.crew_id,
        flight_id=request.flight_id,
        inbound_delay=request.inbound_delay,
        connection_minutes=request.connection_minutes,
        flights_map=flights_map,
        crew_map=crew_map,
    )


# ── RAG SEARCH ─────────────────────────────────────────────────────────────────
class RAGRequest(BaseModel):
    query: str
    top_k: int = 3


@app.post("/rag/search")
def rag_search(request: RAGRequest):
    from rag_retriever import search
    results = search(request.query, top_k=request.top_k)
    return {
        "query": request.query,
        "results": results,
        "total": len(results),
    }


# ── RECOVERY OPTIMIZER ─────────────────────────────────────────────────────────
class RecoveryRequest(BaseModel):
    flight_id: str
    delay_minutes: int
    downstream_exposed: int = 1
    run_monte_carlo: bool = True
    n_simulations: int = 500


@app.post("/recovery/optimize")
def optimize_recovery(request: RecoveryRequest):
    flights, crew, _, flights_map, crew_map = get_data()

    from optimization.recovery_optimizer import run_recovery_optimizer
    result = run_recovery_optimizer(
        flight_id=request.flight_id,
        delay_minutes=request.delay_minutes,
        downstream_exposed=request.downstream_exposed,
        flights_map=flights_map,
        crew_map=crew_map,
        crew_list=crew,
    )

    if request.run_monte_carlo and result.get("recovery_plans"):
        from simulation.monte_carlo import run_monte_carlo
        flight = flights_map.get(request.flight_id, {})
        passenger_count = flight.get("passenger_count", 150)

        mc_results = run_monte_carlo(
            recovery_plans=result["recovery_plans"],
            base_delay=request.delay_minutes,
            passenger_count=passenger_count,
            downstream_exposed=request.downstream_exposed,
            n_simulations=request.n_simulations,
        )
        result["recovery_plans"] = mc_results
        result["monte_carlo_simulations"] = request.n_simulations

    return result


# ── FULL DISRUPTION ANALYSIS ───────────────────────────────────────────────────
@app.get("/analyze/{flight_id}")
def analyze_disruption(flight_id: str, delay_minutes: int = 105):
    """
    Full pipeline: disruption -> network impact -> ML risk -> optimize -> Monte Carlo.
    Single endpoint for the Recovery Center page.
    """
    flights, crew, assignments, flights_map, crew_map = get_data()
    G = get_graph()

    flight = flights_map.get(flight_id)
    if not flight:
        raise HTTPException(status_code=404, detail=f"Flight {flight_id} not found")

    # 1. Network impact
    from network_graph import get_downstream_impact
    network_impact = get_downstream_impact(
        flight_id, delay_minutes, G, flights, crew, assignments
    )

    # 2. ML risk for assigned crew
    assigned_crew = [a["crew_id"] for a in assignments if a["flight_id"] == flight_id]
    ml_risks = []
    if assigned_crew:
        from features import build_crew_features, load_synthetic_data
        _, _, _, _, flights_map_loaded, crew_map_loaded, airports_map = load_synthetic_data()
        from predict import predict_misconnect

        for crew_id in assigned_crew[:3]:
            try:
                feat = build_crew_features(
                    crew_id=crew_id,
                    inbound_delay=delay_minutes,
                    connection_minutes=45,
                    outbound_flight_id=flight_id,
                    flights_map=flights_map_loaded,
                    crew_map=crew_map_loaded,
                    airports_map=airports_map,
                )
                risk = predict_misconnect(feat)
                risk["crew_id"] = crew_id
                ml_risks.append(risk)
            except Exception as e:
                ml_risks.append({"crew_id": crew_id, "error": str(e)})

    # 3. Recovery optimizer + Monte Carlo
    from optimization.recovery_optimizer import run_recovery_optimizer
    recovery = run_recovery_optimizer(
        flight_id=flight_id,
        delay_minutes=delay_minutes,
        downstream_exposed=network_impact.get("total_exposed_flights", 0),
        flights_map=flights_map,
        crew_map=crew_map,
        crew_list=crew,
    )

    if recovery.get("recovery_plans"):
        from simulation.monte_carlo import run_monte_carlo
        passenger_count = flight.get("passenger_count", 150)
        recovery["recovery_plans"] = run_monte_carlo(
            recovery_plans=recovery["recovery_plans"],
            base_delay=delay_minutes,
            passenger_count=passenger_count,
            downstream_exposed=network_impact.get("total_exposed_flights", 0),
            n_simulations=500,
        )

    return {
        "flight_id": flight_id,
        "flight": flight,
        "delay_minutes": delay_minutes,
        "network_impact": network_impact,
        "crew_risk_scores": ml_risks,
        "recovery": recovery,
        "note": "All data SIMULATED. Human review required before any operational action.",
    }


# ── AI COPILOT ─────────────────────────────────────────────────────────────────
class CopilotRequest(BaseModel):
    message: str
    conversation_history: list = []
    flight_id: Optional[str] = None


@app.post("/copilot/query")
def copilot_query(request: CopilotRequest):
    """LLM agent with tool calling. Grounded responses only."""
    try:
        from agents.crew_agent import run_agent
        return run_agent(
            message=request.message,
            conversation_history=request.conversation_history,
            flight_id=request.flight_id,
        )
    except ImportError:
        return {
            "response": "AI Copilot not yet configured. Please set ANTHROPIC_API_KEY.",
            "tools_used": [],
            "error": "Agent module not available",
        }
    except Exception as e:
        return {
            "response": f"Agent error: {str(e)}",
            "tools_used": [],
            "error": str(e),
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
