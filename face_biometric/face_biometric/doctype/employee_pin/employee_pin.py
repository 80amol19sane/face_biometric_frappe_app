import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from face_biometric.core.pin import PinHash, pin_problem
from face_biometric.face_biometric.doctype.face_biometric_settings.face_biometric_settings import get_settings


class EmployeePIN(Document):
	def set_pin(self, pin: str):
		"""Replace the PIN. The caller is an HR user; nothing here ever returns or logs the PIN."""
		settings = get_settings()
		problem = pin_problem(pin, settings.pin_min_length, settings.pin_max_length)
		if problem:
			frappe.throw(_(problem))
		self.pin_hash = PinHash.make(pin)
		self.set_by = frappe.session.user
		self.set_on = now_datetime()
		self.enabled = 1

	def matches(self, pin: str) -> bool:
		return bool(self.enabled) and PinHash.verify(pin, self.pin_hash)
