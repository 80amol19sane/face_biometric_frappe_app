import frappe

DEFAULTS = {
	"require_liveness": 1,
	"identify_margin": 0.05,
	"kiosk_return_seconds": 5,
	"pin_enabled": 1,
	"pin_min_length": 4,
	"pin_max_length": 6,
	"photo_retention_days": 30,
}


def execute():
	"""A Single doctype only applies field defaults when it is first created, so fill in the new ones."""
	singles = frappe.qb.DocType("Singles")
	stored = {
		row.field
		for row in frappe.qb.from_(singles)
		.select(singles.field)
		.where(singles.doctype == "Face Biometric Settings")
		.run(as_dict=True)
	}
	for field, value in DEFAULTS.items():
		if field not in stored:
			frappe.db.set_single_value("Face Biometric Settings", field, value)
