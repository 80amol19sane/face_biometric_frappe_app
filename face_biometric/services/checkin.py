import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from face_biometric.core.challenge import ChallengeStore
from face_biometric.core.device_signature import signing_payload
from face_biometric.core.embedding import Embedding
from face_biometric.core.shift_standing import ShiftStanding
from face_biometric.face_biometric.doctype.face_biometric_settings.face_biometric_settings import get_settings
from face_biometric.services import verification_log
from face_biometric.services.identity import current_employee, owned_device

LOG_TYPES = ("IN", "OUT")


class FaceCheckin:
	"""One signed, face-matched punch. Every refusal is logged before it is raised."""

	def __init__(self):
		self.employee = current_employee()
		self.settings = get_settings()

	def challenge(self, device: str) -> dict:
		owned_device(device, self.employee)
		self._refuse_if_locked(device)
		ttl = self.settings.challenge_ttl_seconds
		return {"nonce": ChallengeStore(ttl).issue(device), "expires_in": ttl}

	def run(self, request: dict) -> dict:
		device = owned_device(request["device"], self.employee)
		self._refuse_if_locked(device.name)
		self._spend_challenge(device, request["nonce"])
		embedding = Embedding(request["embedding"])
		self._verify_signature(device, request, embedding)
		similarity = self._match(device, embedding)
		checkin = self._punch(device, request)
		verification_log.record(
			self.employee, "Matched", device.name, similarity=similarity, employee_checkin=checkin.name
		)
		device.touch()
		return {
			"name": checkin.name,
			"time": str(checkin.time),
			"log_type": checkin.log_type,
			"shift": self._shift_standing(checkin),
		}

	def _refuse_if_locked(self, device: str):
		failures = verification_log.recent_failures(self.employee, self.settings.lockout_minutes)
		if failures >= self.settings.max_failed_attempts:
			verification_log.record(self.employee, "Locked Out", device)
			self._refuse(_("Too many failed attempts. Try again later."))

	def _spend_challenge(self, device, nonce: str):
		if not ChallengeStore().consume(device.name, nonce):
			self._reject("Challenge Failed", device, _("The check-in request expired. Try again."))

	def _verify_signature(self, device, request: dict, embedding: Embedding):
		log_type = request["log_type"]
		if log_type not in LOG_TYPES:
			frappe.throw(_("Log type must be IN or OUT."))
		payload = signing_payload(
			request["nonce"], log_type, request.get("latitude"), request.get("longitude"), embedding.digest()
		)
		if not device.key().verify(payload, request["signature"]):
			self._reject("Bad Signature", device, _("This request was not signed by your device."))

	def _match(self, device, embedding: Embedding) -> float:
		template = self._active_template(device)
		similarity = template.load().similarity(embedding)
		if similarity < self.settings.match_threshold:
			self._reject("No Match", device, _("Your face was not recognised."), similarity=similarity)
		return similarity

	def _active_template(self, device):
		template = frappe.db.get_value(
			"Face Template", {"employee": self.employee, "status": "Active"}, "name"
		)
		if not template:
			self._reject("No Active Template", device, _("Your face is not enrolled or not approved yet."))
		return frappe.get_doc("Face Template", template)

	def _punch(self, device, request: dict):
		# Server time, never the phone's clock: a phone clock can be set to anything.
		checkin = frappe.new_doc("Employee Checkin")
		checkin.employee = self.employee
		checkin.log_type = request["log_type"]
		checkin.time = now_datetime()
		checkin.device_id = device.name
		checkin.latitude = request.get("latitude")
		checkin.longitude = request.get("longitude")
		checkin.insert(ignore_permissions=True)
		return checkin

	def _shift_standing(self, checkin) -> dict | None:
		"""HRMS resolves the shift while inserting the checkin; None when the punch is off-shift."""
		if not checkin.shift:
			return None
		grace = frappe.db.get_value(
			"Shift Type", checkin.shift, ["late_entry_grace_period", "early_exit_grace_period"], as_dict=True
		)
		standing = ShiftStanding(
			checkin.log_type,
			checkin.time,
			checkin.shift_start,
			checkin.shift_end,
			cint(grace.late_entry_grace_period),
			cint(grace.early_exit_grace_period),
		)
		return {"name": checkin.shift, **standing.evaluate()}

	def _reject(self, outcome: str, device, message: str, **fields):
		verification_log.record(self.employee, outcome, device.name, **fields)
		self._refuse(message)

	@staticmethod
	def _refuse(message: str):
		frappe.throw(message, frappe.PermissionError)
