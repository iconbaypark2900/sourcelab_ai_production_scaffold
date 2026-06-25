"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { SourceLabApiError, API_BASE_URL } from "@/lib/sourcelab-api";

/* ---------------------------------------------------------------------------
 * Top navigation
 * ------------------------------------------------------------------------- */

const NAV_LINKS: Array<{ href: string; label: string }> = [
  { href: "/", label: "Library" },
  { href: "/runs", label: "Sessions" },
  { href: "/runs/new", label: "Start lesson" },
  { href: "/batches", label: "Study Sets" },
  { href: "/runs/compare", label: "Compare" },
  { href: "/source-packs", label: "Collections" },
  { href: "/curriculum", label: "Progress" },
  { href: "/evals", label: "Evals" },
  { href: "/release", label: "Release" },
  { href: "/api-health", label: "API Health" },
];

export function AppNav() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-30 border-b border-[var(--sl-border)] bg-[rgba(5,7,15,0.72)] backdrop-blur-xl">
      <div className="mx-auto flex max-w-[1500px] items-center gap-6 px-5 py-3">
        <Link href="/" className="flex items-center gap-2.5">
          <span className="sl-drift inline-flex h-7 w-7 items-center justify-center rounded-lg border border-[rgba(34,211,238,0.4)] bg-[rgba(34,211,238,0.12)] text-[var(--sl-cyan)]">
            <FieldGlyph />
          </span>
          <span className="flex flex-col leading-tight">
            <span className="text-sm font-semibold tracking-tight text-white">
              SourceLab <span className="sl-gradient-text">Research Library</span>
            </span>
            <span className="text-[0.62rem] uppercase tracking-[0.18em] text-[var(--sl-text-faint)]">
              Run Studio
            </span>
          </span>
        </Link>

        <nav className="ml-auto flex items-center gap-1">
          {NAV_LINKS.map((link) => {
            const active =
              link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`rounded-lg px-3 py-1.5 text-sm transition-colors ${
                  active
                    ? "bg-[rgba(34,211,238,0.12)] text-white"
                    : "text-[var(--sl-text-dim)] hover:text-white"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}

function FieldGlyph() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
      <circle cx="8" cy="8" r="2" fill="currentColor" />
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1" opacity="0.5" />
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1" opacity="0.5" />
    </svg>
  );
}

/* ---------------------------------------------------------------------------
 * Layout helpers
 * ------------------------------------------------------------------------- */

export function PageShell({ children }: { children: ReactNode }) {
  return (
    <main className="sl-fieldgrid relative min-h-screen">
      <div className="relative z-10 mx-auto max-w-[1500px] px-5 py-7">{children}</div>
    </main>
  );
}

export function PageHeader({
  title,
  subtitle,
  children,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-[var(--sl-text-dim)]">{subtitle}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}

export function Panel({
  title,
  hint,
  action,
  glow,
  className = "",
  bodyClassName = "",
  id,
  children,
}: {
  title?: ReactNode;
  hint?: ReactNode;
  action?: ReactNode;
  glow?: "cyan" | "violet";
  className?: string;
  bodyClassName?: string;
  id?: string;
  children: ReactNode;
}) {
  const glowClass =
    glow === "cyan" ? "sl-panel--glow-cyan" : glow === "violet" ? "sl-panel--glow-violet" : "";
  return (
    <section id={id} className={`sl-panel ${glowClass} ${className}`}>
      {(title || action) && (
        <div className="flex items-start justify-between gap-3 px-4 pt-3.5">
          <div>
            {title && <h2 className="sl-panel-title">{title}</h2>}
            {hint && <p className="mt-0.5 text-[0.72rem] text-[var(--sl-text-faint)]">{hint}</p>}
          </div>
          {action && <div className="flex items-center gap-2">{action}</div>}
        </div>
      )}
      <div className={`px-4 pb-4 ${title || action ? "pt-3" : "pt-4"} ${bodyClassName}`}>
        {children}
      </div>
    </section>
  );
}

export function Metric({
  label,
  value,
  tone = "default",
  hint,
}: {
  label: ReactNode;
  value: ReactNode;
  tone?: "default" | "cyan" | "violet" | "good" | "warn" | "bad";
  hint?: ReactNode;
}) {
  const toneColor: Record<string, string> = {
    default: "text-white",
    cyan: "text-[var(--sl-cyan)]",
    violet: "text-[var(--sl-violet)]",
    good: "text-[var(--sl-emerald)]",
    warn: "text-[var(--sl-amber)]",
    bad: "text-[var(--sl-rose)]",
  };
  return (
    <div className="rounded-xl border border-[var(--sl-border)] bg-[rgba(9,14,28,0.5)] px-3.5 py-3">
      <div className="text-[0.66rem] uppercase tracking-[0.12em] text-[var(--sl-text-faint)]">
        {label}
      </div>
      <div className={`mt-1 text-xl font-semibold ${toneColor[tone]}`}>{value}</div>
      {hint && <div className="mt-0.5 text-[0.72rem] text-[var(--sl-text-dim)]">{hint}</div>}
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * Loading / error / empty
 * ------------------------------------------------------------------------- */

export function SkeletonLine({ className = "" }: { className?: string }) {
  return <div className={`sl-skeleton h-4 ${className}`} />;
}

export function LoadingPanel({ label = "Forming generation field\u2026" }: { label?: string }) {
  return (
    <div className="sl-panel p-6">
      <div className="mb-4 flex items-center gap-2 text-sm text-[var(--sl-text-dim)]">
        <span className="sl-pill__dot text-[var(--sl-cyan)]" /> {label}
      </div>
      <div className="space-y-3">
        <SkeletonLine className="w-3/4" />
        <SkeletonLine className="w-1/2" />
        <SkeletonLine className="w-5/6" />
        <SkeletonLine className="w-2/3" />
      </div>
    </div>
  );
}

export function EmptyState({ title, message }: { title: string; message?: ReactNode }) {
  return (
    <div className="sl-panel flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <div className="text-base font-semibold text-white">{title}</div>
      {message && <div className="max-w-md text-sm text-[var(--sl-text-dim)]">{message}</div>}
    </div>
  );
}

export function ConnectionCard({
  error,
  onRetry,
}: {
  error: SourceLabApiError;
  onRetry?: () => void;
}) {
  const isConnection = error.isConnectionError;
  return (
    <div className="sl-panel sl-panel--glow-violet mx-auto max-w-2xl p-7">
      <div className="flex items-center gap-2">
        <span className="sl-pill sl-pill--blocked">
          <span className="sl-pill__dot" /> {isConnection ? "API OFFLINE" : `ERROR ${error.status}`}
        </span>
      </div>
      <h2 className="mt-4 text-lg font-semibold text-white">
        {isConnection ? "Cannot reach the SourceLab API" : "The SourceLab API returned an error"}
      </h2>
      <p className="mt-2 text-sm text-[var(--sl-text-dim)]">{error.message}</p>
      {error.detail && (
        <p className="mt-1 text-xs text-[var(--sl-text-faint)]">{error.detail}</p>
      )}

      {isConnection && (
        <div className="mt-4 rounded-xl border border-[var(--sl-border)] bg-[rgba(4,7,16,0.7)] p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--sl-text-dim)]">
            Start the backend
          </p>
          <pre className="sl-code mt-2 text-xs">
{`cd sourcelab_ai_production
source .venv/bin/activate
sourcelab api --serve`}
          </pre>
          <p className="mt-2 text-xs text-[var(--sl-text-faint)]">
            Expecting it at <code className="text-[var(--sl-cyan)]">{API_BASE_URL}</code> (set{" "}
            <code>NEXT_PUBLIC_SOURCELAB_API_URL</code> to change).
          </p>
        </div>
      )}

      {onRetry && (
        <button type="button" className="sl-btn sl-btn--primary mt-5" onClick={onRetry}>
          Retry connection
        </button>
      )}
    </div>
  );
}
