import frappe
from frappe import _

from face_biometric.services.identity import ADMIN_ROLES


class KioskRegistry:
	"""HR registers a phone as a kiosk. This one-time step is what makes its signed requests trusted."""

	def __init__(self):
		frappe.only_for(ADMIN_ROLES)

	def register(self, public_key: str, label: str, location: str | None):
		if location and not frappe.db.exists("Shift Location", location):
			frappe.throw(_("That location does not exist."))
		device = frappe.get_doc(
			doctype="Biometric Device",
			device_kind="Kiosk",
			device_label=label,
			location=location or None,
			public_key=public_key,
			status="Active",
		)
		device.insert()
		return device
