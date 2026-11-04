import frappe
from frappe import _


def current_employee() -> str:
	"""The active Employee linked to the logged-in user."""
	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"})
	if not employee:
		frappe.throw(_("Your login is not linked to an active employee."), frappe.PermissionError)
	return employee


def owned_device(device: str, employee: str):
	"""The caller's own active device. Anything else gets the same error, so ids cannot be probed."""
	doc = frappe.db.get_value("Biometric Device", device, ["name", "employee", "status"], as_dict=True)
	if not doc or doc.employee != employee or doc.status != "Active":
		frappe.throw(_("This device is not registered to you."), frappe.PermissionError)
	return frappe.get_doc("Biometric Device", device)


ADMIN_ROLES = ("HR Manager", "System Manager")
