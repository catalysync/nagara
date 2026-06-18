import "server-only";
import { createReader } from "@keystatic/core/reader";
import keystaticConfig from "../keystatic.config";

// ─────────────────────────────────────────────────────────────
// Single source of truth for the site's copy + images — sourced from
// Keystatic. The admin at /keystatic edits the `site` singleton, writing
// content/site/index.json and any uploaded images under public/images/….
// This module reads that content back with the Keystatic reader, which
// also resolves image fields to their public URLs (e.g. /images/shots/
// relay.png). Editing any field in the CMS changes what this returns, and
// therefore what the rendered page shows.
//
// SERVER-ONLY: the reader touches the filesystem, so this never enters the
// client bundle. The home page is a server component and awaits getSite().
// ─────────────────────────────────────────────────────────────
const reader = createReader(process.cwd(), keystaticConfig);

export type Product = {
  index: string;
  name: string;
  pov: string;
  desc: string;
  linkLabel: string;
  href: string;
  /** Resolved public URL of the screenshot, or null when none is set. */
  shot: string | null;
};

export type Tenet = { k: string; t: string };

export type SiteContent = {
  logo: string | null;
  ogImage: string | null;
  eyebrow: string;
  heroLead: string;
  heroEmphasis: string;
  heroTrail: string;
  heroSub: string;
  heroCta: string;
  heroImage: string | null;
  suiteHeading: string;
  suiteSub: string;
  products: Product[];
  workHeading: string;
  workSub: string;
  workLeadA: string;
  workLeadEm: string;
  workLeadB: string;
  tenets: Tenet[];
  statA: string;
  statALabel: string;
  statB: string;
  statBLabel: string;
  footerEyebrow: string;
  footerHeading: string;
  contactEmail: string;
};

export async function getSite(): Promise<SiteContent> {
  const s = await reader.singletons.site.read();
  // The singleton always exists (committed content/site/index.json), but the
  // reader's type allows null — guard so the build/types stay honest.
  if (!s) throw new Error("Missing Keystatic singleton: site");

  // Images are served by the dynamic /media route (app/media/[...path]) so
  // freshly uploaded files appear without a container restart. Normalize any
  // legacy "/images/…" value (from before the /media route) to "/media/…".
  const media = (v: string | null | undefined): string | null =>
    v ? v.replace(/^\/images\//, "/media/") : null;

  return {
    logo: media(s.logo),
    ogImage: media(s.ogImage),
    eyebrow: s.eyebrow,
    heroLead: s.heroLead,
    heroEmphasis: s.heroEmphasis,
    heroTrail: s.heroTrail,
    heroSub: s.heroSub,
    heroCta: s.heroCta,
    heroImage: media(s.heroImage),
    suiteHeading: s.suiteHeading,
    suiteSub: s.suiteSub,
    products: s.products.map((p) => ({
      index: p.index,
      name: p.name,
      pov: p.pov,
      desc: p.desc,
      linkLabel: p.linkLabel,
      href: p.href ?? "",
      shot: media(p.shot),
    })),
    workHeading: s.workHeading,
    workSub: s.workSub,
    workLeadA: s.workLeadA,
    workLeadEm: s.workLeadEm,
    workLeadB: s.workLeadB,
    tenets: s.tenets.map((t) => ({ k: t.k, t: t.t })),
    statA: s.statA,
    statALabel: s.statALabel,
    statB: s.statB,
    statBLabel: s.statBLabel,
    footerEyebrow: s.footerEyebrow,
    footerHeading: s.footerHeading,
    contactEmail: s.contactEmail,
  };
}
