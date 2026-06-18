import type { Metadata } from "next";
import "./globals.css";
import { getSite } from "@/lib/content";

const TITLE = "nagara — a suite of products that scales with you";
const DESCRIPTION =
  "nagara is a suite of five opinionated products that scale with you — support, commerce, deploys, data engineering, and accounting.";

export async function generateMetadata(): Promise<Metadata> {
  const s = await getSite();
  return {
    // Absolute-URL base for OG/Twitter image tags so social shares resolve to
    // the public site instead of localhost. Override via SITE_URL if needed.
    metadataBase: new URL(process.env.SITE_URL ?? "https://nagara.isle.run"),
    title: TITLE,
    description: DESCRIPTION,
    openGraph: {
      title: TITLE,
      description: DESCRIPTION,
      images: s.ogImage ? [{ url: s.ogImage }] : undefined,
    },
  };
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400..800&family=Hanken+Grotesk:ital,wght@0,300..700;1,400..500&family=JetBrains+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
