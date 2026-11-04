import hashlib
from functools import cache

import frappe
from frappe import _
from frappe.utils import format_time, get_datetime, now_datetime, time_diff_in_seconds

from face_biometric.core.challenge import ChallengeStore
from face_biometric.core.device_signature import kiosk_payload
from face_biometric.core.embedding import Embedding
from face_biometric.core.matcher import AMBIGUOUS, MATCHED, FaceMatcher
from face_biometric.core.pin import ITERATIONS, PinHash
from face_biometric.core.proof_photo import ProofPhotoError, decode_proof_photo
from face_biometric.face_biometric.doctype.face_biometric_settings.face_biometric_settings import get_settings
from face_biometric.services import verification_log
from face_biometric.services.punches import Punches
from face_biometric.services.shift_report import shift_standing

PAUSE_AFTER_FAILURES = 5
PAUSE_MINUTES = 1
COOLDOWN_SECONDS = 120
WRONG_ID_OR_PIN = "Wrong employee ID or PIN."


class Kiosk:
	"""Requests from a shared kiosk phone. Nobody is logged in, so every request must be signed.

	The kiosk proves itself with the key an HR user registered for it: one-time nonce, then an ECDSA
	signature over what the request carries. A device id alone is not a credential.
	"""

	def __init__(self, device: str):
		self.settings = get_settings()
		self.device = self._load(device)

	def challenge(self) -> dict:
		self._refuse_if_paused()
		ttl = self.settings.challenge_ttl_seconds
		return {
			"nonce": ChallengeStore(ttl).issue(self.device.name),
			"expires_in": ttl,
			"config": self._config(),
		}

	def _config(self) -> dict:
		"""What the kiosk screen needs to behave as HR configured it. Nothing here is secret."""
		return {
			"require_liveness": bool(self.settings.require_liveness),
			"pin_enabled": bool(self.settings.pin_enabled),
			"pin_min_length": self.settings.pin_min_length,
			"pin_max_length": self.settings.pin_max_length,
			"return_seconds": self.settings.kiosk_return_seconds,
			"location": self.device.location,
			"label": self.device.device_label,
		}

	def identify(self, nonce: str, embedding_b64: str, signature: str) -> dict:
		"""Who is this face? Punches them in or out, or refuses without saying who came closest."""
		self._refuse_if_paused()
		self._spend(nonce)
		embedding = Embedding(embedding_b64)
		self._verify("identify", nonce, embedding.digest(), signature)
		matched = self._match(embedding)
		self._refuse_if_locked(matched.employee, "Face")
		return self._punch(matched.employee, "Face", similarity=matched.similarity)

	def look_up(self, nonce: str, employee: str, signature: str) -> dict:
		"""The name behind an employee id, so a person can confirm it is them before entering a PIN."""
		self._refuse_if_paused()
		self._spend(nonce)
		self._verify("lookup", nonce, _sha(employee.encode()), signature)
		name = frappe.db.get_value("Employee", {"name": employee, "status": "Active"}, "employee_name")
		if not name:
			self._fail(None, "Wrong PIN", WRONG_ID_OR_PIN, method="PIN", detail=_entered(employee))
		return {"employee": employee, "employee_name": name}

	def pin_punch(self, nonce: str, employee: str, pin: str, photo: str, signature: str) -> dict:
		if not self.settings.pin_enabled:
			frappe.throw(_("PIN attendance is turned off."), frappe.PermissionError)
		self._refuse_if_paused()
		self._spend(nonce)
		jpeg = self._photo(photo)
		self._verify("pin", nonce, _sha(employee.encode() + b"|" + jpeg), signature)
		known = bool(frappe.db.exists("Employee", {"name": employee, "status": "Active"}))
		if known:
			self._refuse_if_locked(employee, "PIN")
		self._check_pin(employee if known else None, employee, pin, jpeg)
		return self._punch(employee, "PIN", jpeg=jpeg)

	def _load(self, device: str):
		row = frappe.db.get_value("Biometric Device", device, ["name", "status", "device_kind"], as_dict=True)
		if not row or row.status != "Active" or row.device_kind != "Kiosk":
			frappe.throw(_("This kiosk is not registered."), frappe.PermissionError)
		return frappe.get_doc("Biometric Device", device)

	def _refuse_if_paused(self):
		if verification_log.recent_device_failures(self.device.name, PAUSE_MINUTES) >= PAUSE_AFTER_FAILURES:
			frappe.throw(_("This kiosk is paused for a minute. Please wait."), frappe.PermissionError)

	def _spend(self, nonce: str):
		if not ChallengeStore().consume(self.device.name, nonce):
			self._fail(None, "Challenge Failed", _("The request expired. Please try again."))

	def _verify(self, action: str, nonce: str, digest: str, signature: str):
		payload = kiosk_payload(action, self.device.name, nonce, digest)
		if not self.device.key().verify(payload, signature):
			self._fail(None, "Bad Signature", _("This request was not signed by the kiosk."))

	def _match(self, embedding: Embedding):
		scored = []
		for name in frappe.get_all("Face Template", {"status": "Active"}, pluck="name"):
			template = frappe.get_doc("Face Template", name)
			enrolled = template.load()
			if enrolled.dimensions == embedding.dimensions:
				scored.append((template.employee, enrolled.similarity(embedding)))
		matcher = FaceMatcher(self.settings.match_threshold, self.settings.identify_margin)
		result = matcher.decide(scored)
		if result.status == MATCHED and self._is_active(result.employee):
			return result
		outcome = "Ambiguous Face" if result.status == AMBIGUOUS else "Unknown Face"
		message = (
			_("We could not tell who you are. Please use your PIN.")
			if result.status == AMBIGUOUS
			else _("We could not recognise you.")
		)
		self._fail(None, outcome, message, similarity=result.similarity)

	def _check_pin(self, employee: str | None, entered: str, pin: str, jpeg: bytes):
		"""Every failure looks the same to the caller, and costs the same time, so IDs cannot be probed."""
		row = (
			frappe.get_doc("Employee PIN", employee)
			if employee and frappe.db.exists("Employee PIN", employee)
			else None
		)
		ok = PinHash.verify(pin, row.pin_hash if row else _dummy_hash())
		if row and ok and row.enabled:
			return
		outcome = "Wrong PIN" if row and row.enabled else ("PIN Disabled" if row else "No PIN")
		detail = None if employee else _entered(entered)
		self._fail(employee, outcome, _(WRONG_ID_OR_PIN), method="PIN", detail=detail, photo=jpeg)

	def _refuse_if_locked(self, employee: str, method: str):
		failures = verification_log.recent_failures(employee, self.settings.lockout_minutes)
		if failures >= self.settings.max_failed_attempts:
			verification_log.record(employee, "Locked Out", self.device.name, method=method)
			frappe.throw(_("Too many failed attempts. Try again later."), frappe.PermissionError)

	def _punch(
		self, employee: str, method: str, similarity: float | None = None, jpeg: bytes | None = None
	) -> dict:
		punches = Punches(employee)
		self._refuse_if_just_punched(punches)
		checkin = punches.record(punches.next_log_type(), self.device.name)
		if jpeg:
			_attach(jpeg, "Employee Checkin", checkin.name, employee)
		verification_log.record(
			employee,
			"Matched",
			self.device.name,
			method=method,
			similarity=similarity,
			employee_checkin=checkin.name,
		)
		self.device.touch()
		return self._result(employee, checkin, method)

	def _refuse_if_just_punched(self, punches: Punches):
		last = punches.last_punch()
		if last and time_diff_in_seconds(now_datetime(), last.time) < COOLDOWN_SECONDS:
			word = "in" if last.log_type == "IN" else "out"
			at = format_time(get_datetime(last.time).time(), "h:mm a")
			frappe.throw(_("You already checked {0} at {1}.").format(word, at), frappe.ValidationError)

	def _result(self, employee: str, checkin, method: str) -> dict:
		details = frappe.db.get_value(
			"Employee", employee, ["employee_name", "department", "designation"], as_dict=True
		)
		return {
			"name": checkin.name,
			"time": str(checkin.time),
			"log_type": checkin.log_type,
			"method": method,
			"employee": employee,
			"employee_name": details.employee_name,
			"department": details.department,
			"designation": details.designation,
			"shift": shift_standing(checkin),
		}

	@staticmethod
	def _is_active(employee: str) -> bool:
		return bool(frappe.db.exists("Employee", {"name": employee, "status": "Active"}))

	@staticmethod
	def _photo(photo: str) -> bytes:
		try:
			return decode_proof_photo(photo)
		except ProofPhotoError as error:
			frappe.throw(_(str(error)))

	def _fail(
		self, employee, outcome: str, message: str, method: str = "Face", photo: bytes | None = None, **fields
	):
		"""Log the refusal first (it commits), then raise. A wrong-PIN photo stays on the log for HR."""
		log = verification_log.record(employee, outcome, self.device.name, method=method, **fields)
		if photo:
			_attach(photo, "Face Verification Log", log, employee)
			frappe.db.commit()
		frappe.throw(message, frappe.PermissionError)


def _attach(jpeg: bytes, doctype: str, name: str, employee: str | None):
	frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"proof-{employee or 'unknown'}-{now_datetime():%Y%m%d%H%M%S}.jpg",
			"content": jpeg,
			"is_private": 1,
			"attached_to_doctype": doctype,
			"attached_to_name": name,
		}
	).insert(ignore_permissions=True)


def _sha(data: bytes) -> str:
	return hashlib.sha256(data).hexdigest()


def _entered(employee: str) -> str:
	return f"ID entered: {employee[:40]}"


@cache
def _dummy_hash() -> str:
	"""Verified against when the ID is unknown, so a wrong ID takes as long as a wrong PIN."""
	return PinHash.make("000000", ITERATIONS)
