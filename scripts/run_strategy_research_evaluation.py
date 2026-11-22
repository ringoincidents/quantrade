"""Print the deterministic Strategy Research Sandbox reference experiment."""
import json

from quantrade.capabilities.strategy_research_evaluation import (
    canonical_experiment,
)


if __name__ == "__main__":
    print(
        json.dumps(
            canonical_experiment(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
