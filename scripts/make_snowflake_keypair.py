"""Create an RSA key pair for the Snowflake service user.

The private key is written outside the repo (default: ~/.snowflake/f1_pipeline_key.p8) and is never
printed. Only the PUBLIC key body is printed, to paste into warehouse/01_account_setup.sql.
Refuses to overwrite an existing key.
"""

import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

default = Path.home() / ".snowflake" / "f1_pipeline_key.p8"
target = Path(sys.argv[1]) if len(sys.argv) > 1 else default
if target.exists():
    sys.exit(f"{target} already exists; not overwriting.")

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
target.parent.mkdir(parents=True, exist_ok=True)
target.write_bytes(key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
))
public = key.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
).decode()
print(f"Private key written to {target} (keep it out of the repo).")
print("Public key body to paste into the SQL:")
print("".join(public.strip().splitlines()[1:-1]))
