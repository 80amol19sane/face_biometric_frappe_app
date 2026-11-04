import frappe
from frappe.rate_limiter import rate_limit

from face_biometric.services.kiosk import Kiosk

# Guest endpoints on purpose: a kiosk has no logged-in user. Every action except the challenge is
# signed by the kiosk's registered key, and all of them are rate limited.


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=60, seconds=60)
def get_challenge(device: str) -> dict:
	"""A one-time nonce this kiosk must sign into its next request."""
	return Kiosk(device).challenge()


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=20, seconds=60)
def identify(device: str, nonce: str, embedding: str, signature: str) -> dict:
	"""Find out who a face belongs to and punch them in or out."""
	return Kiosk(device).identify(nonce, embedding, signature)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=20, seconds=60)
def look_up(device: str, nonce: str, employee: str, signature: str) -> dict:
	"""The name behind an employee id, shown before a PIN is entered."""
	return Kiosk(device).look_up(nonce, employee, signature)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=60)
def pin_check_in(device: str, nonce: str, employee: str, pin: str, photo: str, signature: str) -> dict:
	"""Punch in or out with an employee id and PIN. The photo is kept as proof."""
	return Kiosk(device).pin_punch(nonce, employee, pin, photo, signature)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=12, seconds=60)
def sync_offline(device: str, nonce: str, records: str, signature: str) -> list:
	"""Send the face scans saved while this kiosk had no connection. The server decides who each was."""
	return Kiosk(device).sync_offline(nonce, _as_list(records), signature)


def _as_list(records) -> list:
	parsed = frappe.parse_json(records) if isinstance(records, str) else records
	if not isinstance(parsed, list):
		frappe.throw("records must be a list.")
	return parsed
