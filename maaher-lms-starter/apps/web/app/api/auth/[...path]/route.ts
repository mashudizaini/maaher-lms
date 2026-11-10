import { NextRequest } from 'next/server';
import { timingSafeEqual } from 'node:crypto';
import { isIP } from 'node:net';

export const dynamic = 'force-dynamic';
const readable = new Set(['me', 'memberships', 'audit', 'security-events', 'tenant-members',
  'oidc/config', 'oidc/callback', 'oidc/session']);
const writable = new Set(['login', 'logout', 'tenant-selection', 'invitations',
  'invitations/accept', 'password-reset/request', 'password-reset/confirm', 'mfa/enroll', 'mfa/verify', 'mfa/request', 'oidc/login']);

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const path = (await context.params).path.join('/');
  const allowed = request.method === 'GET' ? readable.has(path) : writable.has(path)
    || /^memberships\/[0-9a-f-]{36}\/(revoke|role)$/.test(path);
  if (!allowed) return Response.json({ detail: 'Halaman tidak tersedia' }, { status: 404 });
  const origin = process.env.APP_ORIGIN;
  const base = process.env.API_BASE_URL;
  if (!origin || !base) return Response.json({ detail: 'Layanan belum dikonfigurasi' }, { status: 503 });
  if (request.method === 'POST' && request.headers.get('origin') !== origin) {
    return Response.json({ detail: 'Asal permintaan tidak diizinkan' }, { status: 403 });
  }
  const headers = new Headers();
  const bridgeKey = process.env.BFF_API_SECRET;
  const edgeKey = process.env.EDGE_SHARED_SECRET;
  const presented = request.headers.get('x-maaher-edge-key') ?? '';
  const trustedEdge = edgeKey && Buffer.byteLength(edgeKey) === Buffer.byteLength(presented)
    && timingSafeEqual(Buffer.from(edgeKey), Buffer.from(presented));
  if (process.env.APP_ENV !== 'local' && process.env.APP_ENV !== 'test' && (!bridgeKey || !trustedEdge)) {
    return Response.json({ detail: 'Jalur ingress tepercaya belum dikonfigurasi' }, { status: 503 });
  }
  if (bridgeKey && trustedEdge) {
    const ip = request.headers.get('cf-connecting-ip') ?? '';
    if (!isIP(ip)) return Response.json({ detail: 'Identitas jaringan tidak valid' }, { status: 403 });
    headers.set('x-maaher-bff-key', bridgeKey);
    headers.set('x-maaher-client-ip', ip);
  }
  headers.set('accept', 'application/json');
  const cookies = ['maaher_session', 'maaher_oidc_flow'].flatMap(name => {
    const value = request.cookies.get(name)?.value;
    return value ? [`${name}=${value}`] : [];
  });
  if (cookies.length) headers.set('cookie', cookies.join('; '));
  const tenant = request.headers.get('x-tenant-id');
  if (tenant) headers.set('x-tenant-id', tenant); // API validates membership on every request.
  if (request.method === 'POST') {
    headers.set('origin', origin);
    headers.set('content-type', 'application/json');
  }
  let body: Uint8Array | undefined;
  if (request.method === 'POST' && request.body) {
    const reader = request.body.getReader();
    const chunks: Uint8Array[] = [];
    let size = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.length;
      if (size > 16384) {
        await reader.cancel();
        return Response.json({ detail: 'Permintaan terlalu besar' }, { status: 413 });
      }
      chunks.push(value);
    }
    body = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.length; }
  }
  try {
    const upstream = new URL(base);
    if (!['http:', 'https:'].includes(upstream.protocol) || upstream.username || upstream.password
        || upstream.pathname !== '/' || upstream.search || upstream.hash) throw new Error('Invalid API origin');
    upstream.pathname = `/auth/${path}`;
    if (path === 'oidc/callback') {
      const keys = new Set(['state', 'code', 'error', 'error_description', 'iss']);
      if (request.nextUrl.search.length > 8192 || [...request.nextUrl.searchParams.keys()].some(key =>
        !keys.has(key) || request.nextUrl.searchParams.getAll(key).length !== 1)) {
        return Response.json({ detail: 'Callback tidak valid' }, { status: 400 });
      }
      for (const [key, value] of request.nextUrl.searchParams) upstream.searchParams.set(key, value);
    }
    if (path === 'tenant-members') {
      const after = request.nextUrl.searchParams.get('after');
      if (after && !/^[0-9a-f-]{36}$/.test(after)) return Response.json({ detail: 'Cursor tidak valid' }, { status: 400 });
      if (after) upstream.searchParams.set('after', after);
    }
    const response = await fetch(upstream, { method: request.method, headers,
      body: body as BodyInit | undefined, cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(15000) });
    const outgoing = new Headers({ 'content-type': 'application/json', 'cache-control': 'no-store',
      'referrer-policy': 'no-referrer', 'x-content-type-options': 'nosniff' });
    for (const cookie of response.headers.getSetCookie()) outgoing.append('set-cookie', cookie);
    const retry = response.headers.get('retry-after');
    if (retry) outgoing.set('retry-after', retry);
    if (path === 'oidc/callback') {
      // Never forward provider codes, tokens, errors, or return URLs to the UI.
      const destination = new URL('/auth', origin);
      destination.searchParams.set('oidc', response.ok ? 'success' : 'failed');
      outgoing.set('location', destination.toString());
      return new Response(null, { status: 303, headers: outgoing });
    }
    return new Response(await response.arrayBuffer(), { status: response.status, headers: outgoing });
  } catch {
    return Response.json({ detail: 'Layanan sementara tidak tersedia' }, { status: 503 });
  }
}

export const GET = proxy;
export const POST = proxy;
