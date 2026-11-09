import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // ── Background layers ──────────────────────────────────────────────
        "bg-base": "#050D1A",
        "bg-surface": "#0A1628",
        "bg-elevated": "#0F1F35",

        // ── Primary accent — electric cyan ─────────────────────────────────
        "primary-300": "#66E8FF",
        "primary-400": "#33DEFF",
        "primary-500": "#00D4FF",
        "primary-600": "#00AACE",

        // ── Agent identity colors ──────────────────────────────────────────
        "agent-intel":    "#00D4FF", // Agent 1 — Event Intelligence (cyan)
        "agent-forecast": "#8B5CF6", // Agent 2 — Egress Forecast (violet)
        "agent-supply":   "#3B82F6", // Agent 3 — Supply (blue)
        "agent-police":   "#F97316", // Agent 4 — Police Coordination (orange)
        "agent-planner":  "#22C55E", // Agent 5 — Planner (green)
        "agent-citizen":  "#EC4899", // Agent 6 — Citizen Guidance (pink)
        "agent-learning": "#A78BFA", // Agent 7 — Learning (lavender)

        // ── Status colors ─────────────────────────────────────────────────
        "status-running":   "#00D4FF",
        "status-completed": "#22C55E",
        "status-failed":    "#EF4444",
        "status-pending":   "#64748B",
        "status-timeout":   "#F97316",

        // ── Severity (map alerts) ─────────────────────────────────────────
        "severity-low":      "#22C55E",
        "severity-medium":   "#EAB308",
        "severity-high":     "#F97316",
        "severity-critical": "#EF4444",

        // ── Transport modes ───────────────────────────────────────────────
        "mode-metro": "#8B5CF6",
        "mode-bmtc":  "#3B82F6",
        "mode-auto":  "#F59E0B",
        "mode-taxi":  "#10B981",

        // ── Simulated data indicator ─────────────────────────────────────
        "simulated": "#F59E0B",

        // ── Text ──────────────────────────────────────────────────────────
        "text-primary":   "#F8FAFC",
        "text-secondary": "#94A3B8",
        "text-muted":     "#475569",
      },

      fontFamily: {
        sans:  ["Space Grotesk", "system-ui", "sans-serif"],
        mono:  ["JetBrains Mono", "Fira Code", "monospace"],
        kn:    ["Noto Sans Kannada", "sans-serif"],
        hi:    ["Noto Sans Devanagari", "sans-serif"],
      },

      borderRadius: {
        sm:   "0.375rem",  // 6px
        md:   "0.75rem",   // 12px
        lg:   "1rem",      // 16px
        xl:   "1.5rem",    // 24px
        full: "9999px",
      },

      boxShadow: {
        "glass-sm": "0 2px 8px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.06)",
        "glass-md": "0 4px 24px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.08)",
        "glass-lg": "0 8px 48px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.10)",
        "cyan-glow":  "0 0 24px rgba(0,212,255,0.25)",
        "red-glow":   "0 0 24px rgba(239,68,68,0.25)",
        "amber-glow": "0 0 24px rgba(234,179,8,0.25)",
      },

      animation: {
        "pulse-slow": "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "ping-slow":  "ping 2s cubic-bezier(0, 0, 0.2, 1) infinite",
      },

      backdropBlur: {
        glass: "16px",
      },
    },
  },
  plugins: [],
};

export default config;
