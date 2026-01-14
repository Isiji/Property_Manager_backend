import re
from typing import Optional

def normalize_ke_phone(raw: str) -> Optional[str]:
    """
    Normalize Kenyan mobile numbers to E.164 format: +254XXXXXXXXX (9 digits after 254)

    Accepts:
      - 07XXXXXXXX / 01XXXXXXXX
      - 7XXXXXXXX / 1XXXXXXXX
      - 2547XXXXXXXX / 2541XXXXXXXX
      - +2547XXXXXXXX / +2541XXXXXXXX
      - With spaces, hyphens, parentheses

    Returns:
      - "+2547XXXXXXXX" or "+2541XXXXXXXX" if valid
      - None if invalid
    """
    if raw is None:
        return None

    s = str(raw).strip()
    if not s:
        return None

    # Remove spaces, hyphens, parentheses, etc.
    s = re.sub(r"[^\d+]", "", s)

    # Keep only one leading '+', if any
    if s.count("+") > 1:
        return None
    if "+" in s and not s.startswith("+"):
        return None

    # Strip leading '+'
    if s.startswith("+"):
        s = s[1:]

    # Now s should be digits only
    if not s.isdigit():
        return None

    # Handle common Kenyan patterns
    # 07XXXXXXXX or 01XXXXXXXX (10 digits, starts with 0)
    if len(s) == 10 and s.startswith("0") and s[1] in ("7", "1"):
        return "+254" + s[1:]  # drop leading 0

    # 7XXXXXXXX or 1XXXXXXXX (9 digits)
    if len(s) == 9 and s[0] in ("7", "1"):
        return "+254" + s

    # 2547XXXXXXXX or 2541XXXXXXXX (12 digits)
    if len(s) == 12 and s.startswith("254") and s[3] in ("7", "1"):
        return "+" + s

    # Anything else is not a valid Kenyan mobile number format
    return None
