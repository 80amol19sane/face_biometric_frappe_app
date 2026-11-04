from dataclasses import dataclass

MATCHED = "Matched"
NO_MATCH = "No Match"
AMBIGUOUS = "Ambiguous"


@dataclass(frozen=True)
class MatchResult:
	status: str
	employee: str | None = None
	similarity: float = 0.0
	runner_up: float = 0.0


class FaceMatcher:
	"""Picks who a face belongs to out of everyone enrolled (1 to N).

	A hit needs to clear the threshold and also beat the next-best person by `margin`. Without the
	margin, two similar-looking colleagues could be mixed up and the wrong person would be punched in.
	"""

	def __init__(self, threshold: float, margin: float):
		self.threshold = threshold
		self.margin = margin

	def decide(self, scored: list[tuple[str, float]]) -> MatchResult:
		if not scored:
			return MatchResult(NO_MATCH)
		ranked = sorted(scored, key=lambda item: item[1], reverse=True)
		employee, best = ranked[0]
		runner_up = ranked[1][1] if len(ranked) > 1 else -1.0
		if best < self.threshold:
			return MatchResult(NO_MATCH, similarity=best, runner_up=max(runner_up, 0.0))
		if best - runner_up < self.margin:
			return MatchResult(AMBIGUOUS, similarity=best, runner_up=runner_up)
		return MatchResult(MATCHED, employee, best, max(runner_up, 0.0))
