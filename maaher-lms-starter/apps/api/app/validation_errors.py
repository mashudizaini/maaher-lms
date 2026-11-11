"""Bounded, UTF8-safe validation responses; never reflect input or context."""
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def safe(value,limit):
    return str(value)[:limit].encode('utf8','replace').decode('utf8')


async def invalid_request(request,error:RequestValidationError):
    details=[]
    for item in error.errors()[:20]:
        details.append({'type':safe(item.get('type','value_error'),80),
            'loc':[part if isinstance(part,int) else safe(part,160) for part in item.get('loc',())[:10]],
            'msg':safe(item.get('msg','Periksa data yang diisi'),300)})
    return JSONResponse({'detail':details},status_code=422)
