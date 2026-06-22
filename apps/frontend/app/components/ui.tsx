"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/lib/auth";
import { useSettings } from "@/lib/settings";

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
            <SettingsMenu />
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

function Toggle({ on, onClick, label }: { on: boolean; onClick: () => void; label: string }) {
  return (
    <button
      onClick={onClick}
      role="switch"
      aria-checked={on}
      className="flex w-full items-center justify-between gap-4 rounded-lg px-2 py-1.5 text-sm text-ink hover:bg-cream-deep"
    >
      <span>{label}</span>
      <span className={`relative h-5 w-9 rounded-full transition-colors ${on ? "bg-navy" : "bg-line"}`}>
        <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-cream-card transition-all ${on ? "left-[18px]" : "left-0.5"}`} />
      </span>
    </button>
  );
}

export function SettingsMenu() {
  const { motion, sound, toggleMotion, toggleSound } = useSettings();
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label="Settings"
        aria-expanded={open}
        className="btn-ghost px-2.5 py-1.5 text-sm"
        title="Settings"
      >
        ⚙
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute right-0 z-40 mt-2 w-60 rounded-xl2 border border-line bg-cream-card p-2 shadow-lift">
            <div className="flex items-center gap-2 px-2 pb-1">
              <span className="gold-strip w-6" />
              <span className="text-xs font-semibold uppercase tracking-wide text-ink-soft">Experience</span>
            </div>
            <Toggle on={motion} onClick={toggleMotion} label="Motion &amp; animation" />
            <Toggle on={sound} onClick={toggleSound} label="Clinic ambience" />
            <p className="px-2 pt-1 text-[11px] text-ink-soft">Applies in the consultation room.</p>
          </div>
        </>
      )}
    </div>
  );
}
