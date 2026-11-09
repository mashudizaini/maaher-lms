from fastapi import FastAPI

app = FastAPI(title="Maaher LMS API", docs_url=None, redoc_url=None)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    # Liveness only; not proof that database, auth, RLS or grader are ready.
    return {"status": "ok", "service": "maaher-api"}
