import { readFile, stat } from "node:fs/promises";
import path from "node:path";
import { NextResponse } from "next/server";

// ─────────────────────────────────────────────────────────────
// Dynamic media server for CMS-managed images.
//
// Next.js standalone reads the static /public directory ONCE at startup, so
// freshly uploaded images (new filenames written by the Keystatic admin into
// the bind-mounted public/images dir) would 404 until the container restarts.
// This route reads the file straight off disk at request time instead, so a
// brand-new upload is served immediately — no rebuild, no restart.
//
// Keystatic writes uploads under public/images/… and the content references
// them as /media/… (see keystatic.config.ts publicPath + getSite() rewrite),
// which maps here to <cwd>/public/images/<path>.
// ─────────────────────────────────────────────────────────────
export const dynamic = "force-dynamic";

const MIME: Record<string, string> = {
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".webp": "image/webp",
  ".avif": "image/avif",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
};

export async function GET(
  _req: Request,
  ctx: { params: Promise<{ path: string[] }> },
) {
  const { path: parts } = await ctx.params;

  // Resolve safely inside public/images and reject any traversal attempt.
  const root = path.join(process.cwd(), "public", "images");
  const target = path.normalize(path.join(root, ...parts));
  if (target !== root && !target.startsWith(root + path.sep)) {
    return new NextResponse("Not found", { status: 404 });
  }

  try {
    const info = await stat(target);
    if (!info.isFile()) return new NextResponse("Not found", { status: 404 });
    const data = await readFile(target);
    const type = MIME[path.extname(target).toLowerCase()] ?? "application/octet-stream";
    return new NextResponse(data, {
      headers: {
        "Content-Type": type,
        // Short cache: a re-uploaded (replaced) image should surface quickly.
        "Cache-Control": "public, max-age=60, must-revalidate",
      },
    });
  } catch {
    return new NextResponse("Not found", { status: 404 });
  }
}
