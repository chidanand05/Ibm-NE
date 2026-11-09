"use client";

import { useEffect, useState, useCallback } from "react";
import { SimulatedDataBanner } from "@/components/shared/SimulatedDataBanner";
import { PageHeader } from "@/components/shared/PageHeader";
import { GlassCard } from "@/components/shared/GlassCard";
import { ShieldCheck, AlertTriangle, CheckCircle, XCircle, RefreshCw } from "lucide-react";
import { apiClient } from "@/lib/api";
import type { ActionPlanRecord } from "@/lib/api";

const OFFICER_ID = "officer-demo-001";

export default function ApprovalsPage() {
  const [plans, setPlans] = useState<ActionPlanRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedPlan, setSelectedPlan] = useState<ActionPlanRecord | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [comment, setComment] = useState("");
  const [actionResult, setActionResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadPlans = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.getPendingApprovals();
      setPlans(res.plans);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load plans");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPlans();
  }, [loadPlans]);

  const handleApprove = async (planId: string, sessionId: string) => {
    setActionLoading(true);
    try {
      await apiClient.approvePlan(planId, OFFICER_ID, comment || "Approved by demo officer", sessionId);
      setActionResult("✓ Plan approved. Citizen guidance and learning phases will execute.");
      setSelectedPlan(null);
      setComment("");
      setTimeout(loadPlans, 1500);
    } catch (err) {
      setActionResult(`✗ Error: ${err instanceof Error ? err.message : "Failed to approve"}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async (planId: string) => {
    setActionLoading(true);
    try {
      await apiClient.rejectPlan(planId, OFFICER_ID, comment || "Rejected by demo officer");
      setActionResult("✗ Plan rejected. Pipeline terminated.");
      setSelectedPlan(null);
      setComment("");
      setTimeout(loadPlans, 1500);
    } catch (err) {
      setActionResult(`Error: ${err instanceof Error ? err.message : "Failed to reject"}`);
    } finally {
      setActionLoading(false);
    }
  };

  const pendingPlans = plans.filter((p) => p.status === "PENDING_APPROVAL");
  const decidedPlans = plans.filter((p) => p.status !== "PENDING_APPROVAL");

  return (
    <div className="p-6 space-y-6">
      <SimulatedDataBanner />
      <PageHeader
        title="Approval Centre"
        description="Review and approve AI-generated action plans before any operational action."
        actions={
          <button
            onClick={loadPlans}
            disabled={loading}
            className="p-1.5 rounded text-text-muted hover:text-text-primary transition-colors disabled:opacity-40"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          </button>
        }
      />

      {/* Governance notice */}
      <GlassCard className="flex items-start gap-3 border-primary-500/20">
        <ShieldCheck size={18} className="text-primary-400 mt-0.5 shrink-0" />
        <div>
          <p className="text-text-primary text-sm font-semibold">Human Approval Required</p>
          <p className="text-text-secondary text-xs mt-1">
            No AI agent can autonomously dispatch vehicles, issue public instructions, or order
            evacuations. Every action plan must be explicitly approved by an authorized officer.
          </p>
        </div>
      </GlassCard>

      {error && (
        <GlassCard variant="warning" className="flex items-center gap-2">
          <AlertTriangle size={14} className="text-simulated shrink-0" />
          <p className="text-simulated text-xs">{error}</p>
        </GlassCard>
      )}

      {actionResult && (
        <GlassCard className={`flex items-center gap-2 ${actionResult.startsWith("✓") ? "border-green-500/20" : "border-red-500/20"}`}>
          <p className={`text-xs ${actionResult.startsWith("✓") ? "text-green-300" : "text-red-300"}`}>
            {actionResult}
          </p>
        </GlassCard>
      )}

      {/* Pending plans */}
      {pendingPlans.length === 0 ? (
        <GlassCard className="flex flex-col items-center py-16 gap-3">
          <AlertTriangle size={32} className="text-text-muted" />
          <p className="text-text-secondary text-sm">No plans pending approval</p>
          <p className="text-text-muted text-xs">
            Plans appear here after the orchestrator completes Phase 3 (Planner).
            Run a demo replay to generate a plan.
          </p>
        </GlassCard>
      ) : (
        <div className="space-y-4">
          <h2 className="text-text-secondary text-xs font-semibold uppercase tracking-wider">
            Pending Approval ({pendingPlans.length})
          </h2>
          {pendingPlans.map((plan) => (
            <GlassCard key={plan.id} className="border-yellow-500/20 bg-yellow-500/5">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <p className="text-yellow-300 text-sm font-semibold">Action Plan v{plan.version}</p>
                  <p className="text-text-muted text-xs mt-0.5">ID: {plan.id.slice(0, 16)}…</p>
                </div>
                <span className="text-yellow-400 text-xs font-mono bg-yellow-500/10 px-2 py-0.5 rounded">
                  PENDING
                </span>
              </div>

              <p className="text-text-secondary text-sm mb-4">{plan.summary}</p>

              {plan.confidence_score != null && (
                <p className="text-text-muted text-xs mb-3">
                  Confidence: {(plan.confidence_score * 100).toFixed(0)}% · Data: SIMULATED
                </p>
              )}

              {selectedPlan?.id === plan.id && (
                <div className="mb-3">
                  <label className="text-text-muted text-xs block mb-1">Officer comments</label>
                  <textarea
                    className="w-full rounded bg-bg-surface border border-white/[0.08] text-text-secondary text-xs p-2 resize-none focus:outline-none focus:border-primary-500/50"
                    rows={2}
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder="Optional comments…"
                  />
                </div>
              )}

              <div className="flex items-center gap-2">
                {selectedPlan?.id !== plan.id ? (
                  <button
                    onClick={() => setSelectedPlan(plan)}
                    className="px-3 py-1.5 rounded text-xs font-semibold bg-primary-500/20 border border-primary-500/30 text-primary-400 hover:bg-primary-500/30 transition-colors"
                  >
                    Review
                  </button>
                ) : (
                  <>
                    <button
                      onClick={() => handleApprove(plan.id, plan.session_id)}
                      disabled={actionLoading}
                      className="flex items-center gap-1 px-3 py-1.5 rounded text-xs font-semibold bg-green-500/20 border border-green-500/30 text-green-400 hover:bg-green-500/30 transition-colors disabled:opacity-50"
                    >
                      <CheckCircle size={12} />
                      Approve
                    </button>
                    <button
                      onClick={() => handleReject(plan.id)}
                      disabled={actionLoading}
                      className="flex items-center gap-1 px-3 py-1.5 rounded text-xs font-semibold bg-red-500/20 border border-red-500/30 text-red-400 hover:bg-red-500/30 transition-colors disabled:opacity-50"
                    >
                      <XCircle size={12} />
                      Reject
                    </button>
                    <button
                      onClick={() => setSelectedPlan(null)}
                      className="text-text-muted text-xs hover:text-text-primary transition-colors"
                    >
                      Cancel
                    </button>
                  </>
                )}
              </div>
            </GlassCard>
          ))}
        </div>
      )}

      {/* Decided plans */}
      {decidedPlans.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-text-secondary text-xs font-semibold uppercase tracking-wider">
            Recent Decisions ({decidedPlans.length})
          </h2>
          {decidedPlans.slice(0, 5).map((plan) => (
            <GlassCard key={plan.id} padding="compact" className={plan.status === "APPROVED" ? "border-green-500/15" : "border-red-500/15"}>
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-text-secondary text-xs">Plan {plan.id.slice(0, 8)}… · </span>
                  <span className="text-text-muted text-xs">{plan.summary?.slice(0, 80)}…</span>
                </div>
                <span className={`text-xs font-mono px-2 py-0.5 rounded ${plan.status === "APPROVED" ? "text-green-400 bg-green-500/10" : "text-red-400 bg-red-500/10"}`}>
                  {plan.status}
                </span>
              </div>
            </GlassCard>
          ))}
        </div>
      )}
    </div>
  );
}
