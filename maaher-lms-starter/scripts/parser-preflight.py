"""Parser limits and optional host calibration; prints no documents or secrets."""
import argparse,json,statistics,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/api'))
from app.markdown_service import parser,maintenance_parser
from app.markdown_budget import CPU_SECONDS

args=argparse.ArgumentParser()
args.add_argument('--calibrate',action='store_true',help='Measure uncached valid30k CPU margin; does not change resource caps')
options=args.parse_args()
try:
    for name,pool in [('interactive',parser),('maintenance',maintenance_parser)]:
        for worker in pool.workers:
            worker.validate('Parser capability check','preflight')
            print(json.dumps({'lane':name,**worker.limits,'status':'PASS' if worker.limits.get('memory_active') else 'WARN_MEMORY_UNAVAILABLE'}))
            if options.calibrate:
                values=[]
                for n in range(5):
                    worker.validate('*a* '*7500,f'preflight-dense:{n}')
                    values.append(worker.usage['cpu_ms'])
                margin=CPU_SECONDS*1000/max(values)
                print(json.dumps({'lane':name,'valid_30k_samples_cpu_ms':values,'median_cpu_ms':statistics.median(values),
                    'budget_ms':int(CPU_SECONDS*1000),'margin_to_slowest_sample':round(margin,2),'status':'PASS_MARGIN' if margin>=2 else 'WARN_LOW_MARGIN'}))
finally:parser.close();maintenance_parser.close()
