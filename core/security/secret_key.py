import base64
from typing import Optional

from cryptography.fernet import Fernet


class SecretKey:
    def __init__(self, key: Optional[bytes] = None):
        self.key: Optional[bytes] = key

    @staticmethod
    def create() -> bytes:
        return Fernet.generate_key()

    def encrypt(self, payload: bytes, valid_base64: bool = True) -> bytes:
        self.key = SecretKey.create()

        func = Fernet(self.key)
        data = func.encrypt(payload)

        if valid_base64:
            data = base64.b64encode(data, b"-_").decode().replace("=", "").encode()

        return data
