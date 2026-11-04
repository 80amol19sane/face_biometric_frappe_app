import hashlib
from dataclasses import dataclass

from face_biometric.core.device_signature import offline_payload

MAX_EMBEDDING_CHARS = 8000
# 1 January 2100 in milliseconds; anything later is not a real time and would overflow a date.
MAX_MS = 4_102_444_800_000


class OfflineRecordError(ValueError):
	"""The record is not shaped like a scan a kiosk would send."""


@dataclass(frozen=True)
class OfflineRecord:
	"""One face scan a kiosk saved while it had no connection, as it arrives at sync."""

	local_id: str
	prev_hash: str
	anchored_ms: int
	wall_ms: int
	boot_count: int
	anchor_boot_count: int
	embedding: str
	signature: str
	# What the person typed at the kiosk. A hint for HR only: it is not signed and never decides anything.
	claimed_employee: str = ""

	@classmethod
	def parse(cls, raw: object) -> "OfflineRecord":
		if not isinstance(raw, dict):
			raise OfflineRecordError("Each scan must be an object.")
		return cls(
			local_id=_text(raw, "local_id", 8, 64),
			prev_hash=_text(raw, "prev_hash", 0, 64),
			anchored_ms=_whole(raw, "anchored_ms", MAX_MS),
			wall_ms=_whole(raw, "wall_ms", MAX_MS),
			boot_count=_whole(raw, "boot_count"),
			anchor_boot_count=_whole(raw, "anchor_boot_count"),
			embedding=_text(raw, "embedding", 1, MAX_EMBEDDING_CHARS),
			signature=_text(raw, "signature", 1, 400),
			claimed_employee=_optional_text(raw, "claimed_employee", 140),
		)

	def payload(self, device: str, embedding_digest: str) -> bytes:
		return offline_payload(
			device,
			self.local_id,
			self.prev_hash,
			self.anchored_ms,
			self.wall_ms,
			self.boot_count,
			self.anchor_boot_count,
			embedding_digest,
		)


def record_hash(payload: bytes) -> str:
	"""The fingerprint the next scan from the same kiosk must quote as its `prev_hash`."""
	return hashlib.sha256(payload).hexdigest()


def batch_digest(hashes: list[str]) -> str:
	"""What the kiosk signs for a whole upload, so no scan can be added, dropped or reordered in transit."""
	return hashlib.sha256("|".join(hashes).encode()).hexdigest()


def _text(raw: dict, key: str, low: int, high: int) -> str:
	value = raw.get(key)
	if not isinstance(value, str) or not low <= len(value) <= high:
		raise OfflineRecordError(f"{key} is missing or the wrong length.")
	return value


def _optional_text(raw: dict, key: str, high: int) -> str:
	value = raw.get(key)
	if value is None:
		return ""
	if not isinstance(value, str) or len(value) > high:
		raise OfflineRecordError(f"{key} is the wrong length.")
	return value.strip()


def _whole(raw: dict, key: str, high: int = 2**31) -> int:
	value = raw.get(key)
	if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= high:
		raise OfflineRecordError(f"{key} must be a whole number.")
	return value
