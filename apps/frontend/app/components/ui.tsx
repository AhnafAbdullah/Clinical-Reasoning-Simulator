"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/lib/auth";

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`animate-pulse rounded-md bg-neutral-200/70 ${className}`} />;
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="p-10 text-sm text-neutral-500">
      {label}
    </div>
  );
}

export function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="flex justify-between text-xs text-neutral-500">
        <span className="capitalize">{label.replace(/_/g, " ")}</span>
        <span>{value}</span>
      </div>
      <div className="mt-0.5 h-2 rounded-full bg-neutral-100">
        <div
          className="h-2 rounded-full bg-neutral-900"
          style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
        />
      </div>
    </div>
  );
}

export function NavBar() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const link = (href: string, text: string) => (
    <Link
      href={href}
      className={`rounded px-2 py-1 text-sm ${pathname === href ? "font-medium text-neutral-900" : "text-neutral-500 hover:text-neutral-900"}`}
    >
      {text}
    </Link>
  );
  return (
    <nav className="flex items-center justify-between border-b border-neutral-200 px-6 py-3">
      <div className="flex items-center gap-1">
        <Link href="/" className="mr-2 font-semibold">
          CRS
        </Link>
        {link("/", "Dashboard")}
        {link("/analytics", "Analytics")}
      </div>
      {user && (
        <div className="flex items-center gap-3">
          <span className="text-xs text-neutral-500">{user.email}</span>
          <button onClick={logout} className="text-sm text-neutral-600 underline">
            Sign out
          </button>
        </div>
      )}
    </nav>
  );
}
