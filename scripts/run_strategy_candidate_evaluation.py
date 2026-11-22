"""Print the safe candidate generation → evaluation sandbox artifact."""
import json

from quantrade.capabilities.strategy_candidate_evaluation import (
    candidate_generation_experiment,
)


if __name__ == "__main__":
    print(
        json.dumps(
            candidate_generation_experiment(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
