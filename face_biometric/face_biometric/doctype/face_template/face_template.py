import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime
from frappe.utils.password import decrypt, encrypt

from face_biometric.core.embedding import Embedding
from face_biometric.face_biometric.doctype.face_biometric_settings.face_biometric_settings import get_settings


class FaceTemplate(Document):
	def validate(self):
		if self.status == "Active":
			self.require_embedding()
			self.require_approval()

	@frappe.whitelist(methods=["POST"])
	def approve(self):
		"""HR confirms the face belongs to this employee. Nobody approves their own face."""
		frappe.has_permission(self.doctype, "write", self, throw=True)
		if frappe.db.get_value("Employee", {"user_id": frappe.session.user}) == self.employee:
			frappe.throw(_("You cannot approve your own face."))
		self.status = "Active"
		self.approved_by = frappe.session.user
		self.approved_on = now_datetime()
		self.save()

	@frappe.whitelist(methods=["POST"])
	def revoke(self):
		frappe.has_permission(self.doctype, "write", self, throw=True)
		self.status = "Revoked"
		self.save()

	def store(self, embedding: Embedding, model_version: str):
		"""Keep the embedding encrypted at rest. Raw vectors never sit in the database."""
		self.embedding = encrypt(embedding.encoded)
		self.dimensions = embedding.dimensions
		self.model_version = model_version

	def load(self) -> Embedding:
		return Embedding(decrypt(self.embedding))

	def require_embedding(self):
		if not self.embedding:
			frappe.throw(_("An active template needs an embedding."))

	def require_approval(self):
		if get_settings().require_enrolment_approval and not self.approved_by:
			frappe.throw(_("A face must be approved by HR before it can be used."))
