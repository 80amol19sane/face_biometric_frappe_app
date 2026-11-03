import frappe

from face_biometric.services.kiosk_registry import KioskRegistry


@frappe.whitelist(methods=["POST"])
def register_kiosk(public_key: str, label: str, location: str | None = None) -> dict:
	"""HR registers this phone as a kiosk. Only HR Manager and System Manager."""
	device = KioskRegistry().register(public_key, label, location)
	return {"device": device.name}
