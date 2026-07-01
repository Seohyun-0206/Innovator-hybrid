import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings


def _get_fernet() -> Fernet:
    if settings.CREDENTIAL_ENCRYPTION_KEY:
        key = settings.CREDENTIAL_ENCRYPTION_KEY.encode("utf-8")
    else:
        digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_value(value: str) -> str:
    if value == "":
        return ""
    return _get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(value: str) -> str:
    if value == "":
        return ""
    return _get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
