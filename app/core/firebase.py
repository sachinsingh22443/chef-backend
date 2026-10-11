
import json
import os

import firebase_admin
from firebase_admin import credentials


def initialize_firebase():
    if firebase_admin._apps:
        return firebase_admin.get_app()

    raw_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")

    if not raw_json:
        raise RuntimeError(
            "FIREBASE_SERVICE_ACCOUNT_JSON is not configured"
        )

    service_account = json.loads(raw_json)
    credential = credentials.Certificate(service_account)

    return firebase_admin.initialize_app(credential)
