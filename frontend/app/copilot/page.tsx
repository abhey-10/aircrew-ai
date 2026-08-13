'use client';

import { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Plane, Send, Terminal, ChevronDown, ChevronRight, Zap } from 'lucide-react';
import apiClient from '@/lib/api';

const EXAMPLE_PROMPTS = [
  "What are the recovery options for flight F160 with 105 min delay?",
  "What is the misconnect risk for crew C235?",
  "Why can't crew C235 legally operate the next flight?",
  "What does the policy say about duty time limits?",
  "Analyze the downstream impact of the ORD disruption",
];

interface Message {
  role: 'user' | 'assistant';
  content: string;
  tools_used?: string[];
  tool_results?: any[];
  timestamp: Date;
}

function ToolTrace({ tools, results }: { tools: string[]; results: any[] }) {
  const [expanded, setExpanded] = useState(false);

  if (!tools || tools.length === 0) return null;

  return (
    <div className="mt-3 border border-white/8 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 bg-white/[0.02] text-xs text-gray-500 hover:text-gray-300 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Terminal size={10} />
          <span>{tools.length} tool{tools.length > 1 ? 's' : ''} called: {tools.join(', ')}</span>
        </div>
        {expanded ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
      </button>
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 'auto' }}
            exit={{ height: 0 }}
            className="overflow-hidden"
          >
            <div className="p-3 space-y-3 bg-black/20">
              {tools.map((tool, i) => (
                <div key={i} className="text-xs">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-green-400 font-mono">✓ {tool}</span>
                    {results?.[i]?.input && (
                      <span className="text-gray-600">
                        ({JSON.stringify(results[i].input).slice(0, 60)}...)
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user';

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      <div className={`max-w-[85%] ${isUser ? 'order-1' : ''}`}>
        {!isUser && (
          <div className="flex items-center gap-2 mb-2">
            <div className="w-5 h-5 bg-red-600 rounded flex items-center justify-center">
              <Plane size={10} className="text-white" />
            </div>
            <span className="text-xs text-gray-500">AirCrewAI Copilot</span>
            <span className="text-xs text-gray-700">
              {msg.timestamp.toLocaleTimeString()}
            </span>
          </div>
        )}
        <div className={`rounded-xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? 'bg-blue-600/20 border border-blue-500/30 text-white'
            : 'bg-white/[0.04] border border-white/8 text-gray-200'
        }`}>
          {msg.content.split('\n').map((line, i) => (
            <p key={i} className={line === '' ? 'mt-2' : ''}>
              {line}
            </p>
          ))}
        </div>
        {!isUser && msg.tools_used && msg.tools_used.length > 0 && (
          <ToolTrace tools={msg.tools_used} results={msg.tool_results || []} />
        )}
      </div>
    </motion.div>
  );
}

export default function CopilotPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: `Welcome to AirCrewAI Copilot. I'm your AI operations assistant for crew disruption recovery.

I can help you analyze flight disruptions, check crew legality, find recovery options, and explain policy decisions. All responses are grounded in tool calls — I never fabricate operational data.

Current demo context: Flight AA1060 (F160) ORD→JFK with +105 minute delay.

Try one of the example questions below, or ask your own.

⚠️ All data is SIMULATED. Human review required before any operational action.`,
      tools_used: [],
      timestamp: new Date(),
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<any[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || loading) return;

    const userMsg: Message = {
      role: 'user',
      content: text,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    const newHistory = [...history, { role: 'user', content: text }];

    try {
      const res = await apiClient.copilotQuery(text, history, 'F160');
      const data = res.data;

      const assistantMsg: Message = {
        role: 'assistant',
        content: data.response || 'No response generated.',
        tools_used: data.tools_used?.map((t: any) => t.tool) || [],
        tool_results: data.tools_used || [],
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMsg]);
      setHistory([
        ...newHistory,
        { role: 'assistant', content: data.response },
      ]);
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Failed to reach the backend. Please ensure the API server is running at localhost:8000.',
        timestamp: new Date(),
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#060d1a] flex flex-col">
      {/* Header */}
      <div className="border-b border-white/5 bg-[#080f1e] flex-shrink-0">
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
            { label: 'Recovery Center', href: '/recovery' },
            { label: 'AI Copilot', href: '/copilot', active: true },
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

      <div className="max-w-4xl mx-auto w-full px-6 py-6 flex flex-col flex-1">
        {/* Example prompts */}
        <div className="flex gap-2 flex-wrap mb-6">
          {EXAMPLE_PROMPTS.map((p, i) => (
            <button
              key={i}
              onClick={() => sendMessage(p)}
              disabled={loading}
              className="text-xs px-3 py-1.5 bg-white/[0.03] border border-white/8 rounded-full text-gray-400 hover:text-white hover:border-white/20 transition-colors disabled:opacity-50"
            >
              {p.length > 50 ? p.slice(0, 50) + '...' : p}
            </button>
          ))}
        </div>

        {/* Messages */}
        <div className="flex-1 space-y-6 overflow-y-auto scrollbar-none mb-6">
          {messages.map((msg, i) => (
            <MessageBubble key={i} msg={msg} />
          ))}
          {loading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex justify-start"
            >
              <div className="bg-white/[0.04] border border-white/8 rounded-xl px-4 py-3">
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <div className="flex gap-1">
                    {[0, 1, 2].map(i => (
                      <motion.div
                        key={i}
                        className="w-1.5 h-1.5 bg-gray-500 rounded-full"
                        animate={{ opacity: [0.3, 1, 0.3] }}
                        transition={{ duration: 1, repeat: Infinity, delay: i * 0.2 }}
                      />
                    ))}
                  </div>
                  <span>Calling tools and synthesizing response...</span>
                </div>
              </div>
            </motion.div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="glass-card p-3 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 flex-shrink-0">
              <Zap size={14} className="text-yellow-500" />
              <span className="text-xs text-gray-600 font-mono">F160</span>
            </div>
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage(input)}
              placeholder="Ask about crew recovery, legality, costs, or policy..."
              className="flex-1 bg-transparent text-sm text-white placeholder-gray-600 focus:outline-none"
              disabled={loading}
            />
            <button
              onClick={() => sendMessage(input)}
              disabled={loading || !input.trim()}
              className="p-2 bg-red-600/20 border border-red-500/30 rounded-lg text-red-400 hover:bg-red-600/30 transition-colors disabled:opacity-30"
            >
              <Send size={14} />
            </button>
          </div>
        </div>

        <div className="text-center text-xs text-gray-700 mt-3">
          All responses grounded in tool calls · Human review required before operational action
        </div>
      </div>
    </div>
  );
}
