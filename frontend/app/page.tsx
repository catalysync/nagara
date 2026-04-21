export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-start justify-center gap-4 p-8">
      <h1 className="text-4xl font-semibold tracking-tight">nagara</h1>
      <p className="text-muted-foreground text-lg">
        Open-source data platform. The UI will land here.
      </p>
      <a href="/api/health/live" className="text-primary text-sm underline">
        backend liveness →
      </a>
    </main>
  );
}
