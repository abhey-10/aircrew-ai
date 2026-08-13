import axios from 'axios';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

export interface Disruption {
  disruption_id: string;
  flight_id: string;
  flight_number: string;
  origin: string;
  destination: string;
  delay_minutes: number;
  disruption_type: string;
  severity: 'CRITICAL' | 'HIGH' | 'MODERATE' | 'LOW';
  crews_at_risk: number;
  downstream_exposed: number;
}

export interface NetworkStatus {
  active_disruptions: number;
  critical_disruptions: number;
  flights_monitored: number;
  crew_monitored: number;
  network_status: string;
  estimated_total_impact: number;
}

export interface RecoveryPlan {
  plan_id: string;
  plan_label: string;
  action: string;
  crew_id: string | null;
  crew_role: string | null;
  is_reserve: boolean;
  at_location: boolean;
  total_cost: number;
  delay_cost: number;
  assignment_cost: number;
  cancellation_cost: number;
  downstream_penalty: number;
  additional_delay_minutes: number;
  flights_protected: number;
  legality_status: string;
  violations: any[];
  explanation: string;
  recommended: boolean;
  monte_carlo?: {
    n_simulations: number;
    expected_cost: number;
    median_cost: number;
    p90_cost: number;
    recovery_success_probability: number;
    downstream_cancellation_probability: number;
    robustness_score: number;
  };
}

export interface AnalysisResult {
  flight_id: string;
  flight: any;
  delay_minutes: number;
  network_impact: {
    affected_crew: any[];
    immediately_exposed: any[];
    downstream_exposed: any[];
    total_exposed_flights: number;
    estimated_cascade_cost: number;
    severity: string;
  };
  crew_risk_scores: any[];
  recovery: {
    recovery_plans: RecoveryPlan[];
    candidates_evaluated: number;
    feasible_candidates: number;
    solver_time_ms: number;
    rejected_candidates: any[];
  };
}

export const apiClient = {
  getHealth: () => api.get('/health'),
  
  getNetworkStatus: () => api.get<NetworkStatus>('/network/status'),
  
  getActiveDisruptions: () => api.get<{ disruptions: Disruption[]; total: number; critical: number }>('/disruptions/active'),
  
  getDemoDisruption: () => api.get('/disruptions/demo'),
  
  analyzeDisruption: (flightId: string, delayMinutes: number) =>
    api.get<AnalysisResult>(`/analyze/${flightId}?delay_minutes=${delayMinutes}`),
  
  optimizeRecovery: (flightId: string, delayMinutes: number, downstream: number = 1) =>
    api.post('/recovery/optimize', {
      flight_id: flightId,
      delay_minutes: delayMinutes,
      downstream_exposed: downstream,
      run_monte_carlo: true,
      n_simulations: 300,
    }),
  
  checkLegality: (crewId: string, flightId: string, delay: number = 0) =>
    api.post('/legality/check', {
      crew_id: crewId,
      flight_id: flightId,
      inbound_delay: delay,
      connection_minutes: 45,
    }),
  
  ragSearch: (query: string) =>
    api.post('/rag/search', { query, top_k: 2 }),
  
  copilotQuery: (message: string, history: any[] = [], flightId?: string) =>
    api.post('/copilot/query', {
      message,
      conversation_history: history,
      flight_id: flightId,
    }),
  
  getNetworkSummary: () => api.get('/network/summary'),
};

export default apiClient;
