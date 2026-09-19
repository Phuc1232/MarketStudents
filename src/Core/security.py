# hash mk
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

# khoi tao doi tuong cua class PasswordHash
password_context=PasswordHash((Argon2Hasher(),))

def get_password_hashed(password: str):
    return password_context.hash(password)

def verify_password(plan_password, hashed_password):
    return password_context.verify(plan_password, hashed_password)