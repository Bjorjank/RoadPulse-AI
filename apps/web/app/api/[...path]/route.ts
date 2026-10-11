import { NextRequest } from "next/server";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
async function proxy(request: NextRequest, context: {params: Promise<{path: string[]}>}) {
  const {path} = await context.params;
  const headers = new Headers();
  for (const key of ["content-type", "range", "origin"]) {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  }
  const init: RequestInit & {duplex?: string} = {method: request.method, headers, cache: "no-store", signal: request.signal};
  if (request.method !== "GET" && request.method !== "HEAD") {init.body = request.body; init.duplex = "half";}
  try {
    const response = await fetch(`http://127.0.0.1:8000/api/${path.map(encodeURIComponent).join("/")}`, init);
    return new Response(response.body, {status: response.status, headers: response.headers});
  } catch {
    return Response.json({detail: "Local API unavailable. Start the application with scripts/start.py."}, {status: 502});
  }
}
export {proxy as GET, proxy as POST, proxy as HEAD};
