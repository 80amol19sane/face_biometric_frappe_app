import frappe


def execute():
	"""Devices registered before kiosks existed all belong to one employee's own phone."""
	device = frappe.qb.DocType("Biometric Device")
	(
		frappe.qb.update(device)
		.set(device.device_kind, "Personal")
		.where(device.device_kind.isnull() | (device.device_kind == ""))
		.run()
	)
