from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class ShiftStanding:
	"""How a punch sits against its shift: on time, within the grace window, late or an early exit.

	Grace follows HRMS: a late entry is only marked after start + grace, and an early exit
	only before end - grace. Pure on purpose, so the boundaries are testable without a database.
	"""

	log_type: str
	time: datetime
	shift_start: datetime
	shift_end: datetime
	late_grace_minutes: int = 0
	early_grace_minutes: int = 0

	def evaluate(self) -> dict:
		status, minutes = self._entry() if self.log_type == "IN" else self._exit()
		return {"status": status, "minutes": minutes}

	def _entry(self) -> tuple[str, int]:
		if self.time <= self.shift_start:
			return "On Time", 0
		late = self._minutes(self.time - self.shift_start)
		if late <= self.late_grace_minutes:
			return "Within Grace", late
		return "Late", late

	def _exit(self) -> tuple[str, int]:
		early = self._minutes(self.shift_end - self.time)
		if early > self.early_grace_minutes:
			return "Early Exit", early
		return "On Time", 0

	@staticmethod
	def _minutes(delta: timedelta) -> int:
		return int(delta.total_seconds() // 60)
