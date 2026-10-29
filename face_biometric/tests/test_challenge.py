from frappe.tests import IntegrationTestCase

from face_biometric.core.challenge import ChallengeStore


class TestChallengeStore(IntegrationTestCase):
	def setUp(self):
		self.store = ChallengeStore(ttl_seconds=30)

	def test_a_nonce_can_be_spent_once(self):
		nonce = self.store.issue("device-a")
		self.assertTrue(self.store.consume("device-a", nonce))
		self.assertFalse(self.store.consume("device-a", nonce))

	def test_a_wrong_nonce_is_refused_and_burns_the_challenge(self):
		nonce = self.store.issue("device-a")
		self.assertFalse(self.store.consume("device-a", "guess"))
		self.assertFalse(self.store.consume("device-a", nonce))

	def test_nonces_do_not_cross_devices(self):
		nonce = self.store.issue("device-a")
		self.assertFalse(self.store.consume("device-b", nonce))

	def test_issuing_again_replaces_the_old_nonce(self):
		first = self.store.issue("device-a")
		second = self.store.issue("device-a")
		self.assertNotEqual(first, second)
		self.assertFalse(self.store.consume("device-a", first))

	def test_nothing_issued_means_nothing_to_spend(self):
		self.assertFalse(self.store.consume("device-never", "x"))
