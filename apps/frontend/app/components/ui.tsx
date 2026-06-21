"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/lib/auth";

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`animate-pulse rounded-lg bg-cream-deep ${className}`} />;
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center gap-3 p-10 text-sm text-ink-soft">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-line border-t-navy" />
      {label}
    </div>
  );
}

export function GoldStrip({ className = "" }: { className?: string }) {
  return <span className={`gold-strip ${className}`} aria-hidden />;
}

export function Brand({ className = "" }: { className?: string }) {
  return (
    <Link href="/" className={`group flex items-center gap-2 ${className}`}>
      <span className="grid h-8 w-8 place-items-center rounded-lg bg-navy font-display text-sm font-bold text-gold-soft">
        Cr
      </span>
      <span className="font-display text-lg font-semibold tracking-tight text-navy">
        Clinical Reasoning
      </span>
    </Link>
  );
}

export function ScoreBar({ label, value }: { label: string; value: number }) {
  const v = Math.max(0, Math.min(100, value));
  return (
    <div>
      <div className="flex justify-between text-xs text-ink-soft">
        <span className="capitalize">{label.replace(/_/g, " ")}</span>
        <span className="font-semibold text-ink">{value}</span>
      </div>
      <div className="mt-1 h-2 rounded-full bg-cream-deep">
        <div
          className="h-2 rounded-full bg-navy transition-[width] duration-500"
          style={{ width: `${v}%` }}
        />
      </div>
    </div>
  );
}

export function NavBar() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const link = (href: string, text: string) => {
    const active = pathname === href;
    return (
      <Link
        href={href}
        className={`relative rounded-md px-2.5 py-1 text-sm transition-colors ${
          active ? "font-semibold text-navy" : "text-ink-soft hover:text-navy"
        }`}
      >
        {text}
        {active && (
          <span className="absolute inset-x-2 -bottom-[7px] h-[2px] rounded-full bg-gold" aria-hidden />
        )}
      </Link>
    );
  };
  return (
    <nav className="sticky top-0 z-20 border-b border-line bg-cream/85 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
        <div className="flex items-center gap-5">
          <Brand />
          <div className="hidden items-center gap-1 sm:flex">
            {link("/", "Dashboard")}
            {link("/daily", "Daily Challenge")}
            {link("/analytics", "Analytics")}
          </div>
        </div>
        {user && (
          <div className="flex items-center gap-3">
            <span className="hidden text-xs text-ink-soft sm:inline">{user.email}</span>
            <button onClick={logout} className="btn-ghost px-3 py-1.5 text-xs">
              Sign out
            </button>
          </div>
        )}
      </div>
      <div className="gold-rule" />
    </nav>
  );
}
