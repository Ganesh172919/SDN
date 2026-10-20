"""Run with `python -m scripts.probe_providers`. Writes sanitized provider evidence."""
import json
from datetime import datetime, timezone
from pathlib import Path
from agent.providers import RestLLM, discover
from agent.schemas import DecisionOutput


def main():
    output = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "catalogs": discover(), "checks": []}
    for provider in ("gemini", "openrouter"):
        llm = RestLLM(provider)
        try:
            value = llm.with_structured_output(DecisionOutput).invoke([
                {"role": "system", "content": "You control an SDN simulation. Return JSON only."},
                {"role": "user", "content": "Healthy network. Choose no_op and explain briefly."},
            ])
            check = {"provider": provider, "status": "ok", "decision": value.model_dump()}
        except Exception as exc:
            check = {"provider": provider, "status": "error", "error_code": str(exc)}
        check["audit"] = llm.audit
        output["checks"].append(check)
        print(json.dumps(check))
    path = Path(__file__).resolve().parents[1] / "output" / "provider_check.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(output, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
