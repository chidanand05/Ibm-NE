import { SimulatedDataBanner } from "@/components/shared/SimulatedDataBanner";
import { PageHeader } from "@/components/shared/PageHeader";
import { GlassCard } from "@/components/shared/GlassCard";

const PROVIDERS = [
  { id: "watsonx", name: "IBM watsonx.ai (Granite 3.1)",   model: "ibm/granite-3-1-8b-instruct", role: "Primary" },
  { id: "gemini",  name: "Google Gemini 1.5 Flash",        model: "gemini/gemini-1.5-flash",      role: "Secondary" },
  { id: "groq",    name: "Groq Llama 3.1 8B Instant",      model: "groq/llama-3.1-8b-instant",    role: "Fallback" },
];

export default function LLMPage() {
  return (
    <div className="p-6 space-y-6">
      <SimulatedDataBanner />
      <PageHeader
        title="LLM Gateway Monitor"
        description="Token usage, cost tracking, and provider health for all LLM calls."
      />

      {/* Provider status */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {PROVIDERS.map((p) => (
          <GlassCard key={p.id} padding="compact">
            <div className="flex items-center justify-between mb-2">
              <span className="text-text-primary text-sm font-semibold">{p.name}</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-bg-elevated text-text-muted border border-white/[0.06]">
                {p.role}
              </span>
            </div>
            <p className="text-text-muted text-xs font-mono">{p.model}</p>
            <p className="text-text-muted text-xs mt-2">
              Health check available after Sub-task 1.4 (LLM Gateway Module).
            </p>
          </GlassCard>
        ))}
      </div>

      <GlassCard variant="warning" padding="compact">
        <p className="text-simulated text-xs font-semibold">
          Token usage and cost tracking available from Milestone 1.4 / Milestone 3.
        </p>
      </GlassCard>
    </div>
  );
}
