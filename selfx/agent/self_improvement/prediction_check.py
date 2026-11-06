"""Independently rerun the actual LM instead of trusting retained logits/caches."""
from pathlib import Path
import uuid

from .common import now,read,read_rows,sha256,write
from .policy import LoRAPolicy


def verify_model_predictions(root,cache_parent=None,tolerance=2e-5):
    root=Path(root)
    cache_parent=Path(cache_parent or root/"fresh_inference_verification")
    fresh=cache_parent/uuid.uuid4().hex
    fresh.mkdir(parents=True,exist_ok=False)
    actor=LoRAPolicy(root/"candidate",cache_dir=fresh)
    campaigns=[(root/"promotion_stress",{"incumbent":"base","candidate":"candidate"}),
               (root/"heldout_attribution",{"incumbent":"base","candidate":"candidate"})]
    actor.add_adapter("weak",root/"candidate/checkpoint_1")
    campaigns.append((root/"rejection_stress",{"incumbent":"candidate","candidate":"weak"}))
    full=root.parent/"candidate"
    if (root.parent/"promotion_stress/report.json").exists() and (full/"training.json").exists():
        actor.add_adapter("full",full)
        campaigns.append((root.parent/"promotion_stress",{"incumbent":"base","candidate":"full"}))
    results=[]
    for folder,roles in campaigns:
        report=read(folder/"report.json")
        if sha256(folder/"trace.jsonl")!=report["trace_sha256"]:
            raise ValueError("prediction source trace was changed")
        records=read_rows(folder/"trace.jsonl")
        worst=0.;count=0
        for role,adapter in roles.items():
            rows=[r for r in records if r["role"]==role]
            expected_id=report["candidate_sha256"] if role=="candidate" else report["incumbent_sha256"]
            if actor.identities[adapter]!=expected_id:
                raise ValueError("fresh inference loaded the wrong policy")
            print(f"Fresh model verification: {folder.name}/{role}, {len(rows)} decisions",flush=True)
            predictions=actor.predict([r["observation"] for r in rows],adapter)
            for row,pred in zip(rows,predictions):
                error=max(abs(pred["probabilities"][key]-row["probabilities"][key]) for key in pred["probabilities"])
                worst=max(worst,error)
                if pred["action"]!=row["requested_action"] or error>tolerance:
                    raise ValueError(f"model prediction differs from retained evidence: {row['episode_id']}")
                if row.get("adapter_used",adapter!="base")!=pred["adapter_used"]:
                    raise ValueError("retained rollout selection differs from verified adapter manifest")
                if abs(row.get("adapter_fraction",1. if adapter!="base" else 0.)-pred["adapter_fraction"])>1e-12:
                    raise ValueError("retained deployment fraction differs from adapter manifest")
                count+=1
        results.append({"campaign":folder.parent.name+"/"+folder.name,"decisions_checked":count,
            "max_probability_difference":worst,"trace_sha256":report["trace_sha256"]})
    result={"status":"passed","checked_at_utc":now(),"retained_cache_used":False,
        "fresh_cache_directory":fresh.name,"probability_tolerance":tolerance,"campaigns":results,
        "decisions_checked":sum(r["decisions_checked"] for r in results)}
    write(fresh/"prediction_verification.json",result)
    return result
