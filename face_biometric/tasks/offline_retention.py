import frappe
from frappe.utils import add_days, now_datetime

from face_biometric.face_biometric.doctype.face_biometric_settings.face_biometric_settings import get_settings


def close_unreviewed_offline_scans():
	"""Daily. A held scan nobody reviewed in time is closed as rejected, with a note. Nothing is deleted."""
	days = get_settings().held_retention_days
	if not days or days < 1:
		return
	expired = frappe.get_all(
		"Face Verification Log",
		{"outcome": "Offline Held", "creation": ["<", add_days(now_datetime(), -days)]},
		["name", "detail"],
	)
	for row in expired:
		note = f"Closed without review after {days} days."
		frappe.db.set_value(
			"Face Verification Log",
			row.name,
			{"outcome": "Offline Rejected", "detail": f"{row.detail or ''} {note}".strip()},
		)
	if expired:
		frappe.db.commit()
