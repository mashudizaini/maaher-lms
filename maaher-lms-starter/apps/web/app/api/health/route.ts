import { NextResponse } from 'next/server';
export const dynamic = 'force-dynamic';
export async function GET() {
  const target = process.env.API_INTERNAL_URL;
  if (!target) return NextResponse.json({ status: 'unconfigured' }, { status: 503 });
  try {
    const r = await fetch(`${target}/healthz`, { cache: 'no-store', signal: AbortSignal.timeout(3000) });
    if (!r.ok) throw new Error('API not ready');
    return NextResponse.json({ status: 'ok' });
  } catch {
    return NextResponse.json({ status: 'unavailable' }, { status: 503 });
  }
}
