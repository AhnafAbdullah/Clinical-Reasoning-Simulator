import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <h1 className="text-2xl font-semibold">Clinical Reasoning Simulator</h1>
      <p className="mt-2 text-neutral-600">
        Phase 0 foundation. The clinical session experience is built in later phases.
      </p>
      <Link
        href="/skeleton"
        className="mt-6 inline-block rounded-md border border-neutral-300 px-4 py-2 text-sm hover:bg-neutral-50"
      >
        Streaming skeleton demo &rarr;
      </Link>
    </main>
  );
}
