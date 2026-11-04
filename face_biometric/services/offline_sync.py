from dataclasses import replace
from datetime import UTC, datetime

import frappe
from frappe.utils import convert_utc_to_system_timezone, now_datetime

from face_biometric.core.embedding import Embedding
from face_biometric.core.matcher import AMBIGUOUS, MATCHED, NO_MATCH
from face_biometric.core.offline_record import OfflineRecord, OfflineRecordError, record_hash
from face_biometric.core.offline_time import time_problems
from face_biometric.services import verification_log
from face_biometric.services.face_search import FaceSearch
from face_biometric.services.punches import Punches

ACCEPTED, DUPLICATE, HELD, REJECTED = "Accepted", "Duplicate", "Held", "Rejected"
DOUBLE_PUNCH_SECONDS = 120
LOG = "Face Verification Log"


class OfflineSync:
	"""Settles the face scans a kiosk saved while it had no connection.

	The phone never decided who anyone was: it only kept the scan. Here the server matches it with
	the same rule as an online punch, checks when it was taken, and either makes the Employee Checkin,
	holds it for HR, or refuses it. Every scan leaves exactly one Face Verification Log row, which is
	also what makes sending the same scan twice harmless.
	"""

	def __init__(self, device, settings):
		self.device = device
		self.settings = settings
		self.search = FaceSearch(settings)

	def settle(self, raws: list) -> list[dict]:
		return [self._settle_one(raw) for raw in raws]

	def _settle_one(self, raw) -> dict:
		try:
			record = OfflineRecord.parse(raw)
		except OfflineRecordError as error:
			return self._result(raw.get("local_id") if isinstance(raw, dict) else None, REJECTED, str(error))
		if self._seen(record.local_id):
			return self._result(record.local_id, DUPLICATE)
		try:
			embedding = Embedding(record.embedding)
		except frappe.ValidationError:
			return self._close(record, "Offline Rejected", REJECTED, "The scan could not be read.")
		payload = record.payload(self.device.name, embedding.digest())
		if not self.device.key().verify(payload, record.signature):
			return self._close(
				record, "Bad Signature", REJECTED, "The scan was not signed by this kiosk.", payload
			)
		return self._decide(record, embedding, payload)

	def _decide(self, record: OfflineRecord, embedding: Embedding, payload: bytes) -> dict:
		found = self.search.find(embedding)
		claimed = self._claimed(record)
		if claimed and (found.status != MATCHED or found.employee != claimed):
			held = self._hold_claim(record, embedding, payload, found, claimed)
			if held:
				return held
		if self._looks_like_someone(found):
			return self._hold_near_miss(record, payload, found)
		if found.status != MATCHED:
			reason = (
				"More than one person looked alike."
				if found.status == AMBIGUOUS
				else "No enrolled face matched."
			)
			return self._close(
				record, "Offline Rejected", REJECTED, reason, payload, similarity=found.similarity
			)
		taken = self._taken_at(record)
		if Punches(found.employee).near(taken, DOUBLE_PUNCH_SECONDS):
			return self._close(
				record, "Offline Duplicate", DUPLICATE, "Already punched at that time.", payload, found, taken
			)
		problems = self._problems(record)
		if problems:
			return self._close(record, "Offline Held", HELD, " ".join(problems), payload, found, taken)
		return self._accept(record, payload, found, taken)

	def _looks_like_someone(self, found) -> bool:
		return (
			found.status == NO_MATCH
			and bool(found.candidate)
			and found.similarity >= self.settings.offline_review_floor
		)

	def _hold_near_miss(self, record: OfflineRecord, payload: bytes, found) -> dict:
		"""Not sure enough to punch anyone in, too close to throw away: HR sees the closest employee and decides."""
		reason = (
			f"Closest match only ({found.similarity:.2f}, below the {self.settings.match_threshold:.2f} needed). "
			"HR must confirm who this was."
		)
		return self._hold(record, payload, replace(found, employee=found.candidate), reason)

	def _hold_claim(self, record: OfflineRecord, embedding: Embedding, payload: bytes, found, claimed: str):
		"""The person typed an employee ID at the kiosk. It is a hint: it only gets the scan in front of HR."""
		similarity = self.search.similarity_to(claimed, embedding)
		if similarity is None or similarity < self.settings.offline_review_floor:
			return None
		reason = f"The person entered ID {claimed}; their face is {similarity:.2f} alike to that employee."
		if found.status == MATCHED:
			reason += f" The face matched {found.employee} ({found.similarity:.2f}) instead."
		return self._hold(record, payload, replace(found, employee=claimed, similarity=similarity), reason)

	def _hold(self, record: OfflineRecord, payload: bytes, found, reason: str) -> dict:
		return self._close(
			record,
			"Offline Held",
			HELD,
			" ".join([reason, *self._problems(record)]),
			payload,
			found,
			self._taken_at(record),
		)

	@staticmethod
	def _claimed(record: OfflineRecord) -> str:
		"""The typed ID if it names a real, active employee; otherwise nothing."""
		name = record.claimed_employee
		return name if name and frappe.db.exists("Employee", {"name": name, "status": "Active"}) else ""

	def _accept(self, record: OfflineRecord, payload: bytes, found, taken: datetime) -> dict:
		punches = Punches(found.employee)
		try:
			checkin = punches.record(punches.next_log_type(taken), self.device.name, at=taken)
		except frappe.ValidationError as error:
			frappe.db.rollback()
			return self._close(
				record, "Offline Held", HELD, f"HRMS refused the check-in: {error}", payload, found, taken
			)
		checkin.add_comment(
			"Info",
			f"Recorded offline at kiosk {self.device.name} and synced {now_datetime():%Y-%m-%d %H:%M}.",
		)
		return self._close(
			record, "Matched", ACCEPTED, "Offline scan.", payload, found, taken, checkin=checkin.name
		)

	def _problems(self, record: OfflineRecord) -> list[str]:
		problems = time_problems(
			anchored_ms=record.anchored_ms,
			wall_ms=record.wall_ms,
			boot_count=record.boot_count,
			anchor_boot_count=record.anchor_boot_count,
			now_ms=int(datetime.now(UTC).timestamp() * 1000),
			max_hours=self.settings.offline_max_hours,
			tolerance_minutes=self.settings.offline_clock_tolerance_minutes,
		)
		if record.prev_hash != self._last_hash():
			problems.append("A scan before this one from the same kiosk is missing or out of order.")
		return problems

	def _close(
		self,
		record: OfflineRecord,
		outcome: str,
		status: str,
		reason: str,
		payload: bytes | None = None,
		found=None,
		taken: datetime | None = None,
		similarity: float | None = None,
		checkin: str | None = None,
	) -> dict:
		"""Write the one log row for this scan. It commits, so a later failure cannot lose it."""
		verification_log.record(
			found.employee if found else None,
			outcome,
			self.device.name,
			method="Face",
			similarity=found.similarity if found else similarity,
			employee_checkin=checkin,
			detail=reason,
			local_id=record.local_id,
			record_hash=record_hash(payload) if payload else None,
			# Every scan from a sync carries a time, which is also how pausing a kiosk tells them from live attempts.
			recorded_at=taken or self._taken_at(record),
		)
		return self._result(record.local_id, status, None if status == ACCEPTED else reason)

	def _seen(self, local_id: str) -> bool:
		return bool(frappe.db.exists(LOG, {"device": self.device.name, "local_id": local_id}))

	def _last_hash(self) -> str:
		"""The hash of the newest scan already settled for this kiosk; empty if it has never synced."""
		return (
			frappe.db.get_value(
				LOG,
				{"device": self.device.name, "record_hash": ["is", "set"]},
				"record_hash",
				order_by="creation desc, name desc",
			)
			or ""
		)

	@staticmethod
	def _taken_at(record: OfflineRecord) -> datetime:
		utc = datetime.fromtimestamp(record.anchored_ms / 1000, UTC)
		return convert_utc_to_system_timezone(utc).replace(tzinfo=None, microsecond=0)

	@staticmethod
	def _result(local_id, status: str, reason: str | None = None) -> dict:
		return {"local_id": local_id, "status": status, "reason": reason}
