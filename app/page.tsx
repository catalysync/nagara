import { getSite, type Product } from "@/lib/content";

// Render at request time so edits saved in the Keystatic admin (local storage,
// no rebuild pipeline) appear on the live site immediately.
export const dynamic = "force-dynamic";

// Clean inline placeholder for Atlas (no live screenshot was captured).
// Renders a small ledger that matches the studio's paper/teal palette.
function AtlasPlaceholder() {
  return (
    <div className="shot shot--placeholder" aria-label="Atlas ledger preview">
      <svg
        viewBox="0 0 400 250"
        width="100%"
        height="100%"
        preserveAspectRatio="xMidYMid slice"
        role="img"
        xmlns="http://www.w3.org/2000/svg"
      >
        <rect width="400" height="250" fill="oklch(0.997 0.003 85)" />
        <rect x="0" y="0" width="400" height="34" fill="oklch(0.985 0.006 85)" />
        <line x1="0" y1="34" x2="400" y2="34" stroke="oklch(0.93 0.006 80)" />
        <circle cx="18" cy="17" r="4" fill="oklch(0.885 0.008 80)" />
        <circle cx="32" cy="17" r="4" fill="oklch(0.885 0.008 80)" />
        <circle cx="46" cy="17" r="4" fill="oklch(0.885 0.008 80)" />
        <text x="382" y="21" textAnchor="end" fontFamily="JetBrains Mono, monospace" fontSize="9" letterSpacing="1.2" fill="oklch(0.60 0.010 65)">LEDGER · MAY</text>

        <text x="22" y="66" fontFamily="Bricolage Grotesque, sans-serif" fontSize="17" fontWeight="600" fill="oklch(0.245 0.012 65)">General Ledger</text>
        <text x="378" y="62" textAnchor="end" fontFamily="Bricolage Grotesque, sans-serif" fontSize="18" fontWeight="600" fill="oklch(0.245 0.012 65)">12,438.00</text>
        <text x="378" y="74" textAnchor="end" fontFamily="JetBrains Mono, monospace" fontSize="7.5" letterSpacing="1" fill="oklch(0.60 0.010 65)">BALANCE · NOK</text>

        <line x1="22" y1="92" x2="378" y2="92" stroke="oklch(0.885 0.008 80)" />
        <g fontFamily="Hanken Grotesk, sans-serif" fontSize="11" fill="oklch(0.46 0.012 65)">
          <text x="22" y="116">Invoice — Harbor Co.</text>
          <text x="378" y="116" textAnchor="end" fontFamily="JetBrains Mono, monospace" fontSize="10" fill="oklch(0.44 0.088 195)">+ 4,200.00</text>
          <line x1="22" y1="128" x2="378" y2="128" stroke="oklch(0.93 0.006 80)" />
          <text x="22" y="148">Hosting — Hangar</text>
          <text x="378" y="148" textAnchor="end" fontFamily="JetBrains Mono, monospace" fontSize="10">&#8722; 86.00</text>
          <line x1="22" y1="160" x2="378" y2="160" stroke="oklch(0.93 0.006 80)" />
          <text x="22" y="180">Invoice — Linden LLC</text>
          <text x="378" y="180" textAnchor="end" fontFamily="JetBrains Mono, monospace" fontSize="10" fill="oklch(0.44 0.088 195)">+ 1,950.00</text>
          <line x1="22" y1="192" x2="378" y2="192" stroke="oklch(0.93 0.006 80)" />
          <text x="22" y="212">Invoice — Meridian AS</text>
          <text x="378" y="212" textAnchor="end" fontFamily="JetBrains Mono, monospace" fontSize="10" fill="oklch(0.44 0.088 195)">+ 3,100.00</text>
        </g>
        <line x1="22" y1="226" x2="378" y2="226" stroke="oklch(0.885 0.008 80)" />
        <text x="22" y="244" fontFamily="Hanken Grotesk, sans-serif" fontSize="11" fontWeight="700" fill="oklch(0.245 0.012 65)">Balance</text>
        <text x="378" y="244" textAnchor="end" fontFamily="JetBrains Mono, monospace" fontSize="11" fontWeight="700" fill="oklch(0.245 0.012 65)">12,438.00</text>
      </svg>
    </div>
  );
}

function ProductCard({ p }: { p: Product }) {
  return (
    <article className="product reveal in">
      <div className="product__body">
        <span className="product__index">{p.index}</span>
        <h3 className="product__name">{p.name}</h3>
        <p className="product__pov">{p.pov}</p>
        <p className="product__desc">{p.desc}</p>
        <a className="product__link" href={p.href}>
          <span className="u">{p.linkLabel}</span>
          <span className="arrow">&#8599;</span>
        </a>
      </div>
      <div className="product__preview">
        <div className="screen">
          <div className="screen__bar">
            <i></i>
            <i></i>
            <i></i>
            <span className="ttl">{p.name}</span>
          </div>
          <div className="screen__body">
            {p.shot ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img className="shot" src={p.shot} alt={`${p.name} product preview`} />
            ) : (
              <AtlasPlaceholder />
            )}
          </div>
        </div>
      </div>
    </article>
  );
}

export default async function Home() {
  const s = await getSite();
  return (
    <>
      <header className="nav" id="nav">
        <div className="wrap nav__inner">
          <a className="wordmark" href="#top" aria-label="nagara, home">
            {s.logo ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img className="wordmark__logo" src={s.logo} alt="" aria-hidden="true" />
            ) : (
              <span className="dot"></span>
            )}
            nagara<small>suite</small>
          </a>
          <a className="nav__link" href="#contact">
            <span className="label-full">work with us</span>
            <span className="arrow">&#8594;</span>
          </a>
        </div>
      </header>

      <main id="top">
        <section className="hero">
          <div className="wrap">
            <span className="eyebrow hero__eyebrow reveal in">{s.eyebrow}</span>
            <h1 className="reveal in">
              {s.heroLead} <em>{s.heroEmphasis}</em> {s.heroTrail}
            </h1>
            <p className="hero__sub reveal in">{s.heroSub}</p>
            <a className="hero__cta reveal in" href="#work">
              {s.heroCta || "See the suite"}
              <span className="arrow">&#8595;</span>
            </a>
            {s.heroImage ? (
              <div className="hero__media reveal in">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={s.heroImage} alt="" />
              </div>
            ) : null}
          </div>
        </section>

        <section className="section" id="work">
          <div className="wrap">
            <div className="section__head reveal in">
              <h2>{s.suiteHeading}</h2>
              <p>{s.suiteSub}</p>
            </div>
            <div className="products">
              {s.products.map((p) => (
                <ProductCard key={p.name} p={p} />
              ))}
            </div>
          </div>
        </section>

        <section className="section work" id="how">
          <div className="wrap">
            <div className="section__head reveal in">
              <h2>{s.workHeading}</h2>
              <p>{s.workSub}</p>
            </div>
            <div className="work__grid">
              <div className="reveal in">
                <p className="work__lead">
                  {s.workLeadA} <em>{s.workLeadEm}</em> {s.workLeadB}
                </p>
                <ul className="tenets">
                  {s.tenets.map((t) => (
                    <li key={t.k}>
                      <span className="k">{t.k}</span>
                      <span>{t.t}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="numbers reveal in">
                <div className="n">
                  <b>{s.statA}</b>
                  <span>{s.statALabel}</span>
                </div>
                <div className="n">
                  <b>{s.statB}</b>
                  <span>{s.statBLabel}</span>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="footer" id="contact">
        <div className="wrap">
          <span
            className="eyebrow reveal in"
            style={{ display: "block", marginBottom: "1.4rem" }}
          >
            {s.footerEyebrow}
          </span>
          <h2 className="reveal in">{s.footerHeading}</h2>
          <a className="footer__cta reveal in" href={`mailto:${s.contactEmail}`}>
            {s.contactEmail}
            <span className="arrow">&#8594;</span>
          </a>
          <div className="footer__meta">
            <span>&copy; 2015&ndash;2026 nagara</span>
            <div className="footer__links">
              {s.products.map((p) => (
                <a key={p.name} href={p.href}>
                  {p.name}
                </a>
              ))}
            </div>
          </div>
        </div>
      </footer>
    </>
  );
}
