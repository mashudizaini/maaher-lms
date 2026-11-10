"""Bounded ASGI receive/replay; no framework-private request body mutation."""
from fastapi import HTTPException
from psycopg import Error as DatabaseError
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse

from .course_limits import admit_course_write

MAX_BODY = 262144


class CourseIngress:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        mutation = scope['type'] == 'http' and scope['method'] == 'POST' and any(
            path == root or path.startswith(root + '/') for root in ('/courses', '/cohorts', '/enrollments'))
        if not mutation:
            return await self.app(scope, receive, send)
        try:
            allowed = await run_in_threadpool(admit_course_write, Request(scope))
        except HTTPException as error:
            return await self.reject(scope, receive, send, error.status_code, error.detail)
        except DatabaseError:
            return await self.reject(scope, receive, send, 503, 'Layanan penyimpanan sementara tidak tersedia')
        if not allowed:
            return await self.reject(scope, receive, send, 429, 'Terlalu banyak perubahan kursus. Coba lagi sebentar lagi', {'Retry-After':'60'})
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            chunk = message.get('body', b'')
            if len(body) + len(chunk) > MAX_BODY:
                return await self.reject(scope, receive, send, 413, 'Permintaan terlalu besar')
            body.extend(chunk)
            if not message.get('more_body', False):
                break
        pending = True
        async def replay():
            nonlocal pending
            if pending:
                pending = False
                return {'type':'http.request', 'body':bytes(body), 'more_body':False}
            return await receive()
        await self.app(scope, replay, send)

    @staticmethod
    async def reject(scope, receive, send, status, detail, extra=None):
        response = JSONResponse({'detail':detail}, status_code=status, headers={
            'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff', 'Referrer-Policy':'no-referrer', **(extra or {})})
        await response(scope, receive, send)
