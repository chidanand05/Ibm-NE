/** GlassCard — primary surface container for all dashboard panels. */

import { cn } from "@/lib/utils";

interface GlassCardProps {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "active" | "warning" | "danger";
  padding?: "compact" | "default" | "spacious";
}

export function GlassCard({
  children,
  className,
  variant = "default",
  padding = "default",
}: GlassCardProps) {
  return (
    <div
      className={cn(
        "glass-card",
        variant === "active"  && "glass-card-active",
        variant === "warning" && "glass-card-warning",
        variant === "danger"  && "glass-card-danger",
        padding === "compact"  && "p-4",
        padding === "default"  && "p-5",
        padding === "spacious" && "p-6",
        className
      )}
    >
      {children}
    </div>
  );
}
