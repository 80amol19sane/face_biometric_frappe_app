import frappe
from frappe import _
from frappe.utils import add_days, get_datetime, getdate, now_datetime
from frappe.utils.password import check_password

from face_biometric.core.phone import mask_phone
from face_biometric.face_biometric.doctype.face_biometric_settings.face_biometric_settings import get_settings
from face_biometric.services.identity import ADMIN_ROLES
from face_biometric.services.shift_report import shift_standing
from face_biometric.services.verification_log import NOT_FAILURES

SETTING_FIELDS = (
	"require_liveness",
	"pin_enabled",
	"pin_min_length",
	"pin_max_length",
	"kiosk_return_seconds",
	"photo_retention_days",
	"offline_enabled",
	"offline_max_hours",
	"held_retention_days",
	"offline_review_floor",
)
SYSTEM_MANAGER_FIELDS = (
	"match_threshold",
	"identify_margin",
	"max_failed_attempts",
	"lockout_minutes",
	"offline_clock_tolerance_minutes",
)


class AdminDesk:
	"""Everything the admin screens read or change. Only HR Manager and System Manager get in."""

	def __init__(self):
		frappe.only_for(ADMIN_ROLES)

	def dashboard(self) -> dict:
		active = set(frappe.get_all("Employee", {"status": "Active"}, pluck="name"))
		with_face = set(frappe.get_all("Face Template", {"status": "Active"}, pluck="employee")) & active
		with_pin = set(frappe.get_all("Employee PIN", {"enabled": 1}, pluck="employee")) & active
		today = getdate(now_datetime())
		present = set(
			frappe.get_all("Employee Checkin", {"log_type": "IN", "time": [">=", today]}, pluck="employee")
		)
		return {
			"total": len(active),
			"face_registered": len(with_face),
			"pin_registered": len(with_pin),
			"not_enrolled": len(active - with_face - with_pin),
			"present_today": len(present & active),
			"failed_today": self._failures({"creation": [">=", today]}, count=True),
			"pending": frappe.db.count("Face Template", {"status": "Pending"}),
			"offline_today": frappe.db.count(
				"Face Verification Log",
				{"outcome": "Matched", "recorded_at": ["is", "set"], "creation": [">=", today]},
			),
			"awaiting_review": frappe.db.count("Face Verification Log", {"outcome": "Offline Held"}),
		}

	def employees(self, search: str | None, show: str, start: int, limit: int) -> dict:
		faces = {r.employee: r.status for r in frappe.get_all("Face Template", fields=["employee", "status"])}
		pins = {r.employee: r.enabled for r in frappe.get_all("Employee PIN", fields=["employee", "enabled"])}
		filters: list = [["status", "=", "Active"]]
		if show == "inactive":
			filters = [["status", "!=", "Active"]]
		elif show == "no_face":
			filters.append(["name", "not in", [e for e, s in faces.items() if s == "Active"] or [""]])
		elif show == "no_pin":
			filters.append(["name", "not in", [e for e, on in pins.items() if on] or [""]])
		like = f"%{(search or '').strip()}%"
		or_filters = [["employee_name", "like", like], ["name", "like", like], ["cell_number", "like", like]]
		rows = frappe.get_all(
			"Employee",
			filters=filters,
			or_filters=or_filters if search else None,
			fields=["name", "employee_name", "department", "designation", "cell_number", "status"],
			order_by="employee_name asc",
			start=int(start),
			limit=min(int(limit), 100),
		)
		return {
			"employees": [self._row(r, faces, pins) for r in rows],
			"counts": self._counts(faces, pins),
		}

	def profile(self, employee: str) -> dict:
		row = frappe.db.get_value(
			"Employee",
			employee,
			["name", "employee_name", "department", "designation", "cell_number", "status", "default_shift"],
			as_dict=True,
		)
		if not row:
			frappe.throw(_("Employee not found."), frappe.DoesNotExistError)
		face = frappe.db.get_value(
			"Face Template",
			employee,
			["status", "approved_by", "approved_on", "model_version", "dimensions", "creation", "modified"],
			as_dict=True,
		)
		pin = frappe.db.get_value("Employee PIN", employee, ["enabled", "set_by", "set_on"], as_dict=True)
		return {
			"employee": row.name,
			"employee_name": row.employee_name,
			"department": row.department,
			"designation": row.designation,
			"mobile": mask_phone(row.cell_number),
			"status": row.status,
			"shift": row.default_shift,
			"face": face and {**face, "creation": str(face.creation), "modified": str(face.modified)},
			"pin": pin and {**pin, "set_on": str(pin.set_on) if pin.set_on else None},
		}

	def set_pin(self, employee: str, pin: str, password: str) -> dict:
		self._reauthenticate(password)
		self._require_other_active_employee(employee)
		doc = frappe.get_doc("Employee PIN", employee) if frappe.db.exists("Employee PIN", employee) else None
		verb = "reset" if doc else "set"
		doc = doc or frappe.get_doc(doctype="Employee PIN", employee=employee)
		doc.set_pin(pin)
		doc.save(ignore_permissions=True)
		doc.add_comment("Info", _("PIN {0} by {1}.").format(verb, frappe.session.user))
		return {"employee": employee, "enabled": 1}

	def set_pin_enabled(self, employee: str, enabled: bool, password: str) -> dict:
		self._reauthenticate(password)
		self._require_other_active_employee(employee)
		if not frappe.db.exists("Employee PIN", employee):
			frappe.throw(_("This employee has no PIN yet."))
		doc = frappe.get_doc("Employee PIN", employee)
		doc.enabled = 1 if enabled else 0
		doc.save(ignore_permissions=True)
		doc.add_comment(
			"Info", _("PIN {0} by {1}.").format("enabled" if enabled else "disabled", frappe.session.user)
		)
		return {"employee": employee, "enabled": doc.enabled}

	def history(self, employee: str) -> list[dict]:
		"""Face changes come from the template's version history. PIN changes are timeline comments:
		a version log of Employee PIN would store the PIN hash, so that doctype does not track changes."""
		events = []
		if frappe.db.exists("Face Template", employee):
			created = frappe.db.get_value("Face Template", employee, ["creation", "owner"], as_dict=True)
			events.append(self._event(created.creation, created.owner, "Face registered"))
			for version in frappe.get_all(
				"Version",
				{"ref_doctype": "Face Template", "docname": employee},
				["creation", "owner", "data"],
				order_by="creation asc",
			):
				summary = self._version_summary("Face", version.data)
				if summary:
					events.append(self._event(version.creation, version.owner, summary))
		for comment in frappe.get_all(
			"Comment",
			{"reference_doctype": "Employee PIN", "reference_name": employee, "comment_type": "Info"},
			["creation", "owner", "content"],
		):
			events.append(
				self._event(comment.creation, comment.owner, frappe.utils.strip_html(comment.content))
			)
		return sorted(events, key=lambda e: e["when"], reverse=True)

	def attendance(self, date: str | None, start: int, limit: int) -> dict:
		day = getdate(date) if date else getdate(now_datetime())
		filters = [["time", ">=", day], ["time", "<", add_days(day, 1)]]
		fields = [
			"name",
			"employee",
			"employee_name",
			"log_type",
			"time",
			"shift",
			"shift_start",
			"shift_end",
			"device_id",
		]
		rows = frappe.get_all("Employee Checkin", filters=filters, fields=fields, order_by="time desc")
		methods = self._methods([r.name for r in rows])
		late = 0
		for row in rows:
			row["method"] = methods.get(row.name, "Face")
			row["standing"] = shift_standing(row)
			late += bool(row["standing"] and row["standing"]["status"] == "Late")
		page = rows[int(start) : int(start) + min(int(limit), 200)]
		return {
			"date": str(day),
			"summary": {
				"in": sum(r.log_type == "IN" for r in rows),
				"out": sum(r.log_type == "OUT" for r in rows),
				"late": late,
				"by_pin": sum(r["method"] == "PIN" for r in rows),
			},
			"logs": [self._log(r) for r in page],
		}

	def failed_attempts(self, date: str | None, method: str | None) -> list[dict]:
		day = getdate(date) if date else getdate(now_datetime())
		extra = {"creation": ["between", [day, add_days(day, 1)]]}
		if method in ("Face", "PIN"):
			extra["method"] = method
		return self._failures(extra)

	def devices(self) -> list[dict]:
		return [
			{**d, "last_seen": str(d.last_seen) if d.last_seen else None}
			for d in frappe.get_all(
				"Biometric Device",
				fields=[
					"name",
					"device_kind",
					"device_label",
					"location",
					"allow_offline",
					"status",
					"employee_name",
					"last_seen",
				],
				order_by="device_kind desc, modified desc",
			)
		]

	def revoke_device(self, device: str) -> dict:
		frappe.get_doc("Biometric Device", device).revoke()
		return {"device": device, "status": "Revoked"}

	def sync_status(self) -> dict:
		last = frappe.get_all(
			"Employee Checkin",
			{"device_id": ["is", "set"]},
			["time", "employee"],
			order_by="time desc",
			limit=1,
		)
		return {
			"server_time": str(now_datetime()),
			"site": frappe.local.site,
			"last_punch": last and {"time": str(last[0].time), "employee": last[0].employee},
			"templates": frappe.db.count("Face Template", {"status": "Active"}),
			"settings_updated": str(get_settings().modified),
		}

	def settings(self) -> dict:
		doc = get_settings()
		fields = SETTING_FIELDS + SYSTEM_MANAGER_FIELDS
		return {
			**{f: doc.get(f) for f in fields},
			"can_edit_recognition": "System Manager" in frappe.get_roles(),
		}

	def update_settings(self, values: dict) -> dict:
		doc = frappe.get_doc("Face Biometric Settings")
		for field, value in values.items():
			if field in SYSTEM_MANAGER_FIELDS:
				frappe.only_for("System Manager")
			elif field not in SETTING_FIELDS:
				frappe.throw(_("{0} cannot be changed here.").format(field))
			doc.set(field, value)
		doc.save()
		frappe.cache.delete_value("Face Biometric Settings")
		return self.settings()

	def _row(self, row, faces: dict, pins: dict) -> dict:
		return {
			"employee": row.name,
			"employee_name": row.employee_name,
			"department": row.department,
			"designation": row.designation,
			"mobile": mask_phone(row.cell_number),
			"status": row.status,
			"face": faces.get(row.name),
			"pin": None if row.name not in pins else bool(pins[row.name]),
		}

	def _counts(self, faces: dict, pins: dict) -> dict:
		active = set(frappe.get_all("Employee", {"status": "Active"}, pluck="name"))
		return {
			"all": len(active),
			"no_face": len(active - {e for e, s in faces.items() if s == "Active"}),
			"no_pin": len(active - {e for e, on in pins.items() if on}),
			"inactive": frappe.db.count("Employee", {"status": ["!=", "Active"]}),
		}

	def _failures(self, extra: dict, count: bool = False):
		filters = {"outcome": ["not in", NOT_FAILURES], **extra}
		if count:
			return frappe.db.count("Face Verification Log", filters)
		rows = frappe.get_all(
			"Face Verification Log",
			filters,
			["name", "creation", "employee", "outcome", "method", "similarity", "detail", "device"],
			order_by="creation desc",
			limit=200,
		)
		photos = {
			f.attached_to_name: f.file_url
			for f in frappe.get_all(
				"File",
				{
					"attached_to_doctype": "Face Verification Log",
					"attached_to_name": ["in", [r.name for r in rows] or [""]],
				},
				["attached_to_name", "file_url"],
			)
		}
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
				"creation": str(r.creation),
				"employee_name": names.get(r.employee),
				"photo": photos.get(r.name),
			}
			for r in rows
		]

	@staticmethod
	def _methods(checkins: list[str]) -> dict:
		rows = frappe.get_all(
			"Face Verification Log",
			{"employee_checkin": ["in", checkins or [""]]},
			["employee_checkin", "method"],
		)
		return {r.employee_checkin: r.method for r in rows}

	@staticmethod
	def _log(row) -> dict:
		return {
			"name": row.name,
			"employee": row.employee,
			"employee_name": row.employee_name,
			"log_type": row.log_type,
			"time": str(row.time),
			"method": row["method"],
			"device": row.device_id,
			"standing": row["standing"],
		}

	@staticmethod
	def _event(when, by: str, summary: str) -> dict:
		return {"when": str(get_datetime(when)), "by": by, "summary": summary}

	@staticmethod
	def _version_summary(label: str, data: str) -> str | None:
		changed = {c[0]: c for c in frappe.parse_json(data).get("changed", [])}
		if "status" in changed:
			return f"{label} {str(changed['status'][2]).lower()}"
		if "embedding" in changed:
			return f"{label} updated"
		return None

	@staticmethod
	def _reauthenticate(password: str):
		try:
			check_password(frappe.session.user, password)
		except frappe.AuthenticationError:
			frappe.throw(_("Your password is not correct."), frappe.PermissionError)

	@staticmethod
	def _require_other_active_employee(employee: str):
		if not frappe.db.exists("Employee", {"name": employee, "status": "Active"}):
			frappe.throw(_("Employee not found."), frappe.DoesNotExistError)
		if frappe.db.get_value("Employee", {"user_id": frappe.session.user}) == employee:
			frappe.throw(_("You cannot change your own PIN. Ask another HR Manager."))
