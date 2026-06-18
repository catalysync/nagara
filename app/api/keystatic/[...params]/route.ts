import { makeRouteHandler } from "@keystatic/next/route-handler";
import config from "../../../../keystatic.config";

// Forcing this route dynamic keeps the GitHub-storage env validation out of
// build-time page-data collection, so the site builds even when the Keystatic
// env vars are absent (the admin simply can't authenticate until they're set).
export const dynamic = "force-dynamic";

export const { POST, GET } = makeRouteHandler({ config });
