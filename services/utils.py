"""
Helper functions for the services layer
"""

import bcrypt # type: ignore


def verify_key(plain: str, hashed: bytes) -> bool:
    """
    Verifies a bcrypt key by matching the plaintext string against a hashed byte string.
    """
    return bcrypt.checkpw(plain.encode(), hashed)
