from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any


@dataclass(frozen=True)
class CEOImprovementPolicy:
    repeat_threshold: int = 3
    latency_budget_ms: float = 10_000.0
    model_cost_budget_usd_per_decision: float = 0.05
    failure_rate_threshold: float = 0.15


class QuanTradeCEOObserver:
    """Observe operating telemetry and draft evidence-backed HQ proposals.

    The CEO observer cannot mutate Holdings infrastructure. It only emits a
    proposal envelope that a governed LLM Holdings bridge may later submit to HQ.
    """

    def __init__(self, policy: CEOImprovementPolicy | None = None) -> None:
        self.policy = policy or CEOImprovementPolicy()

    @staticmethod
    def _proposal(
        *,
        issue_type: str,
        title: str,
        summary: str,
        evidence: dict[str, Any],
        required_labs: list[str],
        impact: str = "cross_lab",
    ) -> dict[str, Any]:
        return {
            "schema": "quantrade_hq_proposal_v1",
            "source": "QUANTRADE_LLM_CEO",
            "issue_type": issue_type,
            "title": title,
            "summary": summary,
            "impact": impact,
            "required_labs": required_labs,
            "evidence": evidence,
            "auto_apply": False,
            "requires_hq_review": True,
        }

    def review(
        self,
        *,
        decision_episodes: list[dict[str, Any]] | None = None,
        operational_events: list[dict[str, Any]] | None = None,
        capability_gaps: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        decision_episodes = decision_episodes or []
        operational_events = operational_events or []
        capability_gaps = capability_gaps or []
        proposals: list[dict[str, Any]] = []

        if len(decision_episodes) >= self.policy.repeat_threshold:
            latencies = [
                float(e.get("workflow_latency_proxy_ms") or 0.0)
                for e in decision_episodes
            ]
            mean_latency = mean(latencies) if latencies else 0.0
            if mean_latency > self.policy.latency_budget_ms:
                proposals.append(self._proposal(
                    issue_type="DECISION_LATENCY_BOTTLENECK",
                    title="QuanTrade 의사결정 지연 개선 요청",
                    summary=(
                        "반복된 투자 의사결정에서 평균 end-to-end latency가 "
                        "운영 예산을 초과했다. deterministic/D1 경로 확대, 병렬화, "
                        "provider routing 또는 Runtime 실행환경 개선을 검토해 달라."
                    ),
                    evidence={
                        "episode_count": len(decision_episodes),
                        "mean_workflow_latency_ms": mean_latency,
                        "budget_ms": self.policy.latency_budget_ms,
                    },
                    required_labs=["runtime", "quantrade"],
                ))

            costs = [
                float(e.get("model_cost_usd") or 0.0)
                for e in decision_episodes
            ]
            mean_cost = mean(costs) if costs else 0.0
            if mean_cost > self.policy.model_cost_budget_usd_per_decision:
                proposals.append(self._proposal(
                    issue_type="MODEL_COST_BOTTLENECK",
                    title="QuanTrade AI 의사결정 비용 최적화 요청",
                    summary=(
                        "반복된 의사결정의 평균 모델 비용이 목표 예산을 초과했다. "
                        "Market State Compiler, call gate, cheap-first routing, 캐시, "
                        "역할 통합 또는 모델 교체 실험을 요청한다."
                    ),
                    evidence={
                        "episode_count": len(decision_episodes),
                        "mean_model_cost_usd": mean_cost,
                        "budget_usd": self.policy.model_cost_budget_usd_per_decision,
                    },
                    required_labs=["runtime", "llm", "quantrade"],
                ))

        if operational_events:
            failures = [
                e for e in operational_events
                if str(e.get("status") or "").upper() in {"ERROR", "FAILED", "TIMEOUT"}
            ]
            failure_rate = len(failures) / len(operational_events)
            if (
                len(failures) >= self.policy.repeat_threshold
                and failure_rate >= self.policy.failure_rate_threshold
            ):
                proposals.append(self._proposal(
                    issue_type="OPERATING_RELIABILITY_GAP",
                    title="QuanTrade 운영 신뢰성 개선 요청",
                    summary=(
                        "반복된 데이터/도구/모델 실패가 투자 프로세스의 신뢰성을 "
                        "저해한다. 재시도, fallback, observability, data freshness 및 "
                        "failure isolation 인프라 개선을 검토해 달라."
                    ),
                    evidence={
                        "event_count": len(operational_events),
                        "failure_count": len(failures),
                        "failure_rate": failure_rate,
                    },
                    required_labs=["runtime", "quantrade"],
                ))

        grouped: dict[str, list[dict[str, Any]]] = {}
        for gap in capability_gaps:
            key = str(gap.get("capability") or gap.get("type") or "UNKNOWN")
            grouped.setdefault(key, []).append(gap)
        for capability, gaps in grouped.items():
            if len(gaps) < self.policy.repeat_threshold:
                continue
            proposals.append(self._proposal(
                issue_type="REPEATED_CAPABILITY_GAP",
                title=f"QuanTrade capability 확장 요청 · {capability}",
                summary=(
                    "동일 capability 부재가 반복적으로 실제 투자 업무를 막았다. "
                    "일회성 우회가 아니라 Holdings capability로 제공할 가치가 있는지 "
                    "HQ와 Runtime Engineering의 검토를 요청한다."
                ),
                evidence={
                    "capability": capability,
                    "occurrence_count": len(gaps),
                    "samples": gaps[:5],
                },
                required_labs=["runtime", "quantrade"],
            ))

        return proposals
