import { NextRequest } from 'next/server';
import { timingSafeEqual } from 'node:crypto';
import { isIP } from 'node:net';

export const dynamic = 'force-dynamic';
const uuid = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}';
export async function assignmentProxy(root: 'assignments' | 'work' | 'assignment-submissions', request: NextRequest, context: { params: Promise<{ path?: string[] }> }) {
  const path = (await context.params).path?.join('/') ?? '';
  const read = new RegExp(root === 'assignments' ? `^(?:${uuid}(?:/versions)?)?$` : root === 'work' ? `^(?:assignments(?:/${uuid})?|submissions(?:/${uuid})?)$` : `^(?:${uuid})?$`);
  const write = new RegExp(root === 'assignments' ? `^(?:${uuid}(?:/(?:publish|unpublish|archive|restore))?)?$` : root === 'work' ? `^assignments/${uuid}/(?:draft|submit)$` : '^$a');
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
    upstream.pathname = '/' + root + (path ? '/' + path : '');
    const list = root === 'work' ? ['assignments','submissions'].includes(path) : path === '';
    for (const key of request.nextUrl.searchParams.keys()) {
      const value = request.nextUrl.searchParams.get(key)!;
      const versionPage = root === 'assignments' && path.endsWith('/versions') && key === 'after' && /^[0-9]{1,3}$/.test(value);
      const keys = root === 'assignments' || path === 'assignments' ? ['course_id','lesson_id','after'] : ['course_id','assignment_id','after'];
      if (request.method !== 'GET' || request.nextUrl.searchParams.getAll(key).length !== 1 || (!versionPage && (!list || !keys.includes(key) || !new RegExp(`^${uuid}$`).test(value)))) return Response.json({ detail: 'Parameter tidak valid' }, { status: 400 });
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
