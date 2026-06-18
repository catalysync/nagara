// The /admin route is basic-auth gated at the Caddy edge. It's a small landing
// that hands off to the Keystatic CMS, which edits content/site/index.json.
export const metadata = { title: "nagara · admin" };

export default function AdminPage() {
  return (
    <main
      style={{
        minHeight: "100dvh",
        display: "grid",
        placeItems: "center",
        background: "var(--bg, oklch(0.985 0.006 85))",
        color: "var(--ink, oklch(0.245 0.012 65))",
        fontFamily:
          'var(--sans, "Hanken Grotesk", system-ui, sans-serif)',
        padding: "2rem",
      }}
    >
      <div style={{ maxWidth: "30rem", width: "100%" }}>
        <span
          style={{
            fontFamily: 'var(--mono, "JetBrains Mono", monospace)',
            fontSize: "0.72rem",
            letterSpacing: "0.16em",
            textTransform: "uppercase",
            color: "var(--ink-faint, oklch(0.60 0.010 65))",
          }}
        >
          nagara · suite
        </span>
        <h1
          style={{
            fontFamily:
              'var(--serif, "Bricolage Grotesque", sans-serif)',
            fontSize: "2rem",
            fontWeight: 600,
            letterSpacing: "-0.02em",
            margin: "0.6rem 0 0.4rem",
          }}
        >
          Admin
        </h1>
        <p
          style={{
            color: "var(--ink-soft, oklch(0.46 0.012 65))",
            margin: "0 0 1.6rem",
            lineHeight: 1.5,
          }}
        >
          Edit the site content in the Keystatic CMS. Text and image changes
          save straight to the site and go live immediately — no rebuild.
        </p>
        <a
          href="/keystatic"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.55rem",
            fontFamily: 'var(--mono, "JetBrains Mono", monospace)',
            fontSize: "0.82rem",
            color: "var(--accent-ink, oklch(0.44 0.088 195))",
            borderBottom:
              "1.5px solid color-mix(in oklab, var(--accent, oklch(0.50 0.084 195)) 45%, transparent)",
            paddingBottom: "4px",
          }}
        >
          Open the CMS →
        </a>
      </div>
    </main>
  );
}
