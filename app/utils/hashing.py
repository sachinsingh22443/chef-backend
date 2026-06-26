from pwdlib import PasswordHash
import hashlib

password_hash = PasswordHash.recommended()


def hash_password(password: str):
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str):
    return password_hash.verify(password, hashed_password)


def hash_refresh_token(token: str):
    return hashlib.sha256(token.encode()).hexdigest()