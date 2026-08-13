'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  AlertTriangle, Activity, Users, Plane,
  TrendingUp, Clock, ChevronRight, RefreshCw
} from 'lucide-react';
import apiClient, { Disruption, NetworkStatus } from '@/lib/api';

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: 'badge-critical',
  HIGH: 'badge-high',
  MODERATE: 'badge-moderate',
  LOW: 'badge-low',
};

const SEVERITY_DOT: Record<string, string> = {
  CRITICAL: 'bg-red-500',
  HIGH: 'bg-orange-500',
  MODERATE: 'bg-yellow-500',
  LOW: 'bg-green-500',
};

function MetricCard({ label, value, sub, icon: Icon, color = 'text-white' }: {
  label: string;
  value: string | number;
  sub?: string;
  icon: any;
  color?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-5"
    >
      <div className="flex items-start justify-between mb-3">
        <span className="text-xs text-gray-500 uppercase tracking-widest">{label}</span>
        <Icon size={16} className="text-gray-600" />
      </div>
      <div className={`text-3xl font-bold font-mono ${color}`}>{value}</div>
      {sub && <div className="text-xs text-gray-500 mt-1">{sub}</div>}
    </motion.div>
  );
}

function DisruptionRow({ d, onAnalyze }: { d: Disruption; onAnalyze: (d: Disruption) => void }) {
  return (
    <motion.tr
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="border-b border-white/5 hover:bg-white/[0.02] transition-colors"
    >
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${SEVERITY_DOT[d.severity]}`} />
          <span className="font-mono text-sm font-medium">{d.flight_number}</span>
        </div>
      </td>
      <td className="px-4 py-3 text-sm text-gray-300">
        {d.origin} → {d.destination}
      </td>
      <td className="px-4 py-3">
        <span className="font-mono text-orange-400 text-sm font-bold">
          +{d.delay_minutes} min
        </span>
      </td>
      <td className="px-4 py-3">
        <span className={`text-xs px-2 py-1 rounded-full font-medium ${SEVERITY_COLORS[d.severity]}`}>
          {d.severity}
        </span>
      </td>
      <td className="px-4 py-3 text-sm text-gray-400">
        {d.crews_at_risk} crew · {d.downstream_exposed} downstream
      </td>
      <td className="px-4 py-3">
        <button
          onClick={() => onAnalyze(d)}
          className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors font-medium"
        >
          Analyze <ChevronRight size={12} />
        </button>
      </td>
    </motion.tr>
  );
}

export default function OperationsOverview() {
  const router = useRouter();
  const [status, setStatus] = useState<NetworkStatus | null>(null);
  const [disruptions, setDisruptions] = useState<Disruption[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const fetchData = async () => {
    try {
      const [statusRes, disruptionsRes] = await Promise.all([
        apiClient.getNetworkStatus(),
        apiClient.getActiveDisruptions(),
      ]);
      setStatus(statusRes.data);
      setDisruptions(disruptionsRes.data.disruptions);
      setLastUpdate(new Date());
    } catch (err) {
      console.error('Failed to fetch data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleAnalyze = (d: Disruption) => {
    router.push(`/recovery?flight_id=${d.flight_id}&delay=${d.delay_minutes}&flight_number=${d.flight_number}`);
  };

  const criticalCount = disruptions.filter(d => d.severity === 'CRITICAL').length;

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
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse" />
              <span className="text-xs text-yellow-500 font-medium uppercase tracking-wider">
                {status?.network_status || 'CONNECTING'}
              </span>
            </div>
            <div className="text-xs text-gray-600">
              SIMULATED ENVIRONMENT
            </div>
          </div>
        </div>

        {/* Nav */}
        <div className="max-w-7xl mx-auto px-6 flex gap-6 pb-0">
          {[
            { label: 'Operations Overview', href: '/', active: true },
            { label: 'Recovery Center', href: '/recovery' },
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
        {/* Last update */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-white">Operations Overview</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Real-time disruption monitoring — SIMULATED DATA
            </p>
          </div>
          <button
            onClick={fetchData}
            className="flex items-center gap-2 text-xs text-gray-500 hover:text-gray-300 transition-colors"
          >
            <RefreshCw size={12} />
            Updated {lastUpdate.toLocaleTimeString('en-US', { hour12: false })}
          </button>
        </div>

        {/* Metric Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <MetricCard
            label="Active Disruptions"
            value={disruptions.length}
            sub={`${criticalCount} critical`}
            icon={AlertTriangle}
            color={criticalCount > 0 ? 'text-red-400' : 'text-white'}
          />
          <MetricCard
            label="Crews At Risk"
            value={disruptions.reduce((a, d) => a + d.crews_at_risk, 0)}
            sub="misconnect risk"
            icon={Users}
            color="text-orange-400"
          />
          <MetricCard
            label="Flights Monitored"
            value={status?.flights_monitored || 88}
            sub="this simulation"
            icon={Activity}
          />
          <MetricCard
            label="Est. Impact"
            value={`$${((status?.estimated_total_impact || 83400) / 1000).toFixed(0)}K`}
            sub="cascade cost"
            icon={TrendingUp}
            color="text-yellow-400"
          />
        </div>

        {/* Disruptions Table */}
        <div className="glass-card overflow-hidden">
          <div className="px-6 py-4 border-b border-white/5 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle size={16} className="text-red-500" />
              <span className="text-sm font-semibold text-white">Active Disruptions</span>
              <span className="text-xs text-gray-500">({disruptions.length})</span>
            </div>
            <span className="text-xs text-gray-600">Click "Analyze" to open Recovery Center</span>
          </div>

          {loading ? (
            <div className="px-6 py-12 text-center text-gray-500 text-sm">
              Loading disruptions...
            </div>
          ) : disruptions.length === 0 ? (
            <div className="px-6 py-12 text-center text-gray-500 text-sm">
              No active disruptions
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="text-left">
                  {['Flight', 'Route', 'Delay', 'Severity', 'Impact', 'Action'].map(h => (
                    <th key={h} className="px-4 py-3 text-xs text-gray-600 uppercase tracking-wider font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {disruptions.map(d => (
                  <DisruptionRow key={d.disruption_id} d={d} onAnalyze={handleAnalyze} />
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Network Summary */}
        <div className="mt-6 glass-card px-6 py-4">
          <div className="flex items-center gap-2 mb-3">
            <Activity size={14} className="text-gray-500" />
            <span className="text-xs text-gray-500 uppercase tracking-wider">Network Summary</span>
          </div>
          <div className="grid grid-cols-3 gap-6 text-sm">
            <div>
              <div className="text-gray-500 text-xs mb-1">Total crew</div>
              <div className="text-white font-mono font-bold">{status?.crew_monitored || 250}</div>
            </div>
            <div>
              <div className="text-gray-500 text-xs mb-1">Network status</div>
              <div className="text-yellow-400 font-medium">{status?.network_status || 'DEGRADED'}</div>
            </div>
            <div>
              <div className="text-gray-500 text-xs mb-1">Data mode</div>
              <div className="text-blue-400 font-medium">SIMULATION</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
