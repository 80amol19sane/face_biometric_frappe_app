import frappe
from frappe.rate_limiter import rate_limit

from face_biometric.services.checkin import FaceCheckin


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=20, seconds=60)
def get_challenge(device: str) -> dict:
	"""A one-time nonce the phone must sign into its next check-in."""
	return FaceCheckin().challenge(device)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=10, seconds=60)
def check_in(
	device: str,
	nonce: str,
	log_type: str,
	embedding: str,
	signature: str,
	latitude: float | None = None,
	longitude: float | None = None,
) -> dict:
	"""Punch in or out after the face matches and the device signature checks out."""
	return FaceCheckin().run(
		{
			"device": device,
			"nonce": nonce,
			"log_type": log_type,
			"embedding": embedding,
			"signature": signature,
			"latitude": latitude,
			"longitude": longitude,
		}
	)
