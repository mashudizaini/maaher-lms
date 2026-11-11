"""Local parser capability report; prints no env values, document or secrets."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/api'))
from app.markdown_service import parser,maintenance_parser
for name,pool in [('interactive',parser),('maintenance',maintenance_parser)]:
    for worker in pool.workers:
        worker.validate('Parser capability check','preflight')
        print(json.dumps({'lane':name,**worker.limits,'status':'PASS' if worker.limits.get('memory_active') else 'WARN_MEMORY_UNAVAILABLE'}))
parser.close();maintenance_parser.close()
