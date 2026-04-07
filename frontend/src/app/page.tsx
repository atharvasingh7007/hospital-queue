"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  Send, Users, Clock, Bell, Activity, Menu, X, ChevronRight, User,
  Phone, AlertCircle, Stethoscope, Heart, CheckCircle, Loader2,
  LogOut, Eye, EyeOff, ChevronDown, ChevronUp, Zap, Brain,
  ArrowRight, Shield, Bot, Cpu, BarChart3, Calendar,
} from "lucide-react";

/* ══════════════════════════════════════════════════════
   Types
   ══════════════════════════════════════════════════════ */

interface Message {
  id: string;
  role: "patient" | "agent";
  agentName: string;
  agentEmoji?: string;
  agentColor?: string;
  content: string;
  timestamp: Date;
  thinkingSteps?: ThinkingStep[];
  handoffs?: HandoffEvent[];
  agentsInvolved?: { name: string; emoji: string; role: string }[];
}

interface ThinkingStep {
  agent: string;
  agentName: string;
  emoji: string;
  color: string;
  text: string;
  detail: string;
}

interface HandoffEvent {
  fromAgent: string;
  fromName: string;
  toAgent: string;
  toName: string;
  text: string;
  emoji: string;
}

interface QueueEntry {
  queue_entry_id: number;
  queue_number: number;
  position: number;
  status: string;
  priority_score: number;
  symptoms: string;
  urgency_level?: string;
  estimated_wait_minutes?: number;
  checked_in_at?: string;
  patient: { id: number; name: string; phone: string; age?: number; gender?: string };
}

interface AuthUser {
  id: number;
  name: string;
  email: string;
  role: string;
  patient_id?: number;
  doctor_id?: number;
}

interface AgentInfo {
  id: string;
  name: string;
  emoji: string;
  color: string;
  role: string;
  description: string;
  status: string;
}

interface AgentActivityEntry {
  id: number;
  session_id: string;
  agent_name: string;
  action_type: string;
  thinking_text?: string;
  result_text?: string;
  detected_intent?: string;
  confidence_score?: number;
  created_at: string;
}

interface DashboardData {
  doctor: { id: number; name: string; specialty: string; consultation_duration_minutes?: number };
  queue: QueueEntry[];
  stats: { total_waiting: number; currently_consulting: number; completed_today: number; avg_consultation_minutes: number };
}

interface HospitalState {
  total_waiting: number;
  total_in_consultation: number;
  total_completed_today: number;
  avg_wait_minutes: number;
  busiest_department: string | null;
  least_busy_department: string | null;
  emergency_count: number;
  doctors: { doctor_id: number; doctor_name: string; specialty: string; waiting_patients: number; active_patients: number; estimated_clear_minutes: number; is_running_late: boolean; delay_minutes: number }[];
  departments: { department_id: number; department_name: string; total_waiting: number; total_doctors: number; avg_wait_minutes: number; congestion_level: string }[];
}

interface QueuePrediction {
  doctor_id: number;
  doctor_name: string;
  current_waiting: number;
  current_avg_wait: number;
  predicted_30min_wait: number;
  trend: string;
  recommendation: string | null;
}

interface DelayForecast {
  doctor_id: number;
  doctor_name: string;
  delay_minutes: number;
  confidence: number;
  reason: string;
  affected_patients: number;
  recommendation: string;
}

interface OptimizationReport {
  predictions: QueuePrediction[];
  rebalancing_suggestions: { from_doctor: string; to_doctor: string; patients_to_move: number; reason: string; time_saved_minutes: number }[];
  delay_forecasts: DelayForecast[];
  summary: { total_time_saved_if_rebalanced: number; patients_affected_by_delays: number; rebalancing_actions_available: number; doctors_predicted_late: number; agents_involved: string[] };
}

interface EmergencyEvent {
  level: string;
  severity: number;
  actions: { action: string; detail: string; agent: string }[];
}

/* ══════════════════════════════════════════════════════
   Constants & Helpers
   ══════════════════════════════════════════════════════ */

const API = "http://localhost:8080/api/v1";


const AGENT_ICONS: Record<string, any> = {
  nova: Bot, triage: Stethoscope, scheduler: Calendar,
  queue_manager: Users, notifier: Bell, analytics: BarChart3,
};

/** Convert markdown-ish AI responses into formatted JSX */
function formatMessage(text: string) {
  const lines = text.split("\n");
  return lines.map((line, i) => {
    // Apply inline formatting: **bold**, *italic*
    const parts: (string | JSX.Element)[] = [];
    let remaining = line;
    let partKey = 0;

    // Bold: **text**
    while (remaining.includes("**")) {
      const start = remaining.indexOf("**");
      const end = remaining.indexOf("**", start + 2);
      if (end === -1) break;
      if (start > 0) parts.push(remaining.slice(0, start));
      parts.push(<strong key={`b-${i}-${partKey++}`} className="font-semibold text-zinc-200">{remaining.slice(start + 2, end)}</strong>);
      remaining = remaining.slice(end + 2);
    }
    if (remaining) parts.push(remaining);

    // Bullet point lines
    const trimmed = line.trimStart();
    if (trimmed.startsWith("- ") || trimmed.startsWith("• ")) {
      return (
        <div key={i} className="flex gap-2 ml-1">
          <span className="text-emerald-500 mt-0.5 flex-shrink-0">•</span>
          <span>{parts.length > 1 ? parts.slice(1) : trimmed.slice(2)}</span>
        </div>
      );
    }
    // Numbered list
    const numMatch = trimmed.match(/^(\d+)[.)]\s/);
    if (numMatch) {
      return (
        <div key={i} className="flex gap-2 ml-1">
          <span className="text-amber-400 font-semibold flex-shrink-0 w-4 text-right">{numMatch[1]}.</span>
          <span>{parts.length > 1 ? parts : trimmed.slice(numMatch[0].length)}</span>
        </div>
      );
    }
    // Heading-like lines (all caps or starts with emoji)
    if (trimmed.length > 0 && trimmed === trimmed.toUpperCase() && trimmed.length < 60 && /[A-Z]/.test(trimmed)) {
      return <p key={i} className="font-bold text-xs uppercase tracking-wider text-amber-400 mt-2 mb-0.5">{parts}</p>;
    }
    // Empty line = paragraph break
    if (trimmed === "") return <div key={i} className="h-1.5" />;
    // Regular line
    return <p key={i}>{parts}</p>;
  });
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  return `${Math.floor(mins / 60)}h ago`;
}

/* ══════════════════════════════════════════════════════
   Auth Hook
   ══════════════════════════════════════════════════════ */

function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const saved = localStorage.getItem("hq_token");
    const savedUser = localStorage.getItem("hq_user");
    if (saved && savedUser) {
      setToken(saved);
      setUser(JSON.parse(savedUser));
    }
    setLoading(false);
  }, []);

  const login = async (email: string, password: string) => {
    const res = await fetch(`${API}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || "Login failed");
    const data = await res.json();
    localStorage.setItem("hq_token", data.token);
    localStorage.setItem("hq_user", JSON.stringify(data.user));
    setToken(data.token);
    setUser(data.user);
    return data;
  };

  const register = async (fields: Record<string, any>) => {
    const res = await fetch(`${API}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(fields),
    });
    if (!res.ok) throw new Error((await res.json()).detail || "Registration failed");
    const data = await res.json();
    localStorage.setItem("hq_token", data.token);
    localStorage.setItem("hq_user", JSON.stringify(data.user));
    setToken(data.token);
    setUser(data.user);
    return data;
  };

  const logout = () => {
    localStorage.removeItem("hq_token");
    localStorage.removeItem("hq_user");
    setToken(null);
    setUser(null);
  };

  return { user, token, loading, login, register, logout };
}

/* ══════════════════════════════════════════════════════
   Login Page Component
   ══════════════════════════════════════════════════════ */

function LoginPage({ onLogin, onRegister }: {
  onLogin: (email: string, password: string) => Promise<void>;
  onRegister: (fields: Record<string, any>) => Promise<void>;
}) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [role, setRole] = useState("patient");
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "login") {
        await onLogin(email, password);
      } else {
        await onRegister({ name, email, password, phone, role });
      }
    } catch (err: any) {
      setError(err.message);
    }
    setBusy(false);
  };

  const fillDemo = (type: string) => {
    if (type === "patient") {
      setEmail("patient@demo.com");
      setPassword("demo123");
    } else if (type === "doctor") {
      setEmail("doctor@demo.com");
      setPassword("demo123");
    } else {
      setEmail("admin@demo.com");
      setPassword("demo123");
    }
    setMode("login");
  };

  return (
    <div className="min-h-screen bg-[#09090b] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-500 to-indigo-600 flex items-center justify-center mx-auto mb-4 shadow-xl shadow-emerald-500/20">
            <Activity className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold gradient-text">Hospital Queue AI</h1>
          <p className="text-sm text-zinc-500 mt-1">Multi-Agent Intelligence System</p>
        </div>

        {/* Agent Chips */}
        <div className="flex justify-center gap-1.5 mb-6 flex-wrap">
          {[
            { name: "Nova", color: "#10b981", emoji: "🤖" },
            { name: "Triage", color: "#6366f1", emoji: "🏥" },
            { name: "Scheduler", color: "#f59e0b", emoji: "📅" },
            { name: "Queue", color: "#8b5cf6", emoji: "📋" },
            { name: "Notifier", color: "#ec4899", emoji: "🔔" },
            { name: "Analytics", color: "#14b8a6", emoji: "📊" },
          ].map((a) => (
            <span key={a.name} className="text-[10px] px-2 py-1 rounded-full" style={{ background: `${a.color}15`, color: a.color, border: `1px solid ${a.color}30` }}>
              {a.emoji} {a.name}
            </span>
          ))}
        </div>

        {/* Form */}
        <form onSubmit={submit} className="glass-card p-6 space-y-4">
          <div className="flex rounded-xl bg-white/[0.04] p-1 mb-2">
            <button type="button" onClick={() => setMode("login")} className={`flex-1 py-2 rounded-lg text-xs font-semibold transition-all ${mode === "login" ? "bg-emerald-500 text-white shadow-md" : "text-zinc-400"}`}>
              Sign In
            </button>
            <button type="button" onClick={() => setMode("register")} className={`flex-1 py-2 rounded-lg text-xs font-semibold transition-all ${mode === "register" ? "bg-emerald-500 text-white shadow-md" : "text-zinc-400"}`}>
              Register
            </button>
          </div>

          {mode === "register" && (
            <>
              <input id="reg-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Full Name" className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-3 text-sm input-focus placeholder:text-zinc-600" required />
              <input id="reg-phone" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Phone (+91...)" className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-3 text-sm input-focus placeholder:text-zinc-600" required />
              <div className="flex gap-2">
                {["patient", "doctor", "admin"].map((r) => (
                  <button key={r} type="button" onClick={() => setRole(r)} className={`flex-1 py-2 rounded-lg text-xs font-semibold border transition-all ${role === r ? "border-emerald-500 bg-emerald-500/10 text-emerald-400" : "border-white/[0.08] text-zinc-500"}`}>
                    {r === "patient" ? "🏥" : r === "doctor" ? "👨‍⚕️" : "🛡️"} {r.charAt(0).toUpperCase() + r.slice(1)}
                  </button>
                ))}
              </div>
            </>
          )}

          <input id="email-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-3 text-sm input-focus placeholder:text-zinc-600" required />

          <div className="relative">
            <input id="password-input" type={showPwd ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-3 text-sm input-focus placeholder:text-zinc-600 pr-10" required />
            <button type="button" onClick={() => setShowPwd(!showPwd)} className="absolute right-3 top-3 text-zinc-500 hover:text-zinc-300">
              {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>

          {error && <p className="text-xs text-red-400 bg-red-500/10 rounded-lg px-3 py-2">{error}</p>}

          <button id="auth-submit" type="submit" disabled={busy} className="w-full py-3 bg-emerald-500 hover:bg-emerald-600 disabled:bg-zinc-800 disabled:text-zinc-600 rounded-xl font-semibold text-sm transition-all shadow-lg shadow-emerald-500/20 flex items-center justify-center gap-2">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Shield className="w-4 h-4" />}
            {mode === "login" ? "Sign In" : "Create Account"}
          </button>
        </form>

        {/* Demo Credentials */}
        <div className="mt-4 glass-card p-4">
          <p className="text-[10px] text-zinc-500 uppercase tracking-widest font-semibold mb-2">Quick Demo Access</p>
          <div className="flex gap-2">
            {[
              { label: "Patient", type: "patient", color: "emerald" },
              { label: "Doctor", type: "doctor", color: "indigo" },
              { label: "Admin", type: "admin", color: "amber" },
            ].map(({ label, type, color }) => (
              <button key={type} onClick={() => fillDemo(type)} className={`flex-1 py-2 rounded-lg text-xs font-medium border border-white/[0.08] hover:border-${color}-500/30 text-zinc-400 hover:text-${color}-400 transition-all`}>
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   Thinking Panel Component
   ══════════════════════════════════════════════════════ */

function ThinkingPanel({ steps, handoffs, isLive }: {
  steps: ThinkingStep[];
  handoffs: HandoffEvent[];
  isLive: boolean;
}) {
  const [expanded, setExpanded] = useState(true);
  if (steps.length === 0 && handoffs.length === 0) return null;

  return (
    <div className={`glass-card overflow-hidden transition-all duration-300 ${isLive ? "ring-1 ring-emerald-500/20" : ""}`}>
      <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-white/[0.02] transition-colors">
        <div className="flex items-center gap-2">
          <Brain className={`w-3.5 h-3.5 ${isLive ? "text-emerald-400 animate-pulse" : "text-zinc-500"}`} />
          <span className="text-[11px] font-semibold text-zinc-400">
            {isLive ? "Agent Reasoning" : "Reasoning Complete"}
          </span>
          <span className="text-[10px] text-zinc-600">({steps.length} steps)</span>
        </div>
        {expanded ? <ChevronUp className="w-3 h-3 text-zinc-600" /> : <ChevronDown className="w-3 h-3 text-zinc-600" />}
      </button>

      {expanded && (
        <div className="px-4 pb-3 space-y-1.5">
          {steps.map((step, i) => (
            <div key={i} className="flex items-start gap-2 animate-in" style={{ animationDelay: `${i * 80}ms` }}>
              <span className="text-sm mt-0.5">{step.emoji}</span>
              <div className="flex-1 min-w-0">
                <p className="text-[11px] font-medium" style={{ color: step.color }}>
                  {step.agentName}
                </p>
                <p className="text-[11px] text-zinc-400">{step.text}</p>
                {step.detail && (
                  <p className="text-[10px] text-zinc-600 mt-0.5">{step.detail}</p>
                )}
              </div>
            </div>
          ))}

          {handoffs.map((h, i) => (
            <div key={`h-${i}`} className="flex items-center gap-2 py-1.5 animate-in">
              <div className="flex items-center gap-1 text-[10px] text-zinc-500 bg-white/[0.03] rounded-lg px-2 py-1">
                <span>{h.emoji}</span>
                <span className="text-indigo-400 font-medium">{h.fromName}</span>
                <ArrowRight className="w-2.5 h-2.5 text-zinc-600" />
                <span className="text-emerald-400 font-medium">{h.toName}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   Agent Status Bar
   ══════════════════════════════════════════════════════ */

function AgentStatusBar({ agents }: { agents: AgentInfo[] }) {
  return (
    <div className="flex items-center gap-1 overflow-x-auto pb-1">
      {agents.map((a) => (
        <div key={a.id} className="flex items-center gap-1 px-2 py-1 rounded-lg bg-white/[0.03] border border-white/[0.06] flex-shrink-0 group" title={`${a.name}: ${a.description}`}>
          <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: a.color }} />
          <span className="text-[10px] font-medium" style={{ color: a.color }}>
            {a.emoji}
          </span>
          <span className="text-[10px] text-zinc-500 hidden group-hover:inline">{a.name}</span>
        </div>
      ))}
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   Emergency Alert Banner
   ══════════════════════════════════════════════════════ */

function EmergencyBanner({ event }: { event: EmergencyEvent }) {
  return (
    <div className="animate-in mx-4 my-2">
      <div className={`rounded-xl p-4 border ${event.level === "critical" ? "bg-red-500/10 border-red-500/30" : "bg-amber-500/10 border-amber-500/30"}`}>
        <div className="flex items-center gap-2 mb-2">
          <AlertCircle className={`w-5 h-5 ${event.level === "critical" ? "text-red-400 animate-pulse" : "text-amber-400"}`} />
          <span className={`text-sm font-bold uppercase tracking-wider ${event.level === "critical" ? "text-red-400" : "text-amber-400"}`}>
            {event.level === "critical" ? "🚨 Critical Emergency" : "⚠️ Urgent Alert"}
          </span>
          <span className="ml-auto text-xs bg-red-500/20 text-red-300 px-2 py-0.5 rounded-full">
            Severity: {event.severity}/100
          </span>
        </div>
        <div className="space-y-1.5 ml-7">
          {event.actions.map((action, i) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              <span className={`w-1.5 h-1.5 rounded-full ${event.level === "critical" ? "bg-red-400" : "bg-amber-400"}`} />
              <span className="text-zinc-300 font-medium">{action.agent}</span>
              <span className="text-zinc-500">→</span>
              <span className="text-zinc-400">{action.detail}</span>
            </div>
          ))}
        </div>
        <p className="text-[10px] text-zinc-500 mt-2 ml-7">
          Autonomous action — agents detected and responded without human routing
        </p>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   Hospital Intelligence Panel
   ══════════════════════════════════════════════════════ */

function HospitalIntelPanel({ optimization }: { optimization: OptimizationReport | null }) {
  const [expanded, setExpanded] = useState(false);
  if (!optimization) return null;

  const { summary, predictions, delay_forecasts, rebalancing_suggestions } = optimization;
  const hasInsights = delay_forecasts.length > 0 || rebalancing_suggestions.length > 0;

  return (
    <div className="glass-card overflow-hidden">
      <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/[0.02] transition-colors">
        <div className="flex items-center gap-2">
          <Zap className={`w-3.5 h-3.5 ${hasInsights ? "text-amber-400" : "text-zinc-500"}`} />
          <span className="text-[11px] font-semibold text-zinc-400">Agent Intelligence</span>
          {hasInsights && <span className="text-[9px] bg-amber-500/15 text-amber-400 px-1.5 py-0.5 rounded-full">{delay_forecasts.length + rebalancing_suggestions.length} insights</span>}
        </div>
        {expanded ? <ChevronUp className="w-3 h-3 text-zinc-600" /> : <ChevronDown className="w-3 h-3 text-zinc-600" />}
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3">
          {/* Agents Working */}
          <div className="flex items-center gap-1 flex-wrap">
            {summary.agents_involved.map((a) => (
              <span key={a} className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">{a}</span>
            ))}
            <span className="text-[9px] text-zinc-600 ml-1">collaborating</span>
          </div>

          {/* Delay Forecasts */}
          {delay_forecasts.length > 0 && (
            <div>
              <p className="text-[10px] text-zinc-500 uppercase tracking-widest font-semibold mb-1.5">⏱ Delay Predictions</p>
              {delay_forecasts.map((d, i) => (
                <div key={i} className="flex items-center justify-between py-1.5 border-b border-white/[0.04] last:border-0">
                  <div>
                    <p className="text-[11px] text-zinc-300">{d.doctor_name}</p>
                    <p className="text-[9px] text-zinc-600">{d.reason}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs font-bold text-amber-400">+{d.delay_minutes}min</p>
                    <p className="text-[9px] text-zinc-600">{(d.confidence * 100).toFixed(0)}% sure</p>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Rebalancing */}
          {rebalancing_suggestions.length > 0 && (
            <div>
              <p className="text-[10px] text-zinc-500 uppercase tracking-widest font-semibold mb-1.5">⚖️ Queue Rebalancing</p>
              {rebalancing_suggestions.map((r, i) => (
                <div key={i} className="glass-card p-2 mb-1.5">
                  <div className="flex items-center gap-1.5 text-[11px]">
                    <span className="text-red-400">{r.from_doctor}</span>
                    <ArrowRight className="w-2.5 h-2.5 text-zinc-600" />
                    <span className="text-emerald-400">{r.to_doctor}</span>
                  </div>
                  <p className="text-[9px] text-zinc-500 mt-0.5">{r.patients_to_move} patient{r.patients_to_move > 1 ? "s" : ""} • saves {r.time_saved_minutes}min</p>
                </div>
              ))}
            </div>
          )}

          {/* Predictions Summary */}
          <div className="grid grid-cols-2 gap-2 pt-1">
            <div className="glass-card p-2 text-center">
              <p className="text-sm font-bold text-emerald-400">{summary.total_time_saved_if_rebalanced}m</p>
              <p className="text-[9px] text-zinc-500">Time Saveable</p>
            </div>
            <div className="glass-card p-2 text-center">
              <p className="text-sm font-bold text-amber-400">{summary.doctors_predicted_late}</p>
              <p className="text-[9px] text-zinc-500">Predicted Late</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   Main App
   ══════════════════════════════════════════════════════ */


export default function HospitalQueueApp() {
  const auth = useAuth();
  const [view, setView] = useState<"patient" | "doctor">("patient");
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Chat state
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [liveThinking, setLiveThinking] = useState<ThinkingStep[]>([]);
  const [liveHandoffs, setLiveHandoffs] = useState<HandoffEvent[]>([]);
  const [streamingText, setStreamingText] = useState("");
  const [currentAgent, setCurrentAgent] = useState<{ name: string; emoji: string; color: string } | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Dashboard state
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [selectedPatient, setSelectedPatient] = useState<QueueEntry | null>(null);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [activityLog, setActivityLog] = useState<AgentActivityEntry[]>([]);

  // Phase 1: Autonomous agent state
  const [hospitalState, setHospitalState] = useState<HospitalState | null>(null);
  const [optimization, setOptimization] = useState<OptimizationReport | null>(null);
  const [emergencyEvent, setEmergencyEvent] = useState<EmergencyEvent | null>(null);

  // Add welcome message on login
  useEffect(() => {
    if (auth.user && messages.length === 0) {
      setMessages([{
        id: "welcome",
        role: "agent",
        agentName: "Nova",
        agentEmoji: "🤖",
        agentColor: "#10b981",
        content: `👋 Namaste, ${auth.user.name}! I'm Nova, your hospital queue assistant.\n\nI coordinate a team of specialized AI agents:\n\n🏥 Triage — Symptom assessment\n📅 Scheduler — Appointments\n📋 Queue Manager — Wait times\n🔔 Notifier — Alerts\n📊 Analytics — Insights\n\nHow can I help you today?`,
        timestamp: new Date(),
      }]);
    }
  }, [auth.user]);

  // Fetch agents status
  useEffect(() => {
    fetch(`${API}/agents/status`)
      .then((r) => r.json())
      .then((d) => setAgents(d.agents || []))
      .catch(() => {});
  }, []);

  // Fetch dashboard for doctors
  useEffect(() => {
    if (auth.user?.role !== "doctor" && auth.user?.role !== "admin") return;
    const doctorId = auth.user?.doctor_id || 1;
    const fetchDashboard = () => {
      fetch(`${API}/doctor/${doctorId}/dashboard`)
        .then((r) => r.json())
        .then(setDashboard)
        .catch(() => {});
    };
    fetchDashboard();
    const timer = setInterval(fetchDashboard, 8000);
    return () => clearInterval(timer);
  }, [auth.user, view]);

  // Fetch agent activity log
  useEffect(() => {
    const fetchActivity = () => {
      fetch(`${API}/agents/activity?limit=15`)
        .then((r) => r.json())
        .then((d) => setActivityLog(d.activities || []))
        .catch(() => {});
    };
    fetchActivity();
    const timer = setInterval(fetchActivity, 10000);
    return () => clearInterval(timer);
  }, []);

  // Fetch hospital state & optimization (Phase 1)
  useEffect(() => {
    const fetchIntel = () => {
      fetch(`${API}/hospital/state`)
        .then((r) => r.json())
        .then(setHospitalState)
        .catch(() => {});
      fetch(`${API}/analytics/optimization`)
        .then((r) => r.json())
        .then(setOptimization)
        .catch(() => {});
    };
    fetchIntel();
    const timer = setInterval(fetchIntel, 12000);
    return () => clearInterval(timer);
  }, []);


  // Auto-scroll
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);
  useEffect(() => { scrollToBottom(); }, [messages, streamingText, liveThinking, scrollToBottom]);

  // Determine default view based on role
  useEffect(() => {
    if (auth.user?.role === "doctor") setView("doctor");
    else setView("patient");
  }, [auth.user]);

  /* ── Send Chat Message ───────────────────────────── */
  const sendMessage = async (text: string) => {
    if (!text.trim() || isStreaming || !auth.user) return;

    const patientId = auth.user.patient_id || 1;
    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: "patient",
      agentName: "You",
      content: text.trim(),
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInputValue("");
    setIsStreaming(true);
    setStreamingText("");
    setLiveThinking([]);
    setLiveHandoffs([]);
    setCurrentAgent(null);

    let fullResponse = "";
    const thinkingSteps: ThinkingStep[] = [];
    const handoffs: HandoffEvent[] = [];
    let agentsInvolved: { name: string; emoji: string; role: string }[] = [];
    let responseAgent = { name: "Nova", emoji: "🤖", color: "#10b981" };

    try {
      const response = await fetch(`${API}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ patient_id: patientId, agent_name: "nova", message: text.trim() }),
      });
      if (!response.ok) throw new Error(`Server returned ${response.status}`);

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No stream");
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6));
            if (event.type === "thinking") {
              const step: ThinkingStep = {
                agent: event.agent, agentName: event.agent_name,
                emoji: event.emoji, color: event.color,
                text: event.text, detail: event.detail || "",
              };
              thinkingSteps.push(step);
              setLiveThinking([...thinkingSteps]);
            } else if (event.type === "handoff") {
              const h: HandoffEvent = {
                fromAgent: event.from_agent, fromName: event.from_name,
                toAgent: event.to_agent, toName: event.to_name,
                text: event.text, emoji: event.emoji,
              };
              handoffs.push(h);
              setLiveHandoffs([...handoffs]);
            } else if (event.type === "agent_start") {
              responseAgent = { name: event.agent_name, emoji: event.emoji, color: event.color };
              setCurrentAgent(responseAgent);
            } else if (event.type === "content") {
              fullResponse += event.text;
              setStreamingText(fullResponse);
            } else if (event.type === "done") {
              agentsInvolved = event.agents_involved || [];
            } else if (event.type === "error") {
              fullResponse += event.text;
            } else if (event.type === "emergency") {
              setEmergencyEvent({
                level: event.level,
                severity: event.severity,
                actions: event.actions || [],
              });
            }
          } catch { /* skip malformed */ }
        }
      }
    } catch (err: any) {
      fullResponse = "I'm having trouble connecting right now. Please check that the backend is running and try again.";
    }

    if (fullResponse) {
      const agentMsg: Message = {
        id: `agent-${Date.now()}`,
        role: "agent",
        agentName: responseAgent.name,
        agentEmoji: responseAgent.emoji,
        agentColor: responseAgent.color,
        content: fullResponse,
        timestamp: new Date(),
        thinkingSteps,
        handoffs,
        agentsInvolved,
      };
      setMessages((prev) => [...prev, agentMsg]);
    }

    setIsStreaming(false);
    setStreamingText("");
    setLiveThinking([]);
    setLiveHandoffs([]);
    setCurrentAgent(null);
    inputRef.current?.focus();
  };

  const handleSubmit = (e: React.FormEvent) => { e.preventDefault(); sendMessage(inputValue); };
  const handleKeyDown = (e: React.KeyboardEvent) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(inputValue); } };

  /* ── Doctor Actions ──────────────────────────────── */
  const callNextPatient = async (queueEntryId: number) => {
    try { await fetch(`${API}/queue/${queueEntryId}/status?new_status=called`, { method: "PATCH" }); setSelectedPatient(null); } catch {}
  };
  const completePatient = async (queueEntryId: number) => {
    try { await fetch(`${API}/queue/${queueEntryId}/status?new_status=completed`, { method: "PATCH" }); setSelectedPatient(null); } catch {}
  };

  /* ── Loading / Auth Guard ────────────────────────── */
  if (auth.loading) {
    return (
      <div className="min-h-screen bg-[#09090b] flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-emerald-500 animate-spin" />
      </div>
    );
  }

  if (!auth.user) {
    return <LoginPage onLogin={auth.login} onRegister={auth.register} />;
  }

  const queue = dashboard?.queue || [];
  const stats = dashboard?.stats;

  /* ══════════════════════════════════════════════════
     Render — Main App
     ══════════════════════════════════════════════════ */
  return (
    <div className="min-h-screen bg-[#09090b] text-white flex">
      {/* ── Sidebar ────────────────────────────── */}
      <aside className={`${sidebarOpen ? "w-72" : "w-0"} transition-all duration-300 border-r border-white/[0.06] flex flex-col overflow-hidden flex-shrink-0`}>
        {sidebarOpen && (
          <>
            {/* Logo */}
            <div className="p-5 border-b border-white/[0.06]">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
                  <Activity className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h1 className="font-bold text-base gradient-text">Hospital Queue AI</h1>
                  <p className="text-[11px] text-zinc-500">Multi-Agent System</p>
                </div>
              </div>
            </div>

            {/* User Info */}
            <div className="p-4 border-b border-white/[0.06]">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-full bg-emerald-500/15 flex items-center justify-center ring-1 ring-emerald-500/20">
                    <User className="w-4 h-4 text-emerald-400" />
                  </div>
                  <div>
                    <p className="font-medium text-xs">{auth.user.name}</p>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                      auth.user.role === "doctor" ? "bg-indigo-500/15 text-indigo-400" :
                      auth.user.role === "admin" ? "bg-amber-500/15 text-amber-400" :
                      "bg-emerald-500/15 text-emerald-400"
                    }`}>
                      {auth.user.role}
                    </span>
                  </div>
                </div>
                <button onClick={auth.logout} className="p-1.5 rounded-lg hover:bg-white/[0.04] text-zinc-500 hover:text-red-400 transition-colors" title="Logout">
                  <LogOut className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* View Toggle (for doctors and admins) */}
            {(auth.user.role === "doctor" || auth.user.role === "admin") && (
              <div className="p-4 border-b border-white/[0.06]">
                <div className="flex rounded-xl bg-white/[0.04] p-1">
                  <button id="patient-view-toggle" onClick={() => { setView("patient"); setSelectedPatient(null); }}
                    className={`flex-1 py-2 px-3 rounded-lg text-xs font-semibold transition-all duration-200 ${view === "patient" ? "bg-emerald-500 text-white shadow-md shadow-emerald-500/25" : "text-zinc-400 hover:text-zinc-200"}`}>
                    Chat
                  </button>
                  <button id="doctor-view-toggle" onClick={() => { setView("doctor"); setSelectedPatient(null); }}
                    className={`flex-1 py-2 px-3 rounded-lg text-xs font-semibold transition-all duration-200 ${view === "doctor" ? "bg-emerald-500 text-white shadow-md shadow-emerald-500/25" : "text-zinc-400 hover:text-zinc-200"}`}>
                    Dashboard
                  </button>
                </div>
              </div>
            )}

            {/* Agent Status */}
            <div className="p-4 border-b border-white/[0.06]">
              <p className="text-[10px] text-zinc-500 uppercase tracking-widest font-semibold mb-2">Active Agents</p>
              <div className="space-y-1.5">
                {agents.map((a) => (
                  <div key={a.id} className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-white/[0.03] transition-colors">
                    <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: a.color }} />
                    <span className="text-sm">{a.emoji}</span>
                    <span className="text-[11px] text-zinc-400 flex-1">{a.name}</span>
                    <span className="text-[9px] text-zinc-600">{a.role}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Activity Log */}
            <div className="flex-1 overflow-y-auto p-4">
              <p className="text-[10px] text-zinc-500 uppercase tracking-widest font-semibold mb-2">Agent Activity</p>
              <div className="space-y-1.5">
                {activityLog.length === 0 && (
                  <p className="text-xs text-zinc-700 text-center py-4">No activity yet</p>
                )}
                {activityLog.slice(0, 10).map((a) => (
                  <div key={a.id} className="glass-card p-2 hover:bg-white/[0.03]">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-medium text-emerald-400">{a.agent_name}</span>
                      <span className="text-[9px] text-zinc-600">{timeAgo(a.created_at)}</span>
                    </div>
                    <p className="text-[10px] text-zinc-500 truncate mt-0.5">
                      {a.action_type}: {a.thinking_text || a.result_text || a.detected_intent || "—"}
                    </p>
                    {a.confidence_score && (
                      <span className="text-[9px] text-zinc-600">
                        Confidence: {(a.confidence_score * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Agent Intelligence Panel */}
            <div className="p-4 border-b border-white/[0.06]">
              <HospitalIntelPanel optimization={optimization} />
            </div>

            {/* Hospital State */}
            {hospitalState && (
              <div className="p-4 border-b border-white/[0.06]">
                <p className="text-[10px] text-zinc-500 uppercase tracking-widest font-semibold mb-2">Hospital State</p>
                <div className="grid grid-cols-3 gap-1.5">
                  <div className="glass-card p-2 text-center">
                    <p className="text-sm font-bold text-emerald-400">{hospitalState.total_waiting}</p>
                    <p className="text-[8px] text-zinc-600">Waiting</p>
                  </div>
                  <div className="glass-card p-2 text-center">
                    <p className="text-sm font-bold text-indigo-400">{hospitalState.total_in_consultation}</p>
                    <p className="text-[8px] text-zinc-600">In Consult</p>
                  </div>
                  <div className="glass-card p-2 text-center">
                    <p className="text-sm font-bold text-amber-400">{hospitalState.total_completed_today}</p>
                    <p className="text-[8px] text-zinc-600">Done</p>
                  </div>
                </div>
                {hospitalState.departments.filter(d => d.total_waiting > 0).map((d) => (
                  <div key={d.department_id} className="flex items-center justify-between mt-1.5 text-[10px]">
                    <span className="text-zinc-400">{d.department_name}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium ${
                      d.congestion_level === "critical" ? "bg-red-500/15 text-red-400" :
                      d.congestion_level === "high" ? "bg-amber-500/15 text-amber-400" :
                      d.congestion_level === "moderate" ? "bg-yellow-500/15 text-yellow-400" :
                      "bg-emerald-500/15 text-emerald-400"
                    }`}>{d.congestion_level}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Stats Footer */}
            <div className="p-4 border-t border-white/[0.06] mt-auto">
              <div className="grid grid-cols-2 gap-2">
                <div className="glass-card p-3 text-center">
                  <p className="text-lg font-bold text-emerald-400">{agents.length}</p>
                  <p className="text-[10px] text-zinc-500">Agents</p>
                </div>
                <div className="glass-card p-3 text-center">
                  <p className="text-lg font-bold text-amber-400">{stats?.total_waiting ?? 0}</p>
                  <p className="text-[10px] text-zinc-500">Waiting</p>
                </div>
              </div>
            </div>
          </>
        )}
      </aside>

      {/* ── Main Content ───────────────────────── */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="border-b border-white/[0.06] px-5 py-3.5 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3">
            <button id="sidebar-toggle" onClick={() => setSidebarOpen(!sidebarOpen)} className="p-2 rounded-lg hover:bg-white/[0.04] transition-colors">
              {sidebarOpen ? <X className="w-4 h-4 text-zinc-400" /> : <Menu className="w-4 h-4 text-zinc-400" />}
            </button>
            <div>
              <h2 className="font-semibold text-sm">
                {view === "patient" ? "AI Assistant" : "Doctor Dashboard"}
              </h2>
              <p className="text-[11px] text-zinc-500">
                {view === "patient" ? "Multi-agent orchestration powered by Gemini" : `${dashboard?.doctor?.name || "Doctor"} — ${dashboard?.doctor?.specialty || "Medicine"}`}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <AgentStatusBar agents={agents} />
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-[11px] text-emerald-400 font-medium">Active</span>
            </div>
          </div>
        </header>

        {view === "patient" ? (
          /* ══ Chat View ═══════════════════════════ */
          <>
            <div className="flex-1 overflow-y-auto p-5 chat-area">
              {/* Emergency Banner */}
              {emergencyEvent && <EmergencyBanner event={emergencyEvent} />}

              <div className="max-w-3xl mx-auto space-y-4">
                {messages.map((msg) => (
                  <div key={msg.id} className={`flex ${msg.role === "patient" ? "justify-end" : "justify-start"} animate-in`}>
                    <div className={`max-w-[80%] ${msg.role === "patient" ? "" : ""}`}>
                      {/* Thinking panel for agent messages */}
                      {msg.role === "agent" && msg.thinkingSteps && msg.thinkingSteps.length > 0 && (
                        <div className="mb-2">
                          <ThinkingPanel steps={msg.thinkingSteps} handoffs={msg.handoffs || []} isLive={false} />
                        </div>
                      )}

                      <div className={`px-4 py-3 ${msg.role === "patient" ? "bubble-sent" : "bubble-received"}`}>
                        {msg.role === "agent" && (
                          <div className="flex items-center gap-1.5 mb-1.5">
                            <span className="text-sm">{msg.agentEmoji || "🤖"}</span>
                            <p className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: msg.agentColor || "#10b981" }}>
                              {msg.agentName}
                            </p>
                          </div>
                        )}
                        <div className="text-sm leading-relaxed space-y-0.5">{formatMessage(msg.content)}</div>
                        <div className="flex items-center justify-between mt-1.5">
                          <p className="text-[9px] text-zinc-600">
                            {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                          </p>
                          {msg.agentsInvolved && msg.agentsInvolved.length > 0 && (
                            <div className="flex items-center gap-0.5">
                              {msg.agentsInvolved.map((a, i) => (
                                <span key={i} className="text-[10px]" title={`${a.name} — ${a.role}`}>{a.emoji}</span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}

                {/* Live thinking */}
                {isStreaming && (liveThinking.length > 0 || liveHandoffs.length > 0) && (
                  <div className="flex justify-start animate-in">
                    <div className="max-w-[80%]">
                      <ThinkingPanel steps={liveThinking} handoffs={liveHandoffs} isLive={true} />
                    </div>
                  </div>
                )}

                {/* Streaming response */}
                {isStreaming && streamingText && (
                  <div className="flex justify-start animate-in">
                    <div className="bubble-received max-w-[80%] px-4 py-3">
                      <div className="flex items-center gap-1.5 mb-1.5">
                        <span className="text-sm">{currentAgent?.emoji || "🤖"}</span>
                        <p className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: currentAgent?.color || "#10b981" }}>
                          {currentAgent?.name || "Nova"}
                        </p>
                      </div>
                      <div className="text-sm leading-relaxed space-y-0.5">{formatMessage(streamingText)}</div>
                      <div className="flex gap-1 mt-2">
                        {[0, 0.2, 0.4].map((d) => (
                          <span key={d} className="thinking-dot w-1.5 h-1.5 rounded-full bg-emerald-500/50" style={{ animationDelay: `${d}s` }} />
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* Thinking indicator */}
                {isStreaming && !streamingText && liveThinking.length === 0 && (
                  <div className="flex justify-start animate-in">
                    <div className="bubble-received px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Loader2 className="w-3.5 h-3.5 text-emerald-400 animate-spin" />
                        <span className="text-xs text-zinc-500">Agents processing...</span>
                      </div>
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            </div>

            <footer className="p-4 border-t border-white/[0.06] bg-[#09090b] flex-shrink-0">
              <form onSubmit={handleSubmit} className="max-w-3xl mx-auto flex gap-3">
                <textarea ref={inputRef} id="chat-input" value={inputValue} onChange={(e) => setInputValue(e.target.value)} onKeyDown={handleKeyDown}
                  placeholder="Describe your symptoms, ask about queue status, or book an appointment..."
                  className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-3 text-sm resize-none input-focus placeholder:text-zinc-600" rows={1} disabled={isStreaming} />
                <button id="send-button" type="submit" disabled={!inputValue.trim() || isStreaming}
                  className="px-5 py-3 bg-emerald-500 hover:bg-emerald-600 disabled:bg-zinc-800 disabled:text-zinc-600 rounded-xl font-medium text-sm transition-all flex items-center gap-2 shadow-lg shadow-emerald-500/20 disabled:shadow-none">
                  <Send className="w-4 h-4" />
                </button>
              </form>
              <p className="text-[10px] text-zinc-700 mt-2 text-center">
                Multi-Agent System • {agents.length} agents active • Powered by Gemini AI
              </p>
            </footer>
          </>
        ) : (
          /* ══ Doctor Dashboard ═══════════════════ */
          <div className="flex-1 overflow-y-auto p-6">
            {selectedPatient ? (
              <div className="max-w-2xl mx-auto animate-in">
                <button onClick={() => setSelectedPatient(null)} className="mb-5 text-xs text-emerald-400 hover:text-emerald-300 transition-colors flex items-center gap-1">
                  <ChevronRight className="w-3 h-3 rotate-180" /> Back to Queue
                </button>
                <div className="glass-card p-6">
                  <div className="flex items-center gap-4 mb-6 pb-6 border-b border-white/[0.06]">
                    <div className="w-14 h-14 rounded-full bg-gradient-to-br from-emerald-500/20 to-indigo-500/20 flex items-center justify-center ring-2 ring-emerald-500/20">
                      <User className="w-7 h-7 text-emerald-400" />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold">{selectedPatient.patient.name}</h3>
                      <p className="text-sm text-zinc-400">{selectedPatient.patient.age}y, {selectedPatient.patient.gender}</p>
                      <div className="flex items-center gap-1.5 mt-1"><Phone className="w-3 h-3 text-zinc-500" /><p className="text-xs text-zinc-500">{selectedPatient.patient.phone}</p></div>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-3 mb-6">
                    <div className="glass-card p-4 text-center"><p className="text-2xl font-bold text-emerald-400">#{selectedPatient.queue_number}</p><p className="text-[10px] text-zinc-500 mt-1">Queue</p></div>
                    <div className="glass-card p-4 text-center"><p className="text-2xl font-bold">#{selectedPatient.position}</p><p className="text-[10px] text-zinc-500 mt-1">Position</p></div>
                    <div className="glass-card p-4 text-center"><p className="text-2xl font-bold text-amber-400">{selectedPatient.estimated_wait_minutes ?? "—"}</p><p className="text-[10px] text-zinc-500 mt-1">Min Wait</p></div>
                  </div>
                  <div className="mb-6"><p className="text-[10px] text-zinc-500 uppercase tracking-widest font-semibold mb-2">Symptoms</p><div className="glass-card p-3"><p className="text-sm">{selectedPatient.symptoms}</p></div></div>
                  <div className="flex items-center gap-3 mb-6">
                    <span className={`status-badge ${selectedPatient.status === "waiting" ? "status-waiting" : selectedPatient.status === "called" ? "status-called" : "status-consultation"}`}>{selectedPatient.status}</span>
                    {selectedPatient.priority_score > 30 && <span className="status-badge status-emergency"><AlertCircle className="w-2.5 h-2.5" />Priority</span>}
                  </div>
                  <div className="flex gap-3">
                    {selectedPatient.status === "waiting" && <button id="call-patient-button" onClick={() => callNextPatient(selectedPatient.queue_entry_id)} className="flex-1 py-3 bg-emerald-500 hover:bg-emerald-600 rounded-xl font-semibold text-sm transition-all flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/20"><Bell className="w-4 h-4" />Call Patient</button>}
                    {(selectedPatient.status === "called" || selectedPatient.status === "consultation") && <button id="complete-patient-button" onClick={() => completePatient(selectedPatient.queue_entry_id)} className="flex-1 py-3 bg-indigo-500 hover:bg-indigo-600 rounded-xl font-semibold text-sm transition-all flex items-center justify-center gap-2 shadow-lg shadow-indigo-500/20"><CheckCircle className="w-4 h-4" />Complete</button>}
                  </div>
                </div>
              </div>
            ) : (
              <div className="max-w-2xl mx-auto">
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h3 className="text-lg font-bold">{dashboard?.doctor?.name ?? "Doctor Dashboard"}</h3>
                    <p className="text-xs text-zinc-500">{dashboard?.doctor?.specialty ?? "Medicine"} • {queue.length} in queue</p>
                  </div>
                  {stats && (
                    <div className="flex gap-2">
                      <div className="glass-card px-4 py-2 text-center"><p className="text-sm font-bold text-emerald-400">{stats.completed_today}</p><p className="text-[9px] text-zinc-500">Done Today</p></div>
                      <div className="glass-card px-4 py-2 text-center"><p className="text-sm font-bold text-amber-400">{stats.total_waiting}</p><p className="text-[9px] text-zinc-500">Waiting</p></div>
                    </div>
                  )}
                </div>
                <div className="space-y-3">
                  {queue.length === 0 && (
                    <div className="text-center py-16"><Users className="w-12 h-12 text-zinc-800 mx-auto mb-3" /><p className="text-zinc-500 text-sm">No patients in queue</p></div>
                  )}
                  {queue.map((entry) => (
                    <div key={entry.queue_entry_id} onClick={() => setSelectedPatient(entry)} className="queue-card">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                          <div className="w-11 h-11 rounded-full bg-emerald-500/10 flex items-center justify-center ring-1 ring-emerald-500/20"><span className="text-sm font-bold text-emerald-400">#{entry.queue_number}</span></div>
                          <div>
                            <p className="font-semibold text-sm">{entry.patient.name}</p>
                            <p className="text-[11px] text-zinc-500">{entry.patient.age}y, {entry.patient.gender} • Position #{entry.position}</p>
                          </div>
                        </div>
                        <div className="text-right flex items-center gap-3">
                          <span className={`status-badge ${entry.status === "waiting" ? "status-waiting" : entry.status === "called" ? "status-called" : "status-consultation"}`}>{entry.status}</span>
                          <ChevronRight className="w-4 h-4 text-zinc-600" />
                        </div>
                      </div>
                      <p className="text-xs text-zinc-500 mt-2 pl-[60px]">{entry.symptoms}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
