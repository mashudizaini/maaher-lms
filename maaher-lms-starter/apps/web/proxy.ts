import { NextRequest, NextResponse } from 'next/server';
import { randomBytes } from 'node:crypto';

export function proxy(request: NextRequest) {
  const nonce = randomBytes(24).toString('base64');
  const directives = ["default-src 'self'", `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${process.env.NODE_ENV === 'development' ? " 'unsafe-eval'" : ''}`,
    `style-src 'self' 'nonce-${nonce}'`, "connect-src 'self'", "img-src 'self' data:", "font-src 'self'",
    "object-src 'none'", "base-uri 'none'", "form-action 'self'", "frame-ancestors 'none'"];
  if (process.env.APP_ORIGIN?.startsWith('https://')) directives.push('upgrade-insecure-requests');
  const csp = directives.join('; ');
  const headers = new Headers(request.headers);
  // Always overwrite client-supplied nonces/CSP before rendering.
  headers.set('content-security-policy', csp);
  headers.set('x-nonce', nonce);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set('content-security-policy', csp);
  response.headers.set('cache-control', 'no-store');
  return response;
}

export const config = { matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'] };
