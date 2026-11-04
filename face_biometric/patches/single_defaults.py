import frappe


def fill_missing(doctype: str, defaults: dict):
	"""A Single doctype only applies field defaults when it is first created, so fill in the new ones."""
	singles = frappe.qb.DocType("Singles")
	stored = {
		row.field
		for row in frappe.qb.from_(singles)
		.select(singles.field)
		.where(singles.doctype == doctype)
		.run(as_dict=True)
	}
	for field, value in defaults.items():
		if field not in stored:
			frappe.db.set_single_value(doctype, field, value)
