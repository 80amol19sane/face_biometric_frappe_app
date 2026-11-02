import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from face_biometric.core.device_signature import DeviceKey


class BiometricDevice(Document):
	def validate(self):
		if self.is_new():
			self.key()
			self.registered_on = now_datetime()
			self.require_unused_key()

	@frappe.whitelist(methods=["POST"])
	def revoke(self):
		frappe.has_permission(self.doctype, "write", self, throw=True)
		self.status = "Revoked"
		self.save()

	def key(self) -> DeviceKey:
		return DeviceKey(self.public_key)

	def touch(self):
		self.db_set("last_seen", now_datetime(), update_modified=False)

	def require_unused_key(self):
		if frappe.db.exists("Biometric Device", {"public_key": self.public_key}):
			frappe.throw(_("This device key is already registered."))
