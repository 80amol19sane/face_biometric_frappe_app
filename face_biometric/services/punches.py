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

	def next_log_type(self) -> str:
		"""IN after an OUT or nothing, OUT after an IN. Looks back 24h so night shifts still alternate."""
		last = frappe.db.get_value(
			"Employee Checkin",
			{"employee": self.employee, "time": [">=", add_to_date(now_datetime(), hours=-24)]},
			"log_type",
			order_by="time desc",
		)
		return "OUT" if last == "IN" else "IN"

	def record(
		self, log_type: str, device: str, latitude: float | None = None, longitude: float | None = None
	):
		"""Insert the Employee Checkin. Server time, never the phone's clock: a phone clock can be set to anything."""
		checkin = frappe.new_doc("Employee Checkin")
		checkin.employee = self.employee
		checkin.log_type = log_type
		checkin.time = now_datetime()
		checkin.device_id = device
		checkin.latitude = latitude
		checkin.longitude = longitude
		checkin.insert(ignore_permissions=True)
		return checkin
