from face_biometric.patches.single_defaults import fill_missing


def execute():
	fill_missing("Face Biometric Settings", {"offline_review_floor": 0.4})
