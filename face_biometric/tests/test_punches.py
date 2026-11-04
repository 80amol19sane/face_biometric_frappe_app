import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime

from face_biometric.services.punches import Punches


class TestPunches(IntegrationTestCase):
	def setUp(self):
		self.employee = self.make_employee()
		self.punches = Punches(self.employee)

	def test_the_first_punch_of_the_day_is_in(self):
		self.assertEqual(self.punches.next_log_type(), "IN")
		self.assertEqual(self.punches.today(), [])

	def test_punches_alternate_and_are_listed_oldest_first(self):
		self.punch("IN", minutes=-30)
		self.assertEqual(self.punches.next_log_type(), "OUT")
		self.punch("OUT", minutes=-10)
		self.assertEqual(self.punches.next_log_type(), "IN")
		self.assertEqual([row["log_type"] for row in self.punches.today()], ["IN", "OUT"])

	def punch(self, log_type: str, minutes: int):
		frappe.get_doc(
			{
				"doctype": "Employee Checkin",
				"employee": self.employee,
				"log_type": log_type,
				"time": add_to_date(now_datetime(), minutes=minutes),
			}
		).insert(ignore_permissions=True)

	def make_employee(self) -> str:
		return frappe.db.get_value("Employee", {"status": "Active"}, "name")
