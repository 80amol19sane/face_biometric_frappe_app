import frappe
from frappe.utils import add_to_date, now_datetime

DOCTYPE = "Face Verification Log"
# Offline outcomes are settled in bulk at sync, not a person failing at the kiosk, so they must not lock anyone out.
NOT_FAILURES = ("Matched", "Locked Out", "Offline Held", "Offline Duplicate", "Offline Approved")


def record(employee: str | None, outcome: str, device: str | None = None, **fields) -> str:
	log = frappe.get_doc(doctype=DOCTYPE, employee=employee, device=device, outcome=outcome, **fields)
	log.insert(ignore_permissions=True)
	# The caller usually raises next, which rolls the request back. Commit so the failure stays on record.
	frappe.db.commit()
	return log.name


def recent_failures(employee: str, window_minutes: int) -> int:
	"""Failed attempts inside the window and since the last success."""
	since = add_to_date(now_datetime(), minutes=-window_minutes)
	last_match = frappe.db.get_value(
		DOCTYPE, {"employee": employee, "outcome": "Matched"}, "creation", order_by="creation desc"
	)
	if last_match and last_match > since:
		since = last_match
	return frappe.db.count(
		DOCTYPE,
		{"employee": employee, "outcome": ["not in", NOT_FAILURES], "creation": [">", since]},
	)


def recent_device_failures(device: str, window_minutes: int) -> int:
	"""Failures on one device inside the window, whoever they were for. Used to pause a kiosk being guessed at."""
	since = add_to_date(now_datetime(), minutes=-window_minutes)
	return frappe.db.count(
		DOCTYPE,
		{
			"device": device,
			"outcome": ["not in", NOT_FAILURES],
			"creation": [">", since],
			# A sync can settle many strangers in one second; that is not someone guessing at the kiosk.
			"recorded_at": ["is", "not set"],
		},
	)
