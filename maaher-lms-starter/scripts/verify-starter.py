from pathlib import Path
import ast, json, sys
root = Path(__file__).resolve().parents[1]
checks = ['AGENTS.md','CLAUDE.md','README.md','docker-compose.yml','docs/PROJECT-SPEC.md','docs/REA-FINDINGS.md','docs/ARCHITECTURE.md','docs/SETUP-DEPLOY.md','docs/AGENT-WORKFLOW.md','apps/api/app/main.py','apps/web/package.json']
missing=[p for p in checks if not (root/p).is_file()]
if missing: sys.exit('Missing: '+', '.join(missing))
ast.parse((root/'apps/api/app/main.py').read_text())
json.loads((root/'apps/web/package.json').read_text())
print('PASS: key files exist, API syntax parses, web package manifest valid')
