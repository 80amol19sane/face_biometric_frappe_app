import frappe
from frappe.utils import add_days, now_datetime

from face_biometric.face_biometric.doctype.face_biometric_settings.face_biometric_settings import get_settings

PROOF_DOCTYPES = ("Employee Checkin", "Face Verification Log")


def delete_expired_proof_photos():
	"""Daily. Proof photos are personal data: keep them only as long as HR needs to review a disputed punch."""
	days = get_settings().photo_retention_days
	if not days or days < 1:
		return
	cutoff = add_days(now_datetime(), -days)
	expired = frappe.get_all(
		"File",
		{
			"attached_to_doctype": ["in", PROOF_DOCTYPES],
			"file_name": ["like", "proof-%"],
			"creation": ["<", cutoff],
		},
		pluck="name",
	)
	for name in expired:
		frappe.delete_doc("File", name, ignore_permissions=True, force=True)
	if expired:
		frappe.db.commit()
