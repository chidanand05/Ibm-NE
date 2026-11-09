/**
 * Shared TypeScript interfaces matching backend Pydantic schemas.
 * All types reflect the actual database schema in docs/database-schema.md.
 */

// ── Common ────────────────────────────────────────────────────────────────────

export type DataSource = "REAL" | "SIMULATED";
export type EventStatus = "SCHEDULED" | "ACTIVE" | "ENDED" | "ARCHIVED";
export type SessionStatus = "RUNNING" | "COMPLETED" | "REJECTED" | "FAILED" | "TIMEOUT";
export type AgentStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "TIMEOUT";
export type PlanStatus = "PENDING_APPROVAL" | "APPROVED" | "REJECTED" | "SUPERSEDED";
export type ApprovalDecision = "APPROVED" | "REJECTED" | "SENT_BACK";
export type TransportMode = "METRO" | "BMTC" | "AUTO" | "TAXI";
export type DemandCategory = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

// ── Venue ────────────────────────────────────────────────────────────────────

export interface Venue {
  id: string;
  name: string;
  city: string;
  address?: string;
  total_capacity: number;
  gates?: GateInfo[];
  metro_stations?: MetroStation[];
  bus_stops?: BusStop[];
  h3_center_res7?: string;
  created_at: string;
}

export interface GateInfo {
  gate_id: string;
  name: string;
  lat: number;
  lon: number;
  capacity_pct: number;
}

export interface MetroStation {
  name: string;
  line: string;
  walking_minutes: number;
  lat: number;
  lon: number;
}

export interface BusStop {
  name: string;
  routes: string[];
  walking_minutes: number;
}

// ── Event ────────────────────────────────────────────────────────────────────

export interface Event {
  id: string;
  venue_id: string;
  venue?: Venue;
  name: string;
  event_type: string;
  scheduled_start: string;
  scheduled_end: string;
  estimated_end?: string;
  estimated_attendance?: number;
  actual_attendance?: number;
  status: EventStatus;
  data_source: DataSource;
  metadata?: Record<string, unknown>;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

// ── Orchestrator Session ──────────────────────────────────────────────────────

export interface OrchestratorSession {
  id: string;
  event_id: string;
  status: SessionStatus;
  triggered_by?: string;
  trigger_type: "MANUAL" | "REPLAY" | "SCHEDULED";
  started_at: string;
  completed_at?: string;
  failed_phase?: string;
  error_message?: string;
  approval_status?: "PENDING_APPROVAL" | "APPROVED" | "REJECTED";
}

// ── Agent Execution ───────────────────────────────────────────────────────────

export type AgentId =
  | "event_intelligence"
  | "egress_forecast"
  | "supply"
  | "police_coordination"
  | "planner"
  | "citizen_guidance"
  | "learning";

export interface AgentExecution {
  id: string;
  event_id: string;
  session_id: string;
  agent_id: AgentId;
  agent_version: string;
  status: AgentStatus;
  started_at?: string;
  completed_at?: string;
  duration_ms?: number;
  input_data?: Record<string, unknown>;
  output_data?: Record<string, unknown>;
  error_message?: string;
  retry_count: number;
  model_used?: string;
  prompt_version?: string;
  total_tokens?: number;
  created_at: string;
}

// ── Action Plan ───────────────────────────────────────────────────────────────

export interface ActionPlan {
  id: string;
  event_id: string;
  session_id: string;
  status: PlanStatus;
  version: number;
  summary: string;
  strategies_considered?: Strategy[];
  recommended_strategy?: Strategy;
  metro_actions?: TransportAction[];
  bmtc_actions?: TransportAction[];
  auto_actions?: TransportAction[];
  police_actions?: PoliceAction[];
  citizen_guidance?: CitizenGuidance;
  risk_assessment?: RiskAssessment;
  confidence_score?: number;
  data_source_summary?: string;
  created_at: string;
  updated_at: string;
}

export interface Strategy {
  id: string;
  name: string;
  description: string;
  estimated_clearance_mins: number;
  safety_score: number;
  cost_score: number;
  capacity_score: number;
}

export interface TransportAction {
  mode: TransportMode;
  action: string;
  frequency_change?: string;
  zones_affected?: string[];
  estimated_capacity_increase?: number;
}

export interface PoliceAction {
  location: string;
  action: string;
  priority: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
}

export interface CitizenGuidance {
  en: GateGuidance[];
  kn: GateGuidance[];
  hi: GateGuidance[];
}

export interface GateGuidance {
  gate: string;
  recommended_transport: TransportMode[];
  instructions: string;
  walking_time?: number;
}

export interface RiskAssessment {
  overall_risk: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  risks: { description: string; mitigation: string }[];
}

// ── H3 Demand Cell ────────────────────────────────────────────────────────────

export interface H3DemandCell {
  id: number;
  forecast_id: string;
  event_id: string;
  h3_id: string;
  resolution: number;
  center_lat?: number;
  center_lon?: number;
  demand_persons: number;
  demand_category?: DemandCategory;
  horizon_minutes: number;
  data_source: DataSource;
}

// ── WebSocket Messages ────────────────────────────────────────────────────────

export type WSMessageType =
  | "connected"
  | "agent_update"
  | "plan_ready"
  | "approval_update"
  | "session_complete"
  | "error"
  | "echo";

export interface WSMessage {
  type: WSMessageType;
  session_id?: string;
  agent_id?: AgentId;
  status?: AgentStatus | PlanStatus;
  data?: Record<string, unknown>;
  message?: string;
  timestamp?: string;
}

// ── Health ────────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: "ok" | "degraded" | "error";
  service: string;
  version: string;
  llm_providers?: {
    watsonx: "healthy" | "unavailable" | "not_configured";
    gemini: "healthy" | "unavailable" | "not_configured";
    groq: "healthy" | "unavailable" | "not_configured";
  };
}

// ── API response wrapper ──────────────────────────────────────────────────────

export interface ApiError {
  detail: string;
  status_code?: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}
