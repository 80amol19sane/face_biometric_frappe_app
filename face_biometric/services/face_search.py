import frappe

from face_biometric.core.embedding import Embedding
from face_biometric.core.matcher import MATCHED, NO_MATCH, FaceMatcher, MatchResult


class FaceSearch:
	"""Who, out of every active employee, does this face belong to? Same rule online and at offline sync."""

	def __init__(self, settings):
		self.matcher = FaceMatcher(settings.match_threshold, settings.identify_margin)

	def find(self, embedding: Embedding) -> MatchResult:
		scored = []
		for name in frappe.get_all("Face Template", {"status": "Active"}, pluck="name"):
			template = frappe.get_doc("Face Template", name)
			enrolled = template.load()
			if enrolled.dimensions == embedding.dimensions:
				scored.append((template.employee, enrolled.similarity(embedding)))
		result = self.matcher.decide(scored)
		if result.status == MATCHED and not self._is_active(result.employee):
			return MatchResult(NO_MATCH, similarity=result.similarity)
		return result

	@staticmethod
	def _is_active(employee: str) -> bool:
		return bool(frappe.db.exists("Employee", {"name": employee, "status": "Active"}))
