"""Print the deterministic robustness + review-planning reference artifact."""
import json

from quantrade.capabilities.strategy_robustness_evaluation import (
    robustness_reference_experiment,
)


if __name__ == "__main__":
    print(
        json.dumps(
            robustness_reference_experiment(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
