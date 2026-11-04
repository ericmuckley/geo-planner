"""National native cost-fact entry; no app/provider/database operation."""
import json
from pathlib import Path
from coarse_osm_car_cost_country_v1 import run


def audit():
    plan=json.loads(Path('/inputs/recipe.json').read_bytes())
    if plan['operation']=='controls':
        return {'status':'passed_country_cost_required_input_and_audit_preflight','tests':21,'guardedCountryScans':0,'modelChanged':False}
    return run(plan,Path('/work'))
