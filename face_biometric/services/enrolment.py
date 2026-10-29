import frappe
from frappe import _
from frappe.utils import now_datetime

from face_biometric.core.embedding import Embedding
from face_biometric.face_biometric.doctype.face_biometric_settings.face_biometric_settings import get_settings
from face_biometric.services.identity import current_employee, owned_device


class Enrolment:
	"""Registers a phone and its owner's face. Always acts for the logged-in employee."""

	def __init__(self):
		self.employee = current_employee()
		self.settings = get_settings()

	def register_device(self, public_key: str, label: str | None = None):
		device = frappe.get_doc(
			doctype="Biometric Device", employee=self.employee, public_key=public_key, device_label=label
		)
		device.insert(ignore_permissions=True)
		return device

	def enrol_face(self, device: str, embedding: str, model_version: str, consent: bool):
		owned_device(device, self.employee)
		if not consent:
			frappe.throw(_("Consent is needed to store a face template."))
		if model_version != self.settings.embedding_model:
			frappe.throw(_("This app's face model is not accepted. Update the app."))

		template = self._template()
		template.store(Embedding(embedding), model_version)
		template.consent_given_on = now_datetime()
		self._reset_approval(template)
		template.save(ignore_permissions=True)
		return template

	def _template(self):
		if frappe.db.exists("Face Template", self.employee):
			return frappe.get_doc("Face Template", self.employee)
		return frappe.new_doc("Face Template", employee=self.employee)

	def _reset_approval(self, template):
		"""A new face always needs fresh approval, so a face cannot be swapped silently."""
		template.approved_by = None
		template.approved_on = None
		if self.settings.require_enrolment_approval:
			template.status = "Pending"
		else:
			template.status = "Active"
			template.approved_by = frappe.session.user
			template.approved_on = now_datetime()
