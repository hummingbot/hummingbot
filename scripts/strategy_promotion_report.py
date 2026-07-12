#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hummingbot.strategy_v2.routers.adapters import default_adapter_registry  # noqa: E402
from hummingbot.strategy_v2.routers.promotion import PromotionEvidence, assess_registry  # noqa: E402


def build_report(evidence_path: Path) -> dict:
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence = {
        name: PromotionEvidence.model_validate(values)
        for name, values in payload.get("strategies", {}).items()
    }
    adapters = default_adapter_registry()
    assessments = assess_registry(adapters, evidence)
    return {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "default_live_state": "disabled",
        "strategies": [
            {
                **assessment.model_dump(mode="json"),
                "target": adapters[name].spec.target,
                "execution_mode": adapters[name].spec.execution_mode.value,
                "intended_regimes": adapters[name].spec.intended_regimes,
                "minimum_paper_hours": adapters[name].spec.minimum_paper_hours,
                "required_features": adapters[name].spec.required_features,
                "risk_controls": adapters[name].spec.risk_controls,
            }
            for name, assessment in assessments.items()
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Generate fail-closed strategy promotion state.")
    parser.add_argument(
        "--evidence",
        default=str(ROOT / "reports" / "strategy_promotion_evidence.json"),
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "reports" / "strategy_promotion_state.json"),
    )
    args = parser.parse_args()
    report = build_report(Path(args.evidence).expanduser().resolve())
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(report['strategies'])} promotion assessments to {output}")


if __name__ == "__main__":
    main()
