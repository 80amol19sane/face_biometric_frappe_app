import frappe
from frappe import _
from frappe.utils import now_datetime

from face_biometric.core.embedding import Embedding
from face_biometric.face_biometric.doctype.face_biometric_settings.face_biometric_settings import get_settings
from face_biometric.services.identity import current_employee, owned_device


STAFF_ROLES = ("HR Manager", "System Manager")


def template_for(employee: str):
	"""The employee's Face Template, new if they have none yet. Templates are named after the employee."""
	if frappe.db.exists("Face Template", employee):
		return frappe.get_doc("Face Template", employee)
	return frappe.new_doc("Face Template", employee=employee)


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
		return template_for(self.employee)

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


class StaffEnrolment:
	"""HR enrols an employee's face in person, on HR's own phone.

	HR seeing the person is the approval, so the template goes straight to Active with HR as approver.
	The employee still registers their own phone key when they first sign in on it: this never
	creates a Biometric Device, so a staff member cannot check in as someone else.
	"""

	def __init__(self):
		frappe.only_for(STAFF_ROLES)
		self.settings = get_settings()

	def enrol_face(self, employee: str, embedding: str, model_version: str, consent: bool):
		self._require_active_employee(employee)
		self._refuse_own_face(employee)
		if not consent:
			frappe.throw(_("The employee's consent is needed to store a face template."))
		if model_version != self.settings.embedding_model:
			frappe.throw(_("This app's face model is not accepted. Update the app."))

		template = template_for(employee)
		template.store(Embedding(embedding), model_version)
		template.consent_given_on = now_datetime()
		template.status = "Active"
		template.approved_by = frappe.session.user
		template.approved_on = now_datetime()
		template.save(ignore_permissions=True)
		return template

	@staticmethod
	def _require_active_employee(employee: str):
		if frappe.db.get_value("Employee", employee, "status") != "Active":
			frappe.throw(_("{0} is not an active employee.").format(employee))

	@staticmethod
	def _refuse_own_face(employee: str):
		if frappe.db.get_value("Employee", {"user_id": frappe.session.user}) == employee:
			frappe.throw(_("You cannot enrol your own face here. Enrol it from your own phone."))
