from datetime import datetime

import frappe
from frappe.utils import add_to_date, getdate, now_datetime


class Punches:
	"""An employee's recent Employee Checkin rows, and what their next punch should be."""

	def __init__(self, employee: str):
		self.employee = employee

	def today(self) -> list[dict]:
		rows = frappe.get_all(
			"Employee Checkin",
			{"employee": self.employee, "time": [">=", getdate(now_datetime())]},
			["time", "log_type"],
			order_by="time asc",
		)
		return [{"time": str(row.time), "log_type": row.log_type} for row in rows]

	def last_punch(self) -> dict | None:
		"""The most recent punch in the last 24 hours, if any."""
		rows = frappe.get_all(
			"Employee Checkin",
			{"employee": self.employee, "time": [">=", add_to_date(now_datetime(), hours=-24)]},
			["time", "log_type"],
			order_by="time desc",
			limit=1,
		)
		return rows[0] if rows else None

	def next_log_type(self, at: datetime | None = None) -> str:
		"""IN after an OUT or nothing, OUT after an IN. Looks back 24h so night shifts still alternate.

		`at` is the moment being punched, for a scan that arrives late; punches after it are ignored.
		"""
		at = at or now_datetime()
		last = frappe.db.get_value(
			"Employee Checkin",
			{"employee": self.employee, "time": ["between", [add_to_date(at, hours=-24), at]]},
			"log_type",
			order_by="time desc",
		)
		return "OUT" if last == "IN" else "IN"

	def near(self, at: datetime, seconds: int) -> bool:
		"""Is there a punch within `seconds` of `at`, on either side?"""
		return bool(
			frappe.db.exists(
				"Employee Checkin",
				{
					"employee": self.employee,
					"time": [
						"between",
						[add_to_date(at, seconds=-seconds), add_to_date(at, seconds=seconds)],
					],
				},
			)
		)

	def record(
		self,
		log_type: str,
		device: str,
		latitude: float | None = None,
		longitude: float | None = None,
		at: datetime | None = None,
	):
		"""Insert the Employee Checkin. Server time, never the phone's clock: a phone clock can be set to anything.

		`at` is only for a scan saved offline, whose time the server has already worked out and checked.
		"""
		checkin = frappe.new_doc("Employee Checkin")
		checkin.employee = self.employee
		checkin.log_type = log_type
		checkin.time = at or now_datetime()
		checkin.device_id = device
		checkin.latitude = latitude
		checkin.longitude = longitude
		checkin.insert(ignore_permissions=True)
		return checkin
