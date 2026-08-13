"""
AirCrewAI — RAG Crew Operations Knowledge Base
Builds a semantic search index over simulated crew operating rules.
Uses sentence-transformers for embeddings and FAISS for vector search.

IMPORTANT: All documents are SYNTHETIC and ILLUSTRATIVE.
They do NOT represent real airline regulations or FAA rules.
RAG retrieves relevant policy text to EXPLAIN legality decisions.
RAG does NOT determine legality — that is the legality engine's job.
"""

import os
import json
import pickle
import numpy as np
from typing import Optional

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "data", "synthetic"
)

KB_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "data", "knowledge_base"
)

INDEX_PATH = os.path.join(DATA_DIR, "rag_index.pkl")
CHUNKS_PATH = os.path.join(DATA_DIR, "rag_chunks.json")

# ── SYNTHETIC KNOWLEDGE BASE DOCUMENTS ────────────────────────────────────────
# These are illustrative documents for the simulated crew operations environment.

KNOWLEDGE_BASE_DOCUMENTS = {
    "duty_rules.txt": """
SIMULATED CREW DUTY RULES
Document Type: Illustrative Policy — Not Real Airline Regulations

Rule DUTY_01: Maximum Simulated Duty Time
In this simulated airline environment, crew members may not exceed 600 minutes
(10 hours) of accumulated duty time in a single duty period. Duty time begins
at the crew member's report time and ends at scheduled release from their final
flight of the day. Any assignment that would cause projected duty to exceed
600 minutes is automatically flagged as a DUTY_01 violation by the legality engine.

Rule DUTY_02: Duty Time Tracking
The system tracks accumulated duty minutes for each crew member from the start
of their assigned duty period. Accumulated duty includes all time from report
to release across all flights in a duty sequence.

Rule DUTY_03: Pre-Departure Report Time
Crew members are required to report at least 60 minutes prior to scheduled
departure for captain and first officer positions, and 45 minutes prior for
flight attendant positions. Report time is included in accumulated duty calculation.

Note: These rules are entirely synthetic and illustrative. Real airline duty
rules are significantly more complex and governed by FAR Part 117 and
collective bargaining agreements.
""",

    "rest_requirements.txt": """
SIMULATED CREW REST REQUIREMENTS
Document Type: Illustrative Policy — Not Real Airline Regulations

Rule REST_01: Minimum Rest Between Duty Periods
In this simulated environment, crew members must receive a minimum of 480 minutes
(8 hours) of rest between consecutive duty periods. Rest is measured from the
time of release from the previous duty period to the next report time.

Rule REST_02: Rest Period Definition
A rest period is an uninterrupted period during which the crew member is free
from all duty obligations. Positioning or deadhead travel is NOT considered rest
for the purposes of this simulated rule.

Rule REST_03: Extended Operations
For simulated flights exceeding 300 minutes of flight time, crew members must
receive an additional 60 minutes of rest above the standard REST_01 minimum.

Note: These are simulated rules for the AirCrewAI portfolio project only.
""",

    "reserve_procedures.txt": """
SIMULATED RESERVE CREW PROCEDURES
Document Type: Illustrative Policy — Not Real Airline Regulations

Reserve Activation Policy
Reserve crew members in this simulation are available for assignment when:
1. Their reserve_status field is set to True
2. Their availability field is set to True
3. They have sufficient remaining duty time for the proposed assignment
4. They are located at or can be positioned to the required departure airport

Reserve Crew Priority
When the recovery optimizer generates candidate crews, reserve crew members
are considered as a primary recovery resource. Activating a reserve crew
incurs a simulated reserve activation cost of $1,200 in addition to
standard assignment costs.

Reserve crew members are NOT available if:
- They have already exceeded their daily availability window
- Their availability flag is set to False
- They would violate any other simulated legality rule

Rule RESERVE_01: Reserve Activation Constraint
Reserve crew can only be activated when explicitly flagged as available
in the simulated roster system.
""",

    "qualification_rules.txt": """
SIMULATED AIRCRAFT QUALIFICATION RULES
Document Type: Illustrative Policy — Not Real Airline Regulations

Rule QUAL_01: Aircraft Type Qualification
In this simulated environment, each crew member holds qualifications for
one or more aircraft types. The supported aircraft types are:
- B737: Boeing 737-800 family
- B787: Boeing 787-9 Dreamliner
- A320: Airbus A320
- A321: Airbus A321

A crew member may only be assigned to a flight if they hold a qualification
for the aircraft type scheduled for that flight. Assignment to an unqualified
aircraft type is a QUAL_01 violation.

Cross-Qualification
Some crew members in the simulation hold qualifications for multiple aircraft
types. Cross-qualified crew are more flexible for recovery assignments and
are prioritized by the optimizer when multiple candidates are available.

Qualification Check
The legality engine performs qualification validation automatically. When
QUAL_01 is violated, the rejection message will specify the required aircraft
type and the crew member's actual qualifications.
""",

    "connection_minimums.txt": """
SIMULATED CREW CONNECTION TIME REQUIREMENTS
Document Type: Illustrative Policy — Not Real Airline Regulations

Rule CONN_01: Minimum Connection Time
In this simulated environment, crew members require a minimum of 30 minutes
of connection time between the arrival of their inbound flight and the
departure of their next assigned flight. This minimum reflects simulated
time required for deplaning, walking between gates, and crew briefing.

Effective Connection Calculation
When an inbound flight experiences a delay, the effective connection time
is calculated as:

  effective_connection = scheduled_connection_minutes - inbound_delay_minutes

If the effective connection falls below 30 minutes, the CONN_01 rule is
violated and the crew is considered unable to make the connection.

Hub Airport Connection Times
Larger hub airports in the simulation (ORD, DFW, CLT, MIA) have higher
congestion indices, which increases the real-world (though not simulated)
risk of crew misconnection even when the 30-minute minimum is technically met.
The ML misconnect risk model accounts for airport congestion as a feature.

Warning Threshold
A CONN_WARN advisory is issued when effective connection time is between
30 and 45 minutes, indicating a tight but legally permissible connection.
""",

    "positioning_guidelines.txt": """
SIMULATED CREW POSITIONING GUIDELINES
Document Type: Illustrative Policy — Not Real Airline Regulations

Crew Positioning (Deadhead)
When a crew member is not at the required departure airport, they may be
positioned via a deadhead flight to the correct location. In this simulation,
positioning is evaluated as an option by the recovery optimizer.

Rule LOC_01: Location Requirement
Crew must be physically located at the departure airport of their assigned
flight. The legality engine checks the crew member's current_location field
against the flight's origin airport code. A mismatch results in a LOC_01
violation.

Positioning Cost
Simulated positioning/deadhead cost is $800 per crew member per positioning
event. This cost is included in the optimizer's objective function when
evaluating recovery plans that require repositioning.

Positioning Feasibility
Positioning is only feasible if there is a suitable flight from the crew
member's current location to the required departure airport with sufficient
lead time before the disrupted flight's departure.
""",

    "disruption_recovery.txt": """
SIMULATED DISRUPTION RECOVERY GUIDELINES
Document Type: Illustrative Policy — Not Real Airline Regulations

Recovery Priority Framework
When a crew disruption occurs, the AirCrewAI system evaluates recovery
options in the following priority order:

1. Keep original crew (if legally feasible despite delay)
2. Assign available reserve crew at the departure station
3. Swap with another active crew member with available duty time
4. Reposition crew from a nearby station
5. Delay the flight to wait for the original crew
6. Cancel the flight as a last resort

Cost Hierarchy
Recovery costs in the simulated environment are structured as:
- Reserve activation: $1,200 + standard duty pay
- Crew swap: $800 administrative cost
- Repositioning: $800 per crew member
- Flight delay: delay_cost_per_minute × delay_minutes
- Cancellation: cancellation_cost (varies by flight, typically $18,000-$55,000)

Downstream Impact Consideration
The optimizer penalizes recovery plans that leave downstream flights exposed.
A downstream disruption penalty of $5,000 per exposed flight is applied
to encourage recovery plans that protect the full flight sequence.

Human Approval Required
All recovery recommendations from AirCrewAI require human review and approval
before implementation. The system is a decision-support tool, not an
autonomous operations system.
""",

    "cancellation_policy.txt": """
SIMULATED FLIGHT CANCELLATION DECISION GUIDELINES
Document Type: Illustrative Policy — Not Real Airline Regulations

When to Consider Cancellation
In the simulated environment, flight cancellation is evaluated as an option
when all other recovery strategies are infeasible or would result in greater
total cost than cancellation itself.

Cancellation costs in the simulation include:
- Base cancellation processing cost (flight-specific, $18,000-$55,000)
- Passenger rebooking costs
- Downstream flight exposure penalties

Delay vs Cancel Tradeoff
Research on airline disruption recovery (including the RecovAir methodology
referenced in this project) suggests that aggressive cancellation policies
often produce higher total costs than delay-and-recover strategies. This is
because per-passenger rebooking costs accumulate rapidly with cancellation,
while delay costs are more gradual.

The optimizer evaluates both delay and cancellation options and selects
the minimum-cost feasible recovery.

Passenger Impact
Cancelled flights have higher passenger impact scores in the simulation,
as affected passengers must be rebooked and may miss connections. The
optimizer weights passenger impact as part of its objective function.
""",

    "ml_risk_model.txt": """
AIRCREW AI — ML MISCONNECT RISK MODEL DOCUMENTATION

Purpose
The AirCrewAI misconnect risk model predicts the probability that a crew
member will fail to make their next connection given current operational
conditions. It is trained on synthetic data generated from the simulated
airline schedule.

Model: XGBoost Classifier
The model uses gradient boosting with 200 estimators. Class imbalance
is handled using scale_pos_weight calibration. The model outputs a
probability score between 0 and 1.

Risk Levels:
- LOW: probability < 0.35
- MODERATE: probability 0.35-0.60
- HIGH: probability 0.60-0.80
- CRITICAL: probability > 0.80

Key Features (by SHAP importance):
1. aircraft_qualified — whether crew is qualified for the aircraft
2. effective_connection_minutes — connection time minus inbound delay
3. inbound_delay_minutes — how late the inbound flight is
4. weather_severity — severity of weather disruption (0-3 scale)
5. legs_flown_today — fatigue proxy

SHAP Explanations
For each prediction, the model provides SHAP (SHapley Additive exPlanations)
values showing the contribution of each feature to the final prediction.
Positive SHAP values increase misconnect risk; negative values decrease it.

Important Limitation
The model is trained on synthetic data. Real-world performance would differ
significantly. This is a portfolio demonstration of ML and XAI concepts.
""",
}


def build_knowledge_base():
    """
    Chunk documents, compute embeddings, and build FAISS index.
    Saves index and chunks to disk for fast inference.
    """
    try:
        from sentence_transformers import SentenceTransformer
        import faiss
    except ImportError:
        print("sentence-transformers or faiss-cpu not installed.")
        return False

    os.makedirs(KB_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    print("Building RAG knowledge base...")
    print(f"Documents: {len(KNOWLEDGE_BASE_DOCUMENTS)}")

    # Save raw documents
    for filename, content in KNOWLEDGE_BASE_DOCUMENTS.items():
        path = os.path.join(KB_DIR, filename)
        with open(path, "w") as f:
            f.write(content.strip())

    # Chunk documents
    chunks = []
    chunk_size = 300
    overlap = 50

    for doc_name, content in KNOWLEDGE_BASE_DOCUMENTS.items():
        words = content.split()
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i:i + chunk_size]
            chunk_text = " ".join(chunk_words)
            if len(chunk_text.strip()) > 50:
                chunks.append({
                    "chunk_id": len(chunks),
                    "source": doc_name,
                    "text": chunk_text.strip(),
                    "word_count": len(chunk_words),
                })

    print(f"Total chunks: {len(chunks)}")

    # Compute embeddings
    print("Computing embeddings (all-MiniLM-L6-v2)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    embeddings = embeddings.astype(np.float32)

    # Normalize for cosine similarity
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / (norms + 1e-10)

    # Build FAISS index
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)  # Inner product = cosine similarity after normalization
    index.add(embeddings)

    print(f"FAISS index built: {index.ntotal} vectors, dim={dim}")

    # Save
    with open(INDEX_PATH, "wb") as f:
        pickle.dump({
            "index": faiss.serialize_index(index),
            "embeddings": embeddings,
            "model_name": "all-MiniLM-L6-v2",
        }, f)

    with open(CHUNKS_PATH, "w") as f:
        json.dump(chunks, f, indent=2)

    print(f"Saved index to {INDEX_PATH}")
    print(f"Saved chunks to {CHUNKS_PATH}")
    print("Knowledge base ready!")
    return True


# ── RETRIEVAL ──────────────────────────────────────────────────────────────────

_rag_index = None
_rag_chunks = None
_rag_model = None


def load_rag():
    """Load RAG index and chunks into memory (singleton)."""
    global _rag_index, _rag_chunks, _rag_model

    if _rag_index is not None:
        return True

    if not os.path.exists(INDEX_PATH):
        print("RAG index not found. Building...")
        build_knowledge_base()

    try:
        import faiss
        from sentence_transformers import SentenceTransformer

        with open(INDEX_PATH, "rb") as f:
            data = pickle.load(f)

        _rag_index = faiss.deserialize_index(data["index"])
        _rag_model = SentenceTransformer(data.get("model_name", "all-MiniLM-L6-v2"))

        with open(CHUNKS_PATH) as f:
            _rag_chunks = json.load(f)

        print(f"RAG loaded: {_rag_index.ntotal} chunks indexed")
        return True

    except Exception as e:
        print(f"RAG load error: {e}")
        return False


def search(query: str, top_k: int = 3) -> list:
    """
    Semantic search over the crew operations knowledge base.

    Args:
        query: Natural language question or rule reference
        top_k: Number of results to return

    Returns:
        List of retrieved chunks with source, text, and score
    """
    if not load_rag():
        return [{
            "source": "fallback",
            "text": "Knowledge base not available. Please rebuild the RAG index.",
            "score": 0.0,
            "chunk_id": -1,
        }]

    query_embedding = _rag_model.encode([query], convert_to_numpy=True).astype(np.float32)
    norm = np.linalg.norm(query_embedding, axis=1, keepdims=True)
    query_embedding = query_embedding / (norm + 1e-10)

    scores, indices = _rag_index.search(query_embedding, min(top_k, _rag_index.ntotal))

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx >= 0 and idx < len(_rag_chunks):
            chunk = _rag_chunks[idx]
            results.append({
                "chunk_id": chunk["chunk_id"],
                "source": chunk["source"],
                "text": chunk["text"],
                "score": round(float(score), 4),
            })

    return results


if __name__ == "__main__":
    print("=== AirCrewAI — RAG Knowledge Base ===")
    print()

    # Build the index
    success = build_knowledge_base()

    if success:
        print()
        print("=== Testing Semantic Search ===")
        print()

        test_queries = [
            "Why can't a crew member take a flight after a long delay?",
            "What is the maximum simulated duty time?",
            "How are reserve crew activated?",
            "What happens when crew misses connection?",
            "Aircraft qualification requirements",
        ]

        for query in test_queries:
            print(f"Query: {query}")
            results = search(query, top_k=2)
            for r in results:
                print(f"  [{r['source']}] score={r['score']:.3f}")
                print(f"  {r['text'][:150]}...")
            print()
