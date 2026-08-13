"""
AirCrewAI — LLM Operations Agent
Claude-powered agent that answers crew recovery questions using tool calling.

The agent has access to 6 tools:
  1. get_flight_status     — current flight delay info
  2. get_crew_risk         — ML misconnect probability + SHAP
  3. get_downstream_impact — NetworkX cascade analysis
  4. check_crew_legality   — deterministic rule checker
  5. retrieve_crew_policy  — RAG semantic search
  6. optimize_recovery     — OR-Tools + Monte Carlo

CRITICAL DESIGN PRINCIPLE:
  The LLM synthesizes and explains tool results.
  The LLM NEVER fabricates numbers or overrides tool outputs.
  All operational data comes exclusively from tool calls.

All data is SIMULATED. Not real airline operational data.
"""

import os
import sys
import json
from typing import Optional

import anthropic
from dotenv import load_dotenv

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
load_dotenv(os.path.join(_root, '.env'))

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ml"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "network"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "legality"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rag"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "optimization"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "simulation"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "external"))

# ── TOOL DEFINITIONS ───────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "get_flight_status",
        "description": (
            "Get the current status and delay information for a specific flight. "
            "Returns flight number, route, delay minutes, and status. "
            "Use this first when asked about a specific flight disruption."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "flight_number": {
                    "type": "string",
                    "description": "Flight number e.g. AA1060 or flight ID e.g. F160"
                }
            },
            "required": ["flight_number"]
        }
    },
    {
        "name": "get_crew_risk",
        "description": (
            "Get the ML-predicted misconnect risk probability for a crew member. "
            "Returns probability (0-1), risk level (LOW/MODERATE/HIGH/CRITICAL), "
            "and SHAP feature contributions explaining why the risk is high or low. "
            "Use this to assess whether a specific crew member will make their connection."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "crew_id": {
                    "type": "string",
                    "description": "Crew member ID e.g. C235"
                },
                "inbound_delay_minutes": {
                    "type": "integer",
                    "description": "How many minutes the inbound flight is delayed"
                },
                "connection_minutes": {
                    "type": "integer",
                    "description": "Scheduled connection time in minutes",
                    "default": 45
                }
            },
            "required": ["crew_id", "inbound_delay_minutes"]
        }
    },
    {
        "name": "get_downstream_impact",
        "description": (
            "Analyze the cascade effect of a flight disruption across the network. "
            "Returns which crew members are affected, which downstream flights become "
            "exposed, and the estimated cascade cost. "
            "Use this to understand the full network impact of a disruption."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "flight_id": {
                    "type": "string",
                    "description": "Flight ID e.g. F160"
                },
                "delay_minutes": {
                    "type": "integer",
                    "description": "Delay in minutes"
                }
            },
            "required": ["flight_id", "delay_minutes"]
        }
    },
    {
        "name": "check_crew_legality",
        "description": (
            "Check whether a specific crew member can legally operate a specific flight "
            "under the simulated crew operating rules. "
            "Returns legal (true/false), list of rule violations with details, "
            "and list of rules passed. "
            "Use this to verify why a crew member was rejected or approved for an assignment."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "crew_id": {
                    "type": "string",
                    "description": "Crew member ID e.g. C235"
                },
                "flight_id": {
                    "type": "string",
                    "description": "Flight ID e.g. F160"
                },
                "inbound_delay": {
                    "type": "integer",
                    "description": "Inbound delay in minutes",
                    "default": 0
                },
                "connection_minutes": {
                    "type": "integer",
                    "description": "Available connection time",
                    "default": 45
                }
            },
            "required": ["crew_id", "flight_id"]
        }
    },
    {
        "name": "retrieve_crew_policy",
        "description": (
            "Search the simulated crew operations knowledge base for relevant policy text. "
            "Returns the most relevant passages explaining crew rules, duty limits, "
            "rest requirements, qualification rules, and recovery procedures. "
            "Use this to explain WHY a rule applies, not to determine legality "
            "(use check_crew_legality for that)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language question about crew policy"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of passages to retrieve",
                    "default": 2
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "optimize_recovery",
        "description": (
            "Run the OR-Tools recovery optimizer to find the best crew assignment "
            "for a disrupted flight. Returns top 3 recovery plans (recommended, "
            "alternative, and cancellation) with costs, legality status, and "
            "Monte Carlo robustness statistics. "
            "Use this when asked for recovery recommendations or cost estimates."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "flight_id": {
                    "type": "string",
                    "description": "Flight ID to recover e.g. F160"
                },
                "delay_minutes": {
                    "type": "integer",
                    "description": "Delay in minutes"
                },
                "downstream_exposed": {
                    "type": "integer",
                    "description": "Number of downstream flights at risk",
                    "default": 1
                }
            },
            "required": ["flight_id", "delay_minutes"]
        }
    }
]

SYSTEM_PROMPT = """You are AirCrewAI, an AI operations assistant for crew disruption recovery.
You operate in a SIMULATED airline environment for portfolio demonstration purposes.
All data is synthetic — not real American Airlines data.

Your role is to help operations analysts understand crew disruptions and recovery options.

CRITICAL RULES:
1. You ONLY use data from tool calls. Never fabricate numbers, costs, or crew details.
2. You call tools BEFORE answering any operational question.
3. When asked about legality, ALWAYS call check_crew_legality — never guess.
4. When asked about costs, ALWAYS call optimize_recovery — never estimate.
5. Every response must end with: "Human review required before any operational action."
6. You explain WHAT the tools returned and WHY it matters operationally.
7. Keep responses concise and structured — operations staff need fast answers.

You have access to these tools:
- get_flight_status: Current flight delay and status
- get_crew_risk: ML misconnect probability with SHAP explanations
- get_downstream_impact: Network cascade analysis
- check_crew_legality: Deterministic rule-based legality check
- retrieve_crew_policy: Semantic search over crew policy documents
- optimize_recovery: OR-Tools optimizer + Monte Carlo simulation

Default context: Demo disruption is flight F160 (AA1060) ORD→JFK with +105 min delay.
"""


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a tool call and return the result as a JSON string."""
    try:
        if tool_name == "get_flight_status":
            from aviation_client import get_flight_status
            result = get_flight_status(tool_input["flight_number"])
            return json.dumps(result or {"error": "Flight not found"})

        elif tool_name == "get_crew_risk":
            from features import build_crew_features, load_synthetic_data
            from predict import predict_misconnect

            _, _, _, _, flights_map, crew_map, airports_map = load_synthetic_data()

            # Find next flight for crew
            from optimization.recovery_optimizer import load_data
            _, _, assignments, _, _ = load_data()

            crew_id = tool_input["crew_id"]
            inbound_delay = tool_input.get("inbound_delay_minutes", 0)
            connection_minutes = tool_input.get("connection_minutes", 45)

            next_flight_id = None
            for a in assignments:
                if a["crew_id"] == crew_id:
                    next_flight_id = a["flight_id"]
                    break

            if not next_flight_id:
                return json.dumps({"error": f"No assignment found for crew {crew_id}"})

            feat = build_crew_features(
                crew_id=crew_id,
                inbound_delay=inbound_delay,
                connection_minutes=connection_minutes,
                outbound_flight_id=next_flight_id,
                flights_map=flights_map,
                crew_map=crew_map,
                airports_map=airports_map,
            )
            result = predict_misconnect(feat)
            result["crew_id"] = crew_id
            result["next_flight_id"] = next_flight_id
            return json.dumps(result)

        elif tool_name == "get_downstream_impact":
            from optimization.recovery_optimizer import load_data
            from network_graph import build_network_graph, get_downstream_impact

            flights, crew, assignments, _, _ = load_data()
            G = build_network_graph(flights, crew, assignments)

            result = get_downstream_impact(
                tool_input["flight_id"],
                tool_input["delay_minutes"],
                G, flights, crew, assignments
            )
            return json.dumps(result)

        elif tool_name == "check_crew_legality":
            from optimization.recovery_optimizer import load_data
            from legality_engine import check_crew_legality

            _, _, _, flights_map, crew_map = load_data()
            result = check_crew_legality(
                crew_id=tool_input["crew_id"],
                flight_id=tool_input["flight_id"],
                inbound_delay=tool_input.get("inbound_delay", 0),
                connection_minutes=tool_input.get("connection_minutes", 45),
                flights_map=flights_map,
                crew_map=crew_map,
            )
            return json.dumps(result)

        elif tool_name == "retrieve_crew_policy":
            from rag_retriever import search
            results = search(tool_input["query"], top_k=tool_input.get("top_k", 2))
            return json.dumps({"query": tool_input["query"], "passages": results})

        elif tool_name == "optimize_recovery":
            from optimization.recovery_optimizer import load_data, run_recovery_optimizer
            from simulation.monte_carlo import run_monte_carlo

            flights, crew, _, flights_map, crew_map = load_data()
            result = run_recovery_optimizer(
                flight_id=tool_input["flight_id"],
                delay_minutes=tool_input["delay_minutes"],
                downstream_exposed=tool_input.get("downstream_exposed", 1),
                flights_map=flights_map,
                crew_map=crew_map,
                crew_list=crew,
            )

            if result.get("recovery_plans"):
                flight = flights_map.get(tool_input["flight_id"], {})
                mc = run_monte_carlo(
                    recovery_plans=result["recovery_plans"],
                    base_delay=tool_input["delay_minutes"],
                    passenger_count=flight.get("passenger_count", 150),
                    downstream_exposed=tool_input.get("downstream_exposed", 1),
                    n_simulations=300,
                )
                result["recovery_plans"] = mc

            return json.dumps(result, default=str)

        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

    except Exception as e:
        return json.dumps({"error": str(e), "tool": tool_name})


def run_agent(
    message: str,
    conversation_history: list = None,
    flight_id: Optional[str] = None,
) -> dict:
    """
    Run the LLM agent with tool calling.

    Args:
        message: User's question
        conversation_history: Prior conversation turns
        flight_id: Optional context flight ID

    Returns:
        dict with response, tools_used, and tool_results
    """

    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "response": "ANTHROPIC_API_KEY not configured. Please set it in your .env file.",
            "tools_used": [],
            "tool_results": [],
        }

    client = anthropic.Anthropic(api_key=api_key)

    # Build message history
    history = conversation_history or []

    # Add flight context if provided
    context_message = message
    if flight_id and flight_id not in message:
        context_message = f"[Context: Flight {flight_id}] {message}"

    history = history + [{"role": "user", "content": context_message}]

    tools_used = []
    tool_results = []
    max_iterations = 5
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=history,
        )

        # Check if agent wants to use tools
        if response.stop_reason == "tool_use":
            # Process all tool calls
            tool_calls_in_response = []
            tool_results_content = []

            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    tool_use_id = block.id

                    print(f"  Tool call: {tool_name}({json.dumps(tool_input)[:100]}...)")

                    # Execute tool
                    result_str = execute_tool(tool_name, tool_input)
                    result_data = json.loads(result_str)

                    tools_used.append({
                        "tool": tool_name,
                        "input": tool_input,
                        "id": tool_use_id,
                    })

                    tool_results.append({
                        "tool": tool_name,
                        "input": tool_input,
                        "result": result_data,
                    })

                    tool_results_content.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": result_str,
                    })

            # Add assistant response and tool results to history
            history = history + [
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": tool_results_content},
            ]

        elif response.stop_reason == "end_turn":
            # Agent has final answer
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text

            return {
                "response": final_text,
                "tools_used": tools_used,
                "tool_results": tool_results,
                "iterations": iteration,
            }
        else:
            break

    # Fallback if max iterations reached
    final_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            final_text += block.text

    return {
        "response": final_text or "Agent reached maximum iterations without a final answer.",
        "tools_used": tools_used,
        "tool_results": tool_results,
        "iterations": iteration,
    }


if __name__ == "__main__":
    print("=== AirCrewAI — LLM Operations Agent ===")
    print("NOTE: All data is SIMULATED")
    print()

    test_questions = [
        "What is the current status of flight F160?",
        "What is the misconnect risk for crew C235 given a 105 minute delay?",
        "What are the best recovery options for flight F160 with a 105 minute delay?",
        "Why can't crew C235 legally operate the next flight after a 105 minute delay?",
    ]

    print("Testing agent with demo questions...")
    print("(Requires ANTHROPIC_API_KEY in .env)")
    print()

    for q in test_questions[:1]:
        print(f"Q: {q}")
        result = run_agent(q, flight_id="F160")
        print(f"Tools used: {[t['tool'] for t in result['tools_used']]}")
        print(f"A: {result['response'][:300]}...")
        print()
