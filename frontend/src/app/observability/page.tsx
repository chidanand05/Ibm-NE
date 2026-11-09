import { SimulatedDataBanner } from "@/components/shared/SimulatedDataBanner";
import { PageHeader } from "@/components/shared/PageHeader";
import { GlassCard } from "@/components/shared/GlassCard";
import { Eye, Activity, AlertCircle } from "lucide-react";

export default function ObservabilityPage() {
  return (
    <div className="p-6 space-y-6">
      <SimulatedDataBanner />
      <PageHeader
        title="Observability & Governance"
        description="Agent execution traces, audit logs, and system health monitoring."
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <GlassCard padding="compact">
          <div className="flex items-center gap-2 mb-2">
            <Activity size={14} className="text-agent-planner" />
            <span className="text-text-primary text-sm font-semibold">OpenTelemetry</span>
          </div>
          <p className="text-text-muted text-xs">
            Traces exported to Jaeger at{" "}
            <a
              href="http://localhost:16686"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary-400 hover:underline"
            >
              localhost:16686
            </a>
          </p>
        </GlassCard>

        <GlassCard padding="compact">
          <div className="flex items-center gap-2 mb-2">
            <Eye size={14} className="text-agent-forecast" />
            <span className="text-text-primary text-sm font-semibold">Agent Scorecard</span>
          </div>
          <p className="text-text-muted text-xs">
            Per-agent execution metrics available from Milestone 6.
          </p>
        </GlassCard>

        <GlassCard padding="compact">
          <div className="flex items-center gap-2 mb-2">
            <AlertCircle size={14} className="text-agent-police" />
            <span className="text-text-primary text-sm font-semibold">Audit Trail</span>
          </div>
          <p className="text-text-muted text-xs">
            All officer approvals and agent actions logged. Full UI in Milestone 4.
          </p>
        </GlassCard>
      </div>
    </div>
  );
}
