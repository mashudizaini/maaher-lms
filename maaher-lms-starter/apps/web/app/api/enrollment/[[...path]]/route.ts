import { NextRequest } from 'next/server';
import { timingSafeEqual } from 'node:crypto';
import { isIP } from 'node:net';

export const dynamic = 'force-dynamic';
const uuid = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}';
const read = new RegExp(`^(?:cohorts|enrollments|learning/courses(?:/${uuid}(?:/modules/${uuid}/lessons/${uuid})?)?)$`);
const write = new RegExp(`^(?:learning/courses/${uuid}/modules/${uuid}/lessons/${uuid}/(?:complete|uncomplete)|cohorts(?:/${uuid}(?:/(?:archive|restore))?)?|enrollments(?:/${uuid}/(?:move|revoke|reactivate))?)$`);

async function proxy(request: NextRequest, context: { params: Promise<{ path?: string[] }> }) {
  const path = (await context.params).path?.join('/') ?? '';
  if (!(request.method === 'GET' ? read : write).test(path)) return Response.json({ detail: 'Halaman tidak tersedia' }, { status: 404 });
  const origin = process.env.APP_ORIGIN;
  const base = process.env.API_BASE_URL;
  if (!origin || !base) return Response.json({ detail: 'Layanan belum dikonfigurasi' }, { status: 503 });
  if (request.method === 'POST' && request.headers.get('origin') !== origin) return Response.json({ detail: 'Asal permintaan tidak diizinkan' }, { status: 403 });
  const headers = new Headers({ accept: 'application/json' });
  const bridge = process.env.BFF_API_SECRET;
  const edge = process.env.EDGE_SHARED_SECRET;
  const presented = request.headers.get('x-maaher-edge-key') ?? '';
  const trusted = edge && Buffer.byteLength(edge) === Buffer.byteLength(presented) && timingSafeEqual(Buffer.from(edge), Buffer.from(presented));
  if (!['local', 'test'].includes(process.env.APP_ENV ?? '') && (!bridge || !trusted)) return Response.json({ detail: 'Jalur ingress tepercaya belum dikonfigurasi' }, { status: 503 });
  if (bridge && trusted) {
    const ip = request.headers.get('cf-connecting-ip') ?? '';
    if (!isIP(ip)) return Response.json({ detail: 'Identitas jaringan tidak valid' }, { status: 403 });
    headers.set('x-maaher-bff-key', bridge); headers.set('x-maaher-client-ip', ip);
  }
  const session = request.cookies.get('maaher_session')?.value;
  if (session) headers.set('cookie', `maaher_session=${session}`);
  const tenant = request.headers.get('x-tenant-id');
  if (tenant) headers.set('x-tenant-id', tenant);
  let body: Uint8Array | undefined;
  if (request.method === 'POST') {
    headers.set('origin', origin); headers.set('content-type', 'application/json');
    if (request.body) {
      const reader = request.body.getReader(); const chunks: Uint8Array[] = []; let size = 0;
      while (true) {
        const { done, value } = await reader.read(); if (done) break;
        size += value.length;
        if (size > 262144) { await reader.cancel(); return Response.json({ detail: 'Permintaan terlalu besar' }, { status: 413 }); }
        chunks.push(value);
      }
      body = new Uint8Array(size); let offset = 0;
      for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.length; }
    }
  }
  try {
    const upstream = new URL(base);
    if (!['http:', 'https:'].includes(upstream.protocol) || upstream.username || upstream.password || upstream.pathname !== '/' || upstream.search || upstream.hash) throw new Error('Invalid API origin');
    upstream.pathname = '/' + path;
    const allowed = path === 'cohorts' ? ['course_id','after','archived'] : path === 'enrollments' ? ['course_id','cohort_id','status','after'] : path === 'learning/courses' ? ['after'] : [];
    for (const key of request.nextUrl.searchParams.keys()) {
      const value = request.nextUrl.searchParams.get(key)!;
      if (request.method !== 'GET' || !allowed.includes(key) || request.nextUrl.searchParams.getAll(key).length !== 1
          || (['course_id','cohort_id','after'].includes(key) && !new RegExp(`^${uuid}$`).test(value))
          || (key === 'archived' && !['true','false'].includes(value))
          || (key === 'status' && !['active','revoked'].includes(value))) return Response.json({ detail: 'Parameter tidak valid' }, { status: 400 });
      upstream.searchParams.set(key, value);
    }
    const result = await fetch(upstream, { method: request.method, headers, body: body as BodyInit | undefined,
      cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(15000) });
    const outgoing = new Headers({
      'content-type': 'application/json', 'cache-control': 'no-store', 'referrer-policy': 'no-referrer', 'x-content-type-options': 'nosniff',
    });
    const retry = result.headers.get('retry-after'); if (retry) outgoing.set('retry-after', retry);
    return new Response(await result.arrayBuffer(), { status: result.status, headers: outgoing });
  } catch { return Response.json({ detail: 'Layanan sementara tidak tersedia' }, { status: 503 }); }
}

export const GET = proxy;
export const POST = proxy;
