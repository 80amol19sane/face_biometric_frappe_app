import frappe
from frappe import _
from frappe.model.document import Document


class FaceBiometricSettings(Document):
	def validate(self):
		if not 0 < self.match_threshold < 1:
			frappe.throw(_("Match Threshold must be between 0 and 1."))
		if not 0 < self.offline_review_floor <= self.match_threshold:
			frappe.throw(_("Offline Review Floor must be above 0 and not higher than the Match Threshold."))
		if not 10 <= self.challenge_ttl_seconds <= 300:
			frappe.throw(_("Challenge Lifetime must be between 10 and 300 seconds."))
		if self.max_failed_attempts < 1 or self.lockout_minutes < 1:
			frappe.throw(_("Lockout limits must be at least 1."))


def get_settings() -> Document:
	return frappe.get_cached_doc("Face Biometric Settings")
