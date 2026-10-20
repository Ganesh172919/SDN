"""One bounded structured-decision check for every discovered zero-price model."""
import json
from datetime import datetime, timezone
from agent.providers import RestLLM, discover
from agent.schemas import DecisionOutput
import config
import argparse
from pathlib import Path
from eval.run_simulation import local_path
from agent.fast_control import ActionChoice


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',choices=['legacy','compact'],default='legacy')
    parser.add_argument('--out',default=str(config.PROJECT_ROOT/'output/free_model_checks.json'))
    args=parser.parse_args()
    catalog = discover()["openrouter"]
    records = []
    target = local_path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
    for model in catalog["models"]:
        llm = RestLLM("openrouter", model,profile=args.profile)
        try:
            result = llm.with_structured_output(ActionChoice if args.profile=='compact' else DecisionOutput).invoke([
                {"role": "system", "content": "Return a JSON SDN decision."},
                {"role": "user", "content": "Network healthy: choose no_op."},
            ])
            status = "ok" if (result.action=='no_op' if args.profile=='compact' else result.is_well_formed()) else "malformed"
        except Exception:
            status = "unavailable"
        record = {"model": model, "status": status, "audit": llm.audit}
        records.append(record)
        target.write_text(json.dumps({"checked_at_utc": datetime.now(timezone.utc).isoformat(), "catalog_status": catalog["status"], "profile":args.profile,"models": records}, indent=2), encoding="utf-8")
        print(json.dumps({"model": model, "status": status}), flush=True)


if __name__ == "__main__":
    main()
