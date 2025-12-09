"""
Password hashing and verification utilities.

Uses bcrypt for secure password hashing with a work factor of 12.
"""

import bcrypt

# Work factor for bcrypt (number of rounds)
BCRYPT_WORK_FACTOR = 12


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: The plain-text password to hash

    Returns:
        The hashed password as a string
    """
    # Generate salt and hash the password
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=BCRYPT_WORK_FACTOR)
    hashed = bcrypt.hashpw(password_bytes, salt)

    # Return as string for database storage
    return hashed.decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        password: The plain-text password to verify
        password_hash: The hashed password to compare against

    Returns:
        True if the password matches, False otherwise
    """
    try:
        password_bytes = password.encode('utf-8')
        hash_bytes = password_hash.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception:
        # If there's any error in verification, return False
        return False
