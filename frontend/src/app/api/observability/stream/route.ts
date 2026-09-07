import type { NextRequest } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export async function GET(request: NextRequest) {
  const apiKey = request.headers.get("X-Aegis-API-Key");
  const headers: HeadersInit = {};
  if (apiKey) {
    headers["X-Aegis-API-Key"] = apiKey;
  }

  const upstream = await fetch(`${API_BASE}/api/observability/stream`, {
    headers,
    cache: "no-store",
    // Abort upstream when the browser disconnects so the broker unsubscribes.
    signal: request.signal,
  });

  if (!upstream.ok || !upstream.body) {
    return new Response(await upstream.text(), { status: upstream.status });
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}