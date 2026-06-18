import { config, fields, singleton } from "@keystatic/core";

// ─────────────────────────────────────────────────────────────
// Keystatic CMS — Git-based, no database. The admin UI lives at
// /keystatic and edits the site content singleton committed at
// content/site/index.json. Images are written under public/images/…
// and referenced from the same file. The published site renders straight
// from that content (lib/content.ts uses the Keystatic reader), so the
// storage mode never changes what visitors see.
//
// STORAGE MODE: in production the nagara container runs with
// KEYSTATIC_STORAGE_LOCAL=true, so the admin writes content + images
// directly to the filesystem (no GitHub round-trip, no token needed).
// The /keystatic + /admin routes are gated by basic_auth at the Caddy
// edge, so only the holder of those credentials can reach the editor.
//
// If GitHub OAuth env vars are later provided (and KEYSTATIC_STORAGE_LOCAL
// is unset), it transparently switches to `github` storage — edits then
// commit through a GitHub App instead of the local filesystem.
// ─────────────────────────────────────────────────────────────
const hasGithubAuth =
  !!process.env.KEYSTATIC_GITHUB_CLIENT_ID &&
  !!process.env.KEYSTATIC_GITHUB_CLIENT_SECRET &&
  !!process.env.KEYSTATIC_SECRET;

const useLocalStorage =
  process.env.KEYSTATIC_STORAGE_LOCAL === "true" || !hasGithubAuth;

// One product card: copy + link + its screenshot image.
const product = () =>
  fields.object({
    index: fields.text({ label: "Index (01–05)" }),
    name: fields.text({ label: "Name" }),
    pov: fields.text({ label: "Point of view" }),
    desc: fields.text({ label: "Description", multiline: true }),
    linkLabel: fields.text({ label: "Link label" }),
    href: fields.url({ label: "Link URL" }),
    shot: fields.image({
      label: "Screenshot",
      description:
        "Product preview image. Leave empty to render the built-in Atlas ledger placeholder.",
      directory: "public/images/shots",
      publicPath: "/media/shots",
    }),
  });

const tenet = () =>
  fields.object({
    k: fields.text({ label: "Number" }),
    t: fields.text({ label: "Text" }),
  });

export default config({
  storage: useLocalStorage
    ? { kind: "local" }
    : {
        kind: "github",
        repo: { owner: "nagara", name: "nagara-site" },
      },
  ui: {
    brand: { name: "nagara · suite" },
  },
  singletons: {
    site: singleton({
      label: "Site content",
      path: "content/site/index",
      format: { data: "json" },
      schema: {
        // ─── Brand & social ───
        logo: fields.image({
          label: "Brand logo / wordmark mark",
          description:
            "Small mark shown beside the “nagara” wordmark in the nav. Leave empty to use the built-in dot.",
          directory: "public/images/brand",
          publicPath: "/media/brand",
        }),
        ogImage: fields.image({
          label: "Social share image (Open Graph)",
          description:
            "1200×630 image used when the site is shared on social / chat. Leave empty for none.",
          directory: "public/images/brand",
          publicPath: "/media/brand",
        }),

        // ─── Hero ───
        eyebrow: fields.text({ label: "Hero eyebrow" }),
        heroLead: fields.text({ label: "Hero — lead" }),
        heroEmphasis: fields.text({ label: "Hero — emphasis word" }),
        heroTrail: fields.text({ label: "Hero — trail" }),
        heroSub: fields.text({ label: "Hero subhead", multiline: true }),
        heroCta: fields.text({ label: "Hero CTA label" }),
        heroImage: fields.image({
          label: "Hero image (optional)",
          description:
            "Optional image shown beside/under the hero copy. Leave empty for the text-only hero.",
          directory: "public/images/hero",
          publicPath: "/media/hero",
        }),

        // ─── Suite section ───
        suiteHeading: fields.text({ label: "Suite heading" }),
        suiteSub: fields.text({ label: "Suite subhead", multiline: true }),
        products: fields.array(product(), {
          label: "Products",
          itemLabel: (p) => p.fields.name.value || "Product",
        }),

        // ─── How-we-work section ───
        workHeading: fields.text({ label: "How we work — heading" }),
        workSub: fields.text({ label: "How we work — subhead" }),
        workLeadA: fields.text({
          label: "Work lead (before emphasis)",
          multiline: true,
        }),
        workLeadEm: fields.text({ label: "Work lead — emphasis" }),
        workLeadB: fields.text({ label: "Work lead (after emphasis)" }),
        tenets: fields.array(tenet(), {
          label: "Tenets",
          itemLabel: (t) => t.fields.t.value || "Tenet",
        }),
        statA: fields.text({ label: "Stat A value" }),
        statALabel: fields.text({ label: "Stat A label" }),
        statB: fields.text({ label: "Stat B value" }),
        statBLabel: fields.text({ label: "Stat B label" }),

        // ─── Footer ───
        footerEyebrow: fields.text({ label: "Footer eyebrow" }),
        footerHeading: fields.text({ label: "Footer heading" }),
        contactEmail: fields.text({ label: "Contact email" }),
      },
    }),
  },
});
