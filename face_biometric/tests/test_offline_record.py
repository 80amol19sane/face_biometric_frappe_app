from unittest import TestCase

from face_biometric.core.device_signature import offline_payload
from face_biometric.core.offline_record import OfflineRecord, OfflineRecordError, batch_digest, record_hash

RAW = {
	"local_id": "a1b2c3d4-0001",
	"prev_hash": "",
	"anchored_ms": 1_800_000_000_000,
	"wall_ms": 1_800_000_001_000,
	"boot_count": 7,
	"anchor_boot_count": 7,
	"embedding": "AAAA",
	"signature": "c2ln",
}


class TestOfflineRecord(TestCase):
	def test_a_well_formed_scan_parses(self):
		record = OfflineRecord.parse(RAW)
		self.assertEqual(record.local_id, "a1b2c3d4-0001")
		self.assertEqual(record.boot_count, 7)

	def test_the_payload_is_versioned_and_ordered(self):
		payload = OfflineRecord.parse(RAW).payload("BDEV-00004", "ab12")
		self.assertEqual(payload, b"fb3|BDEV-00004|a1b2c3d4-0001||1800000000000|1800000001000|7|7|ab12")
		self.assertEqual(
			payload,
			offline_payload(
				"BDEV-00004", "a1b2c3d4-0001", "", 1_800_000_000_000, 1_800_000_001_000, 7, 7, "ab12"
			),
		)

	def test_it_cannot_be_confused_with_an_online_payload(self):
		self.assertTrue(OfflineRecord.parse(RAW).payload("D", "x").startswith(b"fb3|"))

	def test_bad_shapes_are_refused(self):
		for change in (
			{"local_id": "short"},
			{"anchored_ms": "1800000000000"},
			{"anchored_ms": -1},
			{"anchored_ms": 10**15},
			{"boot_count": 2**40},
			{"boot_count": True},
			{"embedding": ""},
			{"signature": 5},
		):
			with self.assertRaises(OfflineRecordError, msg=str(change)):
				OfflineRecord.parse({**RAW, **change})
		with self.assertRaises(OfflineRecordError):
			OfflineRecord.parse("not an object")

	def test_a_missing_field_is_refused(self):
		without = {k: v for k, v in RAW.items() if k != "wall_ms"}
		with self.assertRaises(OfflineRecordError):
			OfflineRecord.parse(without)

	def test_the_hash_changes_with_any_field(self):
		base = record_hash(OfflineRecord.parse(RAW).payload("D", "x"))
		other = record_hash(OfflineRecord.parse({**RAW, "wall_ms": RAW["wall_ms"] + 1}).payload("D", "x"))
		self.assertNotEqual(base, other)
		self.assertEqual(len(base), 64)

	def test_the_batch_digest_depends_on_order_and_membership(self):
		self.assertNotEqual(batch_digest(["a", "b"]), batch_digest(["b", "a"]))
		self.assertNotEqual(batch_digest(["a", "b"]), batch_digest(["a"]))
