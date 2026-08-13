'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  AlertTriangle, CheckCircle, XCircle, Users,
  TrendingUp, Clock, Plane, ChevronRight, Zap,
  BarChart3, Shield, ArrowLeft, Activity
} from 'lucide-react';
import apiClient, { AnalysisResult, RecoveryPlan } from '@/lib/api';

function SeverityBadge({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    CRITICAL: 'bg-red-500/10 text-red-400 border-red-500/30',
    HIGH: 'bg-orange-500/10 text-orange-400 border-orange-500/30',
    MODERATE: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
    LOW: 'bg-green-500/10 text-green-400 border-green-500/30',
    PASS: 'bg-green-500/10 text-green-400 border-green-500/30',
    FAIL: 'bg-red-500/10 text-red-400 border-red-500/30',
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${colors[severity] || colors.LOW}`}>
      {severity}
    </span>
  );
}

function PlanCard({ plan, isSelected, onSelect }: {
  plan: RecoveryPlan;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const mc = plan.monte_carlo;
  const isCancel = plan.action === 'cancel';
  const isRecommended = plan.recommended;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      onClick={onSelect}
      className={`cursor-pointer rounded-xl border p-5 transition-all ${
        isSelected
          ? 'border-blue-500/50 bg-blue-500/5'
          : isCancel
          ? 'border-red-500/20 bg-red-500/5'
          : 'border-white/8 bg-white/[0.02] hover:bg-white/[0.04]'
      }`}
    >
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs text-gray-500 font-mono">{plan.plan_id}</span>
            {isRecommended && (
              <span className="text-xs bg-blue-500/20 text-blue-400 border border-blue-500/30 px-2 py-0.5 rounded-full font-medium">
                ★ RECOMMENDED
              </span>
            )}
          </div>
          <div className="font-bold text-white">{plan.plan_label}</div>
          {plan.crew_id && (
            <div className="text-sm text-gray-400 mt-0.5">
              {plan.crew_id} · {plan.crew_role}
              {plan.at_location && <span className="text-green-400 ml-2">● At location</span>}
            </div>
          )}
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold font-mono text-white">
            ${(plan.total_cost / 1000).toFixed(0)}K
          </div>
          <div className="text-xs text-gray-500">total cost</div>
        </div>
      </div>

      {/* Cost breakdown */}
      <div className="grid grid-cols-3 gap-3 mb-4 text-xs">
        <div className="bg-white/[0.03] rounded-lg p-2">
          <div className="text-gray-500 mb-1">Delay</div>
          <div className="text-white font-mono">${(plan.delay_cost / 1000).toFixed(0)}K</div>
        </div>
        <div className="bg-white/[0.03] rounded-lg p-2">
          <div className="text-gray-500 mb-1">Assignment</div>
          <div className="text-white font-mono">${(plan.assignment_cost / 1000).toFixed(1)}K</div>
        </div>
        <div className="bg-white/[0.03] rounded-lg p-2">
          <div className="text-gray-500 mb-1">Downstream</div>
          <div className="text-white font-mono">${(plan.downstream_penalty / 1000).toFixed(0)}K</div>
        </div>
      </div>

      {/* Monte Carlo */}
      {mc && !isCancel && (
        <div className="border-t border-white/5 pt-3">
          <div className="text-xs text-gray-500 mb-2 flex items-center gap-1">
            <BarChart3 size={10} />
            Monte Carlo ({mc.n_simulations} simulations)
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="flex justify-between">
              <span className="text-gray-500">Success rate</span>
              <span className={`font-mono font-bold ${mc.recovery_success_probability > 0.8 ? 'text-green-400' : 'text-yellow-400'}`}>
                {(mc.recovery_success_probability * 100).toFixed(0)}%
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">P90 cost</span>
              <span className="font-mono text-white">${(mc.p90_cost / 1000).toFixed(0)}K</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Expected</span>
              <span className="font-mono text-white">${(mc.expected_cost / 1000).toFixed(0)}K</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Robustness</span>
              <span className={`font-mono font-bold ${mc.robustness_score > 20 ? 'text-green-400' : 'text-yellow-400'}`}>
                {mc.robustness_score.toFixed(1)}
              </span>
            </div>
          </div>
        </div>
      )}

      <div className="mt-3 text-xs text-gray-500 leading-relaxed">
        {plan.explanation.slice(0, 120)}...
      </div>

      <div className="flex items-center gap-2 mt-3">
        <SeverityBadge severity={plan.legality_status === 'PASS' ? 'PASS' : 'FAIL'} />
        <span className="text-xs text-gray-500">
          {plan.additional_delay_minutes > 0 ? `+${plan.additional_delay_minutes} min extra delay` : 'No additional delay'}
        </span>
        {plan.flights_protected > 0 && (
          <span className="text-xs text-green-400">
            · {plan.flights_protected} flight(s) protected
          </span>
        )}
      </div>
    </motion.div>
  );
}

function ShapBar({ feature, value, direction }: { feature: string; value: number; direction: string }) {
  const isPositive = direction === 'increases_risk';
  const width = Math.min(Math.abs(value) * 20, 100);

  return (
    <div className="flex items-center gap-3 text-xs">
      <div className="w-32 text-gray-400 truncate">{feature.replace(/_/g, ' ')}</div>
      <div className="flex-1 bg-white/5 rounded-full h-1.5 overflow-hidden">
        <div
          className={`h-full rounded-full ${isPositive ? 'bg-red-500' : 'bg-green-500'}`}
          style={{ width: `${width}%` }}
        />
      </div>
      <div className={`font-mono w-16 text-right ${isPositive ? 'text-red-400' : 'text-green-400'}`}>
        {isPositive ? '+' : ''}{value.toFixed(3)}
      </div>
    </div>
  );
}

function RecoveryContent() {
  const router = useRouter();
  const params = useSearchParams();
  const flightId = params.get('flight_id') || 'F160';
  const delayMinutes = parseInt(params.get('delay') || '105');
  const flightNumber = params.get('flight_number') || 'AA1060';

  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedPlan, setSelectedPlan] = useState<string>('PLAN_A');
  const [ragQuery, setRagQuery] = useState('');
  const [ragResults, setRagResults] = useState<any[]>([]);
  const [ragLoading, setRagLoading] = useState(false);

  useEffect(() => {
    const fetchAnalysis = async () => {
      setLoading(true);
      try {
        const res = await apiClient.analyzeDisruption(flightId, delayMinutes);
        setAnalysis(res.data);
        const recommended = res.data.recovery?.recovery_plans?.find((p: RecoveryPlan) => p.recommended);
        if (recommended) setSelectedPlan(recommended.plan_id);
      } catch (err) {
        console.error('Analysis failed:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchAnalysis();
  }, [flightId, delayMinutes]);

  const handleRagSearch = async () => {
    if (!ragQuery.trim()) return;
    setRagLoading(true);
    try {
      const res = await apiClient.ragSearch(ragQuery);
      setRagResults(res.data.results || []);
    } catch (err) {
      console.error('RAG search failed:', err);
    } finally {
      setRagLoading(false);
    }
  };

  const selectedPlanData = analysis?.recovery?.recovery_plans?.find(
    (p: RecoveryPlan) => p.plan_id === selectedPlan
  );

  return (
    <div className="min-h-screen bg-[#060d1a]">
      {/* Header */}
      <div className="border-b border-white/5 bg-[#080f1e]">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-red-600 rounded-lg flex items-center justify-center">
              <Plane size={16} className="text-white" />
            </div>
            <div>
              <div className="font-bold text-white tracking-tight">AirCrewAI</div>
              <div className="text-xs text-gray-500">Crew Recovery Operations</div>
            </div>
          </div>
          <div className="text-xs text-gray-600">SIMULATED ENVIRONMENT</div>
        </div>
        <div className="max-w-7xl mx-auto px-6 flex gap-6 pb-0">
          {[
            { label: 'Operations Overview', href: '/' },
            { label: 'Recovery Center', href: '/recovery', active: true },
            { label: 'AI Copilot', href: '/copilot' },
          ].map(nav => (
            <button
              key={nav.href}
              onClick={() => router.push(nav.href)}
              className={`text-sm pb-3 border-b-2 transition-colors ${
                nav.active
                  ? 'text-white border-red-500'
                  : 'text-gray-500 border-transparent hover:text-gray-300'
              }`}
            >
              {nav.label}
            </button>
          ))}
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Disruption Header */}
        <div className="glass-card px-6 py-5 mb-6 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button onClick={() => router.push('/')} className="text-gray-500 hover:text-white transition-colors">
              <ArrowLeft size={16} />
            </button>
            <div>
              <div className="flex items-center gap-3">
                <span className="text-xl font-bold font-mono text-white">{flightNumber}</span>
                <span className="text-gray-500">·</span>
                <span className="text-gray-400">{analysis?.flight?.origin} → {analysis?.flight?.destination}</span>
                <SeverityBadge severity={analysis?.network_impact?.severity || 'HIGH'} />
              </div>
              <div className="text-sm text-gray-500 mt-0.5">
                Aircraft: {analysis?.flight?.aircraft_type} ·
                {analysis?.flight?.passenger_count} passengers ·
                Delay: <span className="text-orange-400 font-bold">+{delayMinutes} min</span>
              </div>
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs text-gray-500 mb-1">Cascade Cost</div>
            <div className="text-2xl font-bold font-mono text-red-400">
              ${((analysis?.network_impact?.estimated_cascade_cost || 0) / 1000).toFixed(0)}K
            </div>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-32 text-gray-500">
            <div className="text-center">
              <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
              <div className="text-sm">Running full analysis pipeline...</div>
              <div className="text-xs text-gray-600 mt-1">ML prediction · NetworkX · OR-Tools · Monte Carlo</div>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-12 gap-6">
            {/* Left: Crew Risk + Network Impact */}
            <div className="col-span-4 space-y-4">
              {/* Crew Risk */}
              <div className="glass-card p-5">
                <div className="flex items-center gap-2 mb-4">
                  <Users size={14} className="text-gray-500" />
                  <span className="text-sm font-semibold text-white">Crew Risk Assessment</span>
                </div>
                {analysis?.crew_risk_scores?.map((risk, i) => (
                  <div key={i} className="mb-4 last:mb-0">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-mono text-white">{risk.crew_id}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold font-mono text-red-400">
                          {(risk.misconnect_probability * 100).toFixed(0)}%
                        </span>
                        <SeverityBadge severity={risk.risk_level} />
                      </div>
                    </div>
                    {/* SHAP bars */}
                    <div className="space-y-1.5">
                      {risk.shap_contributions?.slice(0, 3).map((s: any, j: number) => (
                        <ShapBar
                          key={j}
                          feature={s.feature}
                          value={s.shap_value}
                          direction={s.direction}
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              {/* Network Impact */}
              <div className="glass-card p-5">
                <div className="flex items-center gap-2 mb-4">
                  <Activity size={14} className="text-gray-500" />
                  <span className="text-sm font-semibold text-white">Network Impact</span>
                </div>
                <div className="space-y-3">
                  {analysis?.network_impact?.affected_crew?.map((c: any, i: number) => (
                    <div key={i} className="text-sm">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-white">{c.crew_id}</span>
                        <span className="text-red-400 font-bold text-xs">{c.role}</span>
                      </div>
                      <div className="text-xs text-gray-500 mt-0.5">
                        Effective connection: <span className="text-red-400 font-mono">{c.effective_connection} min</span>
                        {c.misconnect_certain && <span className="text-red-500 ml-2">• CERTAIN MISCONNECT</span>}
                      </div>
                    </div>
                  ))}
                  {analysis?.network_impact?.immediately_exposed?.map((f: any, i: number) => (
                    <div key={i} className="bg-red-500/5 border border-red-500/20 rounded-lg p-3 text-xs">
                      <div className="flex items-center gap-2 mb-1">
                        <AlertTriangle size={10} className="text-red-400" />
                        <span className="text-red-400 font-medium">EXPOSED: {f.flight_number}</span>
                      </div>
                      <div className="text-gray-400">{f.origin} → {f.destination}</div>
                      <div className="text-gray-500 mt-1">Crew: {f.crew_id}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* RAG Policy Search */}
              <div className="glass-card p-5">
                <div className="flex items-center gap-2 mb-3">
                  <Shield size={14} className="text-gray-500" />
                  <span className="text-sm font-semibold text-white">Policy Reference</span>
                </div>
                <div className="flex gap-2 mb-3">
                  <input
                    value={ragQuery}
                    onChange={e => setRagQuery(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleRagSearch()}
                    placeholder="Search crew policies..."
                    className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-blue-500/50"
                  />
                  <button
                    onClick={handleRagSearch}
                    disabled={ragLoading}
                    className="px-3 py-2 bg-blue-600/20 border border-blue-500/30 rounded-lg text-xs text-blue-400 hover:bg-blue-600/30 transition-colors disabled:opacity-50"
                  >
                    {ragLoading ? '...' : 'Search'}
                  </button>
                </div>
                {ragResults.map((r, i) => (
                  <div key={i} className="mb-2 bg-white/[0.02] rounded-lg p-3">
                    <div className="text-xs text-blue-400 mb-1 font-medium">{r.source}</div>
                    <div className="text-xs text-gray-400 leading-relaxed line-clamp-3">{r.text}</div>
                    <div className="text-xs text-gray-600 mt-1">Score: {r.score.toFixed(3)}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Right: Recovery Plans */}
            <div className="col-span-8 space-y-4">
              <div className="glass-card p-5">
                <div className="flex items-center justify-between mb-5">
                  <div className="flex items-center gap-2">
                    <Zap size={14} className="text-yellow-500" />
                    <span className="text-sm font-semibold text-white">Recovery Plans</span>
                    <span className="text-xs text-gray-500">
                      OR-Tools CP-SAT · Monte Carlo {analysis?.recovery?.recovery_plans?.[0]?.monte_carlo?.n_simulations || 0} simulations
                    </span>
                  </div>
                  <div className="text-xs text-gray-600">
                    {analysis?.recovery?.candidates_evaluated} candidates · {analysis?.recovery?.solver_time_ms}ms
                  </div>
                </div>

                <div className="space-y-4">
                  {analysis?.recovery?.recovery_plans?.map((plan: RecoveryPlan) => (
                    <PlanCard
                      key={plan.plan_id}
                      plan={plan}
                      isSelected={selectedPlan === plan.plan_id}
                      onSelect={() => setSelectedPlan(plan.plan_id)}
                    />
                  ))}
                </div>
              </div>

              {/* Rejected Candidates */}
              {(analysis?.recovery?.rejected_candidates?.length || 0) > 0 && (
                <div className="glass-card p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <XCircle size={14} className="text-red-500" />
                    <span className="text-sm font-semibold text-white">Rejected Candidates</span>
                    <span className="text-xs text-gray-500">
                      ({analysis?.recovery?.rejected_candidates?.length} rejected)
                    </span>
                  </div>
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-left text-gray-600">
                        <th className="pb-2 font-medium">Crew ID</th>
                        <th className="pb-2 font-medium">Role</th>
                        <th className="pb-2 font-medium">Violations</th>
                      </tr>
                    </thead>
                    <tbody>
                      {analysis?.recovery?.rejected_candidates?.map((r: any, i: number) => (
                        <tr key={i} className="border-t border-white/5">
                          <td className="py-2 font-mono text-white">{r.crew_id}</td>
                          <td className="py-2 text-gray-400">{r.role}</td>
                          <td className="py-2">
                            <div className="flex gap-1 flex-wrap">
                              {r.violations?.map((v: any, j: number) => (
                                <span key={j} className="bg-red-500/10 text-red-400 border border-red-500/20 px-1.5 py-0.5 rounded text-xs">
                                  {v.rule_id}
                                </span>
                              ))}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Disclaimer */}
              <div className="text-xs text-gray-600 text-center py-2">
                ⚠️ All data is SIMULATED. Human review required before any operational action.
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function RecoveryPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#060d1a] flex items-center justify-center text-gray-500">Loading...</div>}>
      <RecoveryContent />
    </Suspense>
  );
}
