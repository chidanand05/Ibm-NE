"use client";

import { useState, useCallback } from "react";
import { SimulatedDataBanner } from "@/components/shared/SimulatedDataBanner";
import { PageHeader } from "@/components/shared/PageHeader";
import { GlassCard } from "@/components/shared/GlassCard";
import { AlertTriangle, Globe, Loader2 } from "lucide-react";
import { apiClient } from "@/lib/api";
import type { GuidanceResponse } from "@/lib/api";

const DEMO_EVENT_ID = "20000000-0000-0000-0000-000000000001";
const LANGUAGES = ["english", "kannada", "hindi"] as const;
const LANG_LABELS: Record<string, string> = { english: "English", kannada: "ಕನ್ನಡ", hindi: "हिंदी" };

export default function GuidancePage() {
  const [guidance, setGuidance] = useState<GuidanceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeLang, setActiveLang] = useState<"english" | "kannada" | "hindi">("english");

  const generateGuidance = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.generateGuidance(
        DEMO_EVENT_ID,
        "RCB vs CSK IPL 2026",
        30000,
      );
      setGuidance(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate guidance");
    } finally {
      setLoading(false);
    }
  }, []);

  return (
    <div className="p-6 space-y-6">
      {/* Safety disclaimer */}
      <div
        className="w-full flex items-start gap-3 px-4 py-3 bg-severity-critical/10 border border-severity-critical/30 rounded-md"
        role="alert"
      >
        <AlertTriangle size={16} className="text-severity-critical mt-0.5 shrink-0" />
        <p className="text-severity-critical text-xs font-semibold">
          ⚠ SIMULATED GUIDANCE — AI-generated from synthetic data for demonstration purposes only.
          Do NOT use for real navigation or emergency decisions.
        </p>
      </div>

      <SimulatedDataBanner />

      <PageHeader
        title="Citizen Guidance"
        description="Gate-specific travel instructions in English, Kannada, and Hindi."
        actions={
          <button
            onClick={generateGuidance}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-primary-500/20 border border-primary-500/40 text-primary-400 text-xs font-semibold hover:bg-primary-500/30 transition-colors disabled:opacity-50"
          >
            {loading ? <Loader2 size={12} className="animate-spin" /> : <Globe size={12} />}
            {loading ? "Generating…" : "Generate Guidance"}
          </button>
        }
      />

      {error && (
        <GlassCard variant="warning" className="flex items-center gap-2">
          <AlertTriangle size={14} className="text-simulated shrink-0" />
          <p className="text-simulated text-xs">{error}</p>
        </GlassCard>
      )}

      {/* Language selector */}
      <div className="flex gap-2">
        {LANGUAGES.map((lang) => (
          <button
            key={lang}
            onClick={() => setActiveLang(lang)}
            className={`px-4 py-2 text-sm rounded-md border transition-colors ${
              activeLang === lang
                ? "bg-primary-500/20 border-primary-500/40 text-primary-400"
                : "bg-bg-surface border-white/[0.08] text-text-secondary hover:text-text-primary hover:bg-white/5"
            }`}
          >
            {LANG_LABELS[lang]}
          </button>
        ))}
      </div>

      {guidance ? (
        <div className="space-y-4">
          {/* General guidance */}
          <GlassCard>
            <h3 className="text-text-secondary text-xs font-semibold uppercase tracking-wider mb-2">
              General Instructions
            </h3>
            <p className="text-text-primary text-sm">
              {guidance.general_guidance[activeLang] || "—"}
            </p>
          </GlassCard>

          {/* Metro instructions */}
          <GlassCard>
            <h3 className="text-text-secondary text-xs font-semibold uppercase tracking-wider mb-2">
              Metro Instructions
            </h3>
            <p className="text-text-primary text-sm">
              {guidance.metro_instructions[activeLang] || "—"}
            </p>
          </GlassCard>

          {/* Safety message */}
          {guidance.safety_message[activeLang] && (
            <GlassCard className="border-severity-critical/20 bg-severity-critical/5">
              <h3 className="text-severity-critical text-xs font-semibold uppercase tracking-wider mb-2">
                Safety Message
              </h3>
              <p className="text-text-primary text-sm">
                {guidance.safety_message[activeLang]}
              </p>
            </GlassCard>
          )}

          {/* Gate-specific guidance */}
          {Object.keys(guidance.guidance_by_gate).length > 0 && (
            <div>
              <h3 className="text-text-secondary text-xs font-semibold uppercase tracking-wider mb-3">
                Gate Instructions
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                {Object.entries(guidance.guidance_by_gate).map(([gateId, msgs]) => {
                  const seq = guidance.gate_sequence.find((g) => g.gate_id === gateId);
                  return (
                    <GlassCard key={gateId} padding="compact">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-text-primary text-sm font-semibold">Gate {gateId}</span>
                        {seq && (
                          <span className="text-text-muted text-xs">
                            Opens T+{seq.delay_minutes}min
                          </span>
                        )}
                      </div>
                      <p className="text-text-secondary text-xs">{msgs[activeLang] || "—"}</p>
                    </GlassCard>
                  );
                })}
              </div>
            </div>
          )}

          {guidance.llm_fallback && (
            <p className="text-simulated text-xs text-center">
              ⚠ LLM unavailable — showing deterministic fallback guidance
            </p>
          )}
        </div>
      ) : !loading && (
        <GlassCard className="flex flex-col items-center py-16 gap-3">
          <Globe size={32} className="text-text-muted" />
          <p className="text-text-secondary text-sm">No guidance generated yet</p>
          <p className="text-text-muted text-xs">
            Click &quot;Generate Guidance&quot; to run Agent 6 and produce multilingual instructions.
          </p>
        </GlassCard>
      )}
    </div>
  );
}
