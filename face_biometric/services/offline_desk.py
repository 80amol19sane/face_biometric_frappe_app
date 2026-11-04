import frappe
from frappe import _
from frappe.utils import cint

from face_biometric.services.identity import ADMIN_ROLES
from face_biometric.services.punches import Punches

LOG = "Face Verification Log"
DOUBLE_PUNCH_SECONDS = 120


class OfflineDesk:
	"""HR's review of offline scans the server could not settle by itself. HR Manager and System Manager only."""

	def __init__(self):
		frappe.only_for(ADMIN_ROLES)

	def held(self) -> list[dict]:
		rows = frappe.get_all(
			LOG,
			{"outcome": "Offline Held"},
			["name", "creation", "employee", "device", "recorded_at", "similarity", "detail"],
			order_by="recorded_at asc",
			limit=200,
		)
		names = dict(
			frappe.get_all(
				"Employee",
				{"name": ["in", [r.employee for r in rows if r.employee] or [""]]},
				["name", "employee_name"],
				as_list=True,
			)
		)
		return [
			{
				**r,
				"recorded_at": str(r.recorded_at),
				"creation": str(r.creation),
				"employee_name": names.get(r.employee),
			}
			for r in rows
		]

	def approve(self, log: str, note: str) -> dict:
		"""HR confirms the person was there: make the Employee Checkin at the time of the scan."""
		row = self._held(log, note)
		punches = Punches(row.employee)
		if punches.near(row.recorded_at, DOUBLE_PUNCH_SECONDS):
			frappe.throw(_("This employee already has a punch at that time."))
		checkin = punches.record(punches.next_log_type(row.recorded_at), row.device, at=row.recorded_at)
		checkin.add_comment(
			"Info",
			f"Recorded offline at kiosk {row.device}; approved by {frappe.session.user}: {note.strip()}",
		)
		self._close(row, "Offline Approved", note, employee_checkin=checkin.name)
		return {"log": log, "outcome": "Offline Approved", "checkin": checkin.name}

	def reject(self, log: str, note: str) -> dict:
		self._close(self._held(log, note), "Offline Rejected", note)
		return {"log": log, "outcome": "Offline Rejected"}

	def set_device(self, device: str, allow: int) -> dict:
		kind = frappe.db.get_value("Biometric Device", device, "device_kind")
		if kind != "Kiosk":
			frappe.throw(_("Only a kiosk can take attendance offline."))
		frappe.db.set_value("Biometric Device", device, "allow_offline", 1 if cint(allow) else 0)
		return {"device": device, "allow_offline": 1 if cint(allow) else 0}

	@staticmethod
	def _held(log: str, note: str):
		if not (note or "").strip():
			frappe.throw(_("Write a short note saying why."))
		row = frappe.get_doc(LOG, log)
		if row.outcome != "Offline Held" or not row.employee or not row.recorded_at:
			frappe.throw(_("This scan is not waiting for review."))
		return row

	@staticmethod
	def _close(row, outcome: str, note: str, **fields):
		decision = f"{outcome.removeprefix('Offline ')} by {frappe.session.user}: {note.strip()}"
		row.db_set({"outcome": outcome, "detail": f"{row.detail or ''} {decision}".strip(), **fields})
