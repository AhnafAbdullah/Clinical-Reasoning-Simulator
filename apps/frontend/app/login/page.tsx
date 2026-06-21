"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Brand, GoldStrip } from "@/app/components/ui";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const STEPS = [
  { n: "01", t: "Meet your patient", d: "A real, reactive patient streams their story — you take the history in your own words." },
  { n: "02", t: "Work it up", d: "Examine, order investigations, and weigh the findings like you would on the ward." },
  { n: "03", t: "Commit & be marked", d: "Lock a differential, diagnosis and plan — then get a rubric-anchored consultant report." },
];

export default function HomePage() {
  const { login, register } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password, name || undefined);
      router.push("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen lg:grid lg:grid-cols-[1.1fr_0.9fr]">
      {/* Hero — navy panel, light text (light on dark) */}
      <section className="relative hidden flex-col justify-between overflow-hidden bg-navy px-12 py-12 text-cream-card lg:flex">
        <div className="pointer-events-none absolute inset-0 opacity-[0.18]" aria-hidden
          style={{ backgroundImage: "radial-gradient(600px 300px at 20% 10%, #c2a14a, transparent 60%), radial-gradient(500px 320px at 90% 90%, #2f6ea5, transparent 60%)" }} />
        <div className="relative">
          <div className="flex items-center gap-2">
            <span className="grid h-9 w-9 place-items-center rounded-lg bg-cream-card font-display text-sm font-bold text-navy">Cr</span>
            <span className="font-display text-xl font-semibold">Clinical Reasoning Simulator</span>
          </div>
        </div>

        <div className="relative max-w-lg animate-fade-up">
          <GoldStrip className="mb-5 w-16" />
          <h1 className="font-display text-4xl font-semibold leading-tight">
            Think like a clinician.<br />Practise like it&apos;s real.
          </h1>
          <p className="mt-4 text-cream-card/80">
            Reproducible, rubric-anchored patient encounters — take a history, investigate, commit
            to a diagnosis, and get consultant-grade feedback. Every time.
          </p>

          <ol className="mt-9 space-y-4">
            {STEPS.map((s) => (
              <li key={s.n} className="flex gap-4">
                <span className="font-display text-lg font-semibold text-gold-soft">{s.n}</span>
                <div>
                  <p className="font-semibold">{s.t}</p>
                  <p className="text-sm text-cream-card/70">{s.d}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>

        <div className="relative flex items-center gap-6 text-sm text-cream-card/70">
          <span><b className="text-gold-soft">12</b> cases</span>
          <span className="h-4 w-px bg-cream-card/20" />
          <span><b className="text-gold-soft">4</b> difficulty tiers</span>
          <span className="h-4 w-px bg-cream-card/20" />
          <span>Rubric-anchored grading</span>
        </div>
      </section>

      {/* Auth — cream panel, dark text (dark on light) */}
      <section className="flex min-h-screen flex-col justify-center px-6 py-12 sm:px-12">
        <div className="mx-auto w-full max-w-sm animate-fade-up">
          <div className="lg:hidden">
            <Brand />
          </div>
          <div className="mt-8 lg:mt-0">
            <GoldStrip className="mb-4" />
            <h2 className="font-display text-2xl font-semibold text-navy">
              {mode === "login" ? "Welcome back" : "Create your account"}
            </h2>
            <p className="mt-1 text-sm text-ink-soft">
              {mode === "login" ? "Sign in to continue your training." : "Start practising in under a minute."}
            </p>
          </div>

          <form onSubmit={submit} className="mt-6 space-y-3">
            {mode === "register" && (
              <input className="input" placeholder="Display name (optional)" value={name}
                onChange={(e) => setName(e.target.value)} />
            )}
            <input className="input" type="email" required placeholder="Email" value={email}
              onChange={(e) => setEmail(e.target.value)} />
            <input className="input" type="password" required minLength={8}
              placeholder="Password (min 8 characters)" value={password}
              onChange={(e) => setPassword(e.target.value)} />
            {error && (
              <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
            )}
            <button type="submit" disabled={busy} className="btn-primary w-full py-2.5">
              {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>

          <button
            onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }}
            className="mt-5 text-sm text-ink-soft transition-colors hover:text-navy"
          >
            {mode === "login" ? (
              <>New here? <span className="font-semibold text-navy underline decoration-gold decoration-2 underline-offset-4">Create an account</span></>
            ) : (
              <>Have an account? <span className="font-semibold text-navy underline decoration-gold decoration-2 underline-offset-4">Sign in</span></>
            )}
          </button>
        </div>
      </section>
    </main>
  );
}
