# AirCrewAI — Multi-Component AI Crew Disruption Recovery System

**Live Dashboard:** [aircrew-ai.vercel.app](https://aircrew-ai.vercel.app)
**Backend API:** [aircrew-ai.onrender.com](https://aircrew-ai.onrender.com)
**Author:** Abhey Sabesan Mageswaran Aryaan | MS Applied Data Science | USC Viterbi School of Engineering

---

## What Problem This Solves

Airlines run incredibly tight operations. Aircraft and crew rotate through multiple flights per day on fixed schedules. When a disruption hits, it does not just affect one flight. It triggers a cascade.

Here is what that looks like in practice. A severe weather system grounds flight AA1060 at ORD at 5am with a 105 minute delay. The captain assigned to that flight, C235, has a 72 minute scheduled connection to their next flight, AA1062 CLT to MIA. After a 105 minute delay, their effective connection drops to minus 33 minutes. They will certainly miss it. AA1062 is now uncovered. The flight attendants on AA1062 were also depending on crew from ORD. The cascade propagates downstream.

The operations team needs answers fast. Who is at risk? Which downstream flights are exposed? What is the cheapest legal recovery option? How robust is that option if conditions worsen?

AirCrewAI answers all of those questions in a single pipeline, in seconds, using a chain of AI and optimization components that each do one specific job.

This is not a dashboard that displays data. It is a decision support system that reasons through a disruption and produces ranked, costed, legally validated recovery plans.

All data in this project is synthetic and simulated. The AI components, optimization logic, and analytical methodology are production-ready and would transfer directly to real operational data.

---

## Main Objective

The core objective was to build something that demonstrates what modern AI engineering actually looks like in an operational domain. Not a Kaggle notebook. Not a simple API wrapper around a language model. A system where multiple AI techniques each solve a specific subproblem and a reasoning layer orchestrates them into a coherent operational recommendation.

In an airline context specifically, this means:

Machine learning predicts which crew members will miss their connections and explains why. Graph analysis traces which downstream flights become exposed. A constraint optimizer finds the minimum-cost legally valid crew reassignment. Probabilistic simulation tests how robust that recommendation is under uncertainty. A language model synthesizes all of it into a plain-English briefing that a crew strategy analyst can act on.

---

## Architecture

```
AviationStack API (live flight status)
          |
          v
    Flight Disruption Event
          |
          v
    XGBoost Misconnect Risk Model
    + SHAP Explainability
          |
          v
    NetworkX Cascade Propagation Graph
    (which downstream flights are exposed?)
          |
          v
    Candidate Crew Generation
          |
        +────────+
        |        |
        v        v
  Legality    RAG Knowledge Base
  Engine      (FAISS + sentence-transformers)
  (rules)     (explains policy decisions)
        |        |
        +────────+
            |
            v
      OR-Tools CP-SAT
      Recovery Optimizer
            |
            v
      Monte Carlo Simulation
      (robustness analysis)
            |
            v
      Claude LLM Agent
      (tool calling, grounded synthesis)
            |
            v
      FastAPI Backend (18 endpoints)
            |
            v
      Next.js Dashboard (3 pages)
```

Each component has exactly one job. The LLM explains tool results. The legality engine determines rule compliance. The optimizer finds minimum cost assignments. The ML model predicts misconnect probability. None of them do each other's jobs.

---

## Components Built

### 1. Synthetic Airline Data Generator

Since real crew pairing data is internal airline data that is not publicly available, I built a deterministic synthetic data generator (seed = 42) that produces a realistic airline operation for one simulated day.

The generator creates 12 airports (4 major hubs: ORD, DFW, CLT, MIA), 88 scheduled flights across the network, 250 crew members (43 reserve, 207 active) with role assignments, aircraft qualifications, duty time tracking, and base locations, and 231 crew-to-flight assignments including multi-leg crew pairings that create realistic cascade dependencies.

The canonical demo scenario is always flight AA1060 ORD to JFK with a plus 105 minute delay. This is deterministic and reproducible across all environments.

### 2. XGBoost Misconnect Risk Predictor

Trained on 5,000 synthetic crew connection records generated from the airline schedule. Each record represents one crew connection scenario with 14 engineered features.

Features include inbound delay minutes, scheduled and effective connection time, airport congestion index, hub vs non-hub indicator, hour of day, peak hour flag, accumulated duty minutes, remaining duty minutes, legs flown today, aircraft qualification match, turnaround time estimate, weather severity, and network congestion index.

The label generation function uses realistic operational thresholds: short effective connection plus high inbound delay equals high misconnect probability, with added noise to make the problem non-trivial.

Both Logistic Regression (baseline) and XGBoost (main model) are trained and evaluated. XGBoost is selected as the production model.

**Results:**
- ROC-AUC: 0.88
- PR-AUC: 0.96
- Recall: 0.79
- Cross-validation ROC-AUC: 0.86 (5-fold)

Class imbalance is handled using scale_pos_weight calibration in XGBoost rather than SMOTE, which preserves the natural data distribution during training.

SHAP (SHapley Additive exPlanations) explanations are computed for every prediction using TreeExplainer. Each prediction returns the top 5 feature contributions showing which factors most increased or decreased misconnect risk.

In the demo scenario, crew C235 with a minus 33 minute effective connection receives a misconnect probability of 99.89%, with effective connection minutes and inbound delay as the dominant positive contributors.

### 3. NetworkX Cascade Propagation Graph

A directed graph with 338 nodes (88 flight nodes and 250 crew nodes) and 263 edges representing crew-to-flight assignments and crew continuation dependencies.

The key innovation is the crew continuation edge. When the same crew member has sequential assignments, an edge connects their first flight to their second flight through them. When a disruption occurs, the traversal algorithm walks these edges to identify which downstream flights lose their crew coverage.

The algorithm checks whether effective connection time (scheduled connection minus inbound delay) falls below the 30-minute simulated minimum. If it does, the downstream flight is flagged as exposed and the traversal continues recursively up to 3 levels deep.

In the demo scenario: AA1060 delays 105 minutes, C235 CAPTAIN has effective connection of minus 33 minutes (certain misconnect), AA1062 CLT to MIA is immediately exposed as CRITICAL, estimated cascade cost $67,462.

### 4. Deterministic Legality Engine

A rule-based system that deterministically checks 7 simulated crew operating rules for any crew-flight assignment combination. The legality engine is authoritative. The LLM may explain its output but must never override it.

Rules checked:
- QUAL_01: Crew must hold qualification for the assigned aircraft type
- AVAIL_01: Crew must be marked as available
- LOC_01: Crew must be physically at the departure airport
- CONN_01: Minimum simulated connection time of 30 minutes must be satisfied
- DUTY_01: Simulated maximum duty time of 600 minutes must not be exceeded
- REST_01: Simulated minimum rest of 480 minutes must be observed
- ROLE_01: Crew role must match flight requirements

Each check returns a detailed result with the specific rule violated, current values, and threshold values. This is what powers the rejected candidates table in the dashboard.

All rules are simulated and illustrative only. They do not represent real FAA regulations or any airline's actual operating rules.

### 5. RAG Knowledge Base

8 synthetic crew operations policy documents covering duty rules, rest requirements, reserve procedures, aircraft qualification rules, connection minimums, positioning guidelines, disruption recovery guidelines, and the ML model documentation.

Documents are chunked into 300-word segments with 50-word overlap, embedded using sentence-transformers (all-MiniLM-L6-v2), normalized, and indexed with FAISS (IndexFlatIP for cosine similarity search).

At inference time, a query is embedded and the top-k most semantically similar chunks are retrieved and passed to the LLM as grounded context. The RAG system explains policy decisions. It does not determine legality.

### 6. OR-Tools CP-SAT Recovery Optimizer

The mathematical centerpiece of the project. Uses Google OR-Tools CP-SAT (Constraint Programming with Satisfiability) to find the minimum-cost legally valid crew assignment for a disrupted flight.

Mathematical formulation:

Decision variables: x[c] in {0,1} where x[c] = 1 if crew member c is assigned to the disrupted flight

Objective (minimize): total recovery cost = delay cost + crew assignment cost + reserve activation premium + location adjustment + downstream cascade penalty

Constraints: exactly one crew must be assigned (coverage), crew must be qualified (QUAL_01), crew must be available (AVAIL_01), duty time must not be exceeded (DUTY_01), location at departure airport required or repositioning cost applied (LOC_01)

The optimizer evaluates up to 20 pre-filtered candidates and returns three ranked recovery plans:

- Plan A (Recommended): OR-Tools optimal selection, minimum cost
- Plan B (Alternative): Second best feasible candidate
- Plan C (Cancel): Always available as last resort

Solver time in the demo scenario: 28 milliseconds.

Demo result: Plan A assigns C241 (First Officer, at location) at $19,975 total cost. Plan C cancellation costs $76,957. The optimizer finds a recovery that is 74% cheaper than cancellation.

### 7. Monte Carlo Robustness Simulation

500 simulations per recovery plan to assess robustness under uncertainty. Each simulation samples random variations in additional inbound delay (normally distributed, mean 15 min, std 20 min), connection time variability, crew availability risk (3% probability of becoming unavailable), and downstream cascade probability (15% chance of additional downstream disruption).

Output per plan:
- Expected cost
- Median cost
- P90 cost (worst 10% of scenarios)
- Recovery success probability
- Downstream cancellation probability
- Robustness score

This distinguishes between the cheapest expected cost plan and the most robust plan. In the demo scenario, Plan A has 84% recovery success probability and P90 cost of $86K across 500 simulations.

### 8. Claude LLM Agent with Tool Calling

A Claude claude-sonnet-4-6 powered agent that answers crew recovery questions using structured tool calling. The agent has access to 6 tools: get_flight_status, get_crew_risk, get_downstream_impact, check_crew_legality, retrieve_crew_policy, and optimize_recovery.

Critical design principle: the LLM synthesizes and explains tool results. It never fabricates numbers, never overrides the legality engine, and every response ends with a governance note requiring human review before any operational action.

The agent is multi-turn, maintains conversation history, and can chain tool calls. For example when asked "why can't C235 operate the next flight?" it calls check_crew_legality to get the specific rule violation, then calls retrieve_crew_policy to fetch the relevant policy text, then synthesizes a plain-English explanation grounded in both.

### 9. FastAPI Backend

18 REST endpoints organized around the core components. Key endpoints include GET /analyze/{flight_id} which runs the full pipeline (ML, NetworkX, optimizer, Monte Carlo) in a single call and returns a comprehensive result, POST /recovery/optimize for standalone recovery optimization, POST /copilot/query for the LLM agent, and POST /rag/search for policy retrieval.

### 10. Next.js Frontend

Three pages built with Next.js, TypeScript, Tailwind CSS, and Framer Motion.

Operations Overview shows active disruptions with severity badges, metric cards (active disruptions, crews at risk, flights monitored, estimated impact), and a disruption table with direct links to the Recovery Center.

Recovery Center is the hero page. Fully interactive with a Scenario Builder at the top: flight dropdown (8 selectable flights), delay slider (0 to 180 minutes), quick scenario presets (Minor 30 min, Moderate 60 min, Severe 105 min, Critical 150 min), and an Analyze button that triggers the full backend pipeline. Results show crew risk scores with SHAP bars, network impact with exposed flights, ranked recovery plans with Monte Carlo statistics, and a rejected candidates table with specific rule violations.

AI Copilot is a chat interface where analysts can ask natural language questions. The tool trace panel shows which tools were called for each response. Example questions are provided as clickable chips.

---

## Key Results

| Metric | Value |
|--------|-------|
| XGBoost ROC-AUC | 0.88 |
| XGBoost PR-AUC | 0.96 |
| XGBoost Recall | 0.79 |
| OR-Tools solver time | 28ms |
| Recovery cost vs cancellation | $20K vs $77K (74% cheaper) |
| Monte Carlo simulations per plan | 500 |
| Plan A success probability | 84% |
| C235 misconnect probability (demo) | 99.89% |
| Cascade cost (demo scenario) | $67,462 |
| API endpoints | 18 |
| Crew continuation edges in graph | 32 |

---

## Concepts Used

**Machine Learning and Explainability:** XGBoost gradient boosting, SHAP TreeExplainer, scale_pos_weight for class imbalance, ROC-AUC and PR-AUC evaluation, feature engineering from operational data

**Retrieval Augmented Generation:** sentence-transformers embeddings (all-MiniLM-L6-v2), FAISS vector index (IndexFlatIP, cosine similarity), semantic chunking with overlap, grounded response generation

**Operations Research and Optimization:** Google OR-Tools CP-SAT constraint programming, binary decision variables, multi-objective cost function, hard constraint encoding, feasibility checking

**Probabilistic Modeling:** Monte Carlo simulation with 500 trials, uncertainty quantification, P90 cost estimation, robustness scoring

**Graph Theory:** NetworkX directed graph, crew continuation edge construction, recursive disruption traversal, cascade impact quantification

**LLM Engineering:** Claude API tool use (function calling), multi-turn conversation management, grounded synthesis, governance guardrails, tool trace logging

**Software Engineering:** FastAPI async backend, Pydantic data validation, Next.js App Router, TypeScript, Tailwind CSS, Framer Motion, Render deployment, Vercel deployment

---

## Challenges and How I Solved Them

**Cascade modeling without real crew pairing data.** Real crew pairing is internal airline data. I solved this by building a synthetic generator that creates realistic multi-leg crew assignments with proper continuation dependencies, then calibrating the cascade multiplier against historical BTS storm data from the crew simulator project.

**SHAP incompatibility with XGBoost 3.x.** The latest XGBoost broke SHAP's TreeExplainer. I pinned XGBoost to 2.1.1 which maintains compatibility, and added a graceful fallback so the API serves predictions without SHAP explanations if the library is unavailable (relevant for production deployment constraints).

**Render deployment package conflicts.** scipy, numpy, and shap had conflicting build requirements on Render's Linux environment. I made shap optional at import time so the API deploys cleanly without it, allowing SHAP to run locally where the full environment is available.

**Ensuring the LLM never fabricates operational data.** I designed the agent so every data point in its response must come from a tool call. The system prompt explicitly prohibits estimation and requires every numerical claim to trace back to a tool result. The governance note at the end of every response reinforces this.

**Making the frontend genuinely interactive vs just a display.** The initial version loaded one hardcoded scenario. I rebuilt the Recovery Center with a Scenario Builder component: flight selector dropdown, delay slider from 0 to 180 minutes, quick presets, and a live Analyze button that calls the full backend pipeline and re-renders all results dynamically.

---

## Limitations

**Synthetic data only.** All crew pairing data is synthetic. Real crew recovery systems use individual crew schedules with FAR 117 legality constraints, domicile rules, collective bargaining agreements, and connecting passenger data. The analytical architecture would transfer to real data, but the specific numbers and patterns would differ significantly.

**Simplified legality rules.** The 7 simulated rules are illustrative. Real crew legality involves hundreds of FAR 117 sub-rules, rest facility classifications, augmented crew provisions, and contract-specific provisions that vary by crew base and role.

**No real-time flight data dependency.** The AviationStack API integration exists and works in demo mode with hardcoded fixtures. In production, live flight status would drive the disruption detection. The demo mode ensures the project works reliably for demonstrations without API quota constraints.

**LLM agent is not autonomous.** The agent is decision support, not a decision maker. Every recommendation requires human review. This is intentional and correct for safety-critical operational domains.

**Monte Carlo parameters are estimated.** The uncertainty distributions used in Monte Carlo (delay variability, crew availability risk, downstream cascade probability) are reasonable estimates rather than values fitted to historical data. With real operational data, these could be calibrated precisely.

---

## Future Scope

**Real BTS flight data integration.** The crew simulator project (Project 1) already uses 1.29 million real AA flights from BTS. Connecting that data pipeline to AirCrewAI would replace the synthetic schedule with real flight operations, making the cascade modeling genuinely data-driven.

**FAR 117 compliance engine.** Replace the 7 illustrative rules with a proper implementation of FAA Federal Aviation Regulations Part 117 (flight and duty time limitations). This is the single highest-value improvement for operational credibility.

**Reinforcement learning for recovery policy.** Train an RL agent on historical disruption and recovery data to learn recovery policies that go beyond single-event optimization. The optimizer currently solves one disruption at a time; RL could optimize across a full day of cascading disruptions.

**Real crew pairing integration.** With access to actual crew pairings (through an airline data partnership), the graph model would reflect real crew rotation sequences and the optimizer would produce legally actionable assignments.

**Streaming updates.** Replace the current request-response model with WebSocket streaming so the dashboard updates in real time as disruptions develop rather than requiring a manual Analyze trigger.

**Multi-hub simultaneous disruption.** The current model handles one disrupted flight at a time. Major weather events like the January 2026 DFW ice storm affect all hubs simultaneously. Extending the optimizer to handle multi-hub, multi-disruption scenarios is the natural next step.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, TypeScript, Tailwind CSS, Framer Motion |
| Charts and UI | Lucide React, custom CSS |
| Backend | FastAPI, uvicorn, Pydantic |
| Machine Learning | XGBoost, scikit-learn, SHAP |
| Graph Analysis | NetworkX |
| Optimization | Google OR-Tools CP-SAT |
| RAG | sentence-transformers, FAISS |
| LLM Agent | Anthropic Claude API (claude-sonnet-4-6) |
| External Data | AviationStack API (demo + live modes) |
| Deployment | Render (backend), Vercel (frontend) |
| Language | Python 3.10, TypeScript |

---

## Running Locally

```bash
# Clone the repo
git clone https://github.com/abhey-10/aircrew-ai.git
cd aircrew-ai

# Backend setup
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Generate synthetic data
python app/data/generate_airline.py

# Train the ML model
cd app/ml
python train.py
cd ../..

# Build the RAG index
cd app/rag
python rag_retriever.py
cd ../..

# Set environment variables
# Create .env in the backend folder with:
# ANTHROPIC_API_KEY=your_key_here
# FLIGHT_DATA_MODE=demo

# Start the backend
uvicorn main:app --reload --port 8000

# Frontend setup (new terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 for the dashboard and http://localhost:8000/docs for the API documentation.

---

## Project Context

This project is the second in a two-part portfolio targeting American Airlines crew strategy and analytics roles.

Project 1 (AA Crew Recovery Simulator) uses 1.29 million real BTS flights to quantify the damage from crew disruptions, validated against the January 25, 2026 DFW ice storm with 0.2% cost error on a $39.2 million event. Live at aa-dashboard-ten.vercel.app.

Project 2 (AirCrewAI) builds the AI system to find optimal recovery from those disruptions. Where Project 1 answers "what will this disruption cost?", Project 2 answers "what should we do about it?".

Together they tell a coherent story: understand the problem with real data, then build AI to solve it.

---

Abhey Sabesan Mageswaran Aryaan
MS Applied Data Science | USC Viterbi School of Engineering
GitHub: github.com/abhey-10
