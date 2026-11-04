import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import cint

from face_biometric.services.admin_desk import AdminDesk
from face_biometric.services.kiosk_registry import KioskRegistry


@frappe.whitelist(methods=["POST"])
def register_kiosk(public_key: str, label: str, location: str | None = None) -> dict:
	"""HR registers this phone as a kiosk. Only HR Manager and System Manager."""
	device = KioskRegistry().register(public_key, label, location)
	return {"device": device.name}


@frappe.whitelist(methods=["GET"])
def dashboard() -> dict:
	return AdminDesk().dashboard()


@frappe.whitelist(methods=["GET"])
def employees(search: str | None = None, show: str = "all", start: int = 0, limit: int = 30) -> dict:
	return AdminDesk().employees(search, show, start, limit)


@frappe.whitelist(methods=["GET"])
def employee_profile(employee: str) -> dict:
	return AdminDesk().profile(employee)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=10, seconds=60)
def set_pin(employee: str, pin: str, password: str) -> dict:
	"""Set or reset an employee's PIN. The admin's own password is required."""
	return AdminDesk().set_pin(employee, pin, password)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=10, seconds=60)
def set_pin_enabled(employee: str, enabled: bool, password: str) -> dict:
	return AdminDesk().set_pin_enabled(employee, bool(cint(enabled)), password)


@frappe.whitelist(methods=["GET"])
def biometric_history(employee: str) -> list:
	return AdminDesk().history(employee)


@frappe.whitelist(methods=["GET"])
def attendance_logs(date: str | None = None, start: int = 0, limit: int = 50) -> dict:
	return AdminDesk().attendance(date, start, limit)


@frappe.whitelist(methods=["GET"])
def failed_attempts(date: str | None = None, method: str | None = None) -> list:
	return AdminDesk().failed_attempts(date, method)


@frappe.whitelist(methods=["GET"])
def devices() -> list:
	return AdminDesk().devices()


@frappe.whitelist(methods=["POST"])
def revoke_device(device: str) -> dict:
	return AdminDesk().revoke_device(device)


@frappe.whitelist(methods=["GET"])
def sync_status() -> dict:
	return AdminDesk().sync_status()


@frappe.whitelist(methods=["GET"])
def get_settings() -> dict:
	return AdminDesk().settings()


@frappe.whitelist(methods=["POST"])
def update_settings(values: str) -> dict:
	"""`values` is a JSON object of setting name to value."""
	return AdminDesk().update_settings(frappe.parse_json(values))
