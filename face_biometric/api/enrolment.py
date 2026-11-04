import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import cint

from face_biometric.services.enrolment import Enrolment, StaffEnrolment
from face_biometric.services.identity import current_employee
from face_biometric.services.punches import Punches


@frappe.whitelist(methods=["POST"])
def register_device(public_key: str, label: str | None = None) -> dict:
	"""Bind this phone's public key to the logged-in employee."""
	device = Enrolment().register_device(public_key, label)
	return {"device": device.name}


@frappe.whitelist(methods=["GET"])
def my_status() -> dict:
	employee = current_employee()
	punches = Punches(employee)
	return {
		"next_log_type": punches.next_log_type(),
		"today": punches.today(),
		"template": frappe.db.get_value("Face Template", employee, "status"),
		"devices": frappe.get_all(
			"Biometric Device", {"employee": employee, "status": "Active"}, ["name", "device_label"]
		),
	}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=30, seconds=60)
def enrol_employee_face(employee: str, embedding: str, model_version: str, consent: bool) -> dict:
	"""HR enrols an employee's face in person. Active at once, with HR recorded as the approver."""
	template = StaffEnrolment().enrol_face(employee, embedding, model_version, bool(cint(consent)))
	return {"employee": template.employee, "status": template.status}
