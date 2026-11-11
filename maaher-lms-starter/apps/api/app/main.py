from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from psycopg import Error as DatabaseError
from .auth import router
from .auth_lifecycle import router as lifecycle_router
from .mfa import router as mfa_router
from .oidc import router as oidc_router
from .courses import router as courses_router
from .course_ingress import CourseIngress
from .enrollment import router as enrollment_router
from .learning import router as learning_router
from .assignments import router as assignments_router,work as work_router,review as assignment_review_router
from .traffic import ANONYMOUS_PATHS, admit
from .auth_support import limited

app = FastAPI(title="Maaher LMS API", docs_url=None, redoc_url=None)
app.include_router(router)
app.include_router(lifecycle_router)
app.include_router(mfa_router)
app.include_router(oidc_router)
app.include_router(courses_router)
app.include_router(enrollment_router)
app.include_router(learning_router)
app.include_router(assignments_router)
app.include_router(work_router)
app.include_router(assignment_review_router)


@app.middleware("http")
async def private_responses(request, call_next):
    if request.method == 'POST' and request.url.path in ANONYMOUS_PATHS:
        try:
            allowed = await run_in_threadpool(admit, request)
        except HTTPException as error:
            return JSONResponse({'detail': error.detail},status_code=error.status_code,
                                headers={'Cache-Control':'no-store'})
        except DatabaseError:
            return JSONResponse({'detail':'Layanan penyimpanan sementara tidak tersedia'},status_code=503,
                                headers={'Cache-Control':'no-store'})
        if not allowed:
            return limited()
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


app.add_middleware(CourseIngress)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    # Liveness only; not proof that database, auth, RLS or grader are ready.
    return {"status": "ok", "service": "maaher-api"}
