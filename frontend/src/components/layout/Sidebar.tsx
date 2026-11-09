"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Map,
  Bot,
  CheckSquare,
  Users,
  BarChart2,
  Eye,
  Play,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/dashboard",     label: "Command Centre",       icon: LayoutDashboard },
  { href: "/map",           label: "Crowd Intelligence",   icon: Map },
  { href: "/agents",        label: "Agent Workflow",       icon: Bot },
  { href: "/approvals",     label: "Approval Centre",      icon: CheckSquare },
  { href: "/guidance",      label: "Citizen Guidance",     icon: Users },
  { href: "/llm",           label: "LLM Gateway",          icon: BarChart2 },
  { href: "/observability", label: "Observability",        icon: Eye },
  { href: "/replay",        label: "Demo Replay",          icon: Play },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        "group/sidebar",
        "relative flex flex-col",
        "w-16 hover:w-60 transition-all duration-300 ease-out",
        "bg-bg-surface border-r border-white/[0.06]",
        "overflow-hidden shrink-0 z-20"
      )}
    >
      {/* Logo mark */}
      <div className="flex items-center gap-3 h-16 px-4 border-b border-white/[0.06] shrink-0">
        <div className="w-8 h-8 rounded-md bg-primary-500/20 border border-primary-500/40 flex items-center justify-center shrink-0">
          <span className="text-primary-400 font-bold text-sm font-mono">NX</span>
        </div>
        <span className="text-text-primary font-semibold text-sm whitespace-nowrap opacity-0 group-hover/sidebar:opacity-100 transition-opacity duration-200">
          NAMMA EXODUS
        </span>
      </div>

      {/* Nav items */}
      <nav className="flex-1 py-4 px-2 space-y-1 overflow-hidden">
        {navItems.map(({ href, label, icon: Icon }) => {
          const isActive = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "nav-item group/item",
                isActive && "active"
              )}
              title={label}
            >
              <Icon
                size={18}
                className={cn(
                  "shrink-0 transition-colors duration-200",
                  isActive ? "text-primary-400" : "text-text-muted group-hover/item:text-text-secondary"
                )}
              />
              <span className="whitespace-nowrap text-xs opacity-0 group-hover/sidebar:opacity-100 transition-opacity duration-200 truncate">
                {label}
              </span>
              {isActive && (
                <ChevronRight
                  size={12}
                  className="ml-auto text-primary-500 opacity-0 group-hover/sidebar:opacity-100 transition-opacity duration-200 shrink-0"
                />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-3 border-t border-white/[0.06]">
        <div className="h-8 flex items-center gap-2 px-2 opacity-0 group-hover/sidebar:opacity-100 transition-opacity duration-200">
          <div className="w-2 h-2 rounded-full bg-severity-low shrink-0" />
          <span className="text-xs text-text-muted whitespace-nowrap">System OK</span>
        </div>
      </div>
    </aside>
  );
}
