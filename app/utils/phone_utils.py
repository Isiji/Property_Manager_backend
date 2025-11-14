# app/utils/phone_utils.py
import re

def normalize_ke_phone(phone: str) -> str:
    """
    Normalize Kenyan phone numbers to E.164-like +2547XXXXXXXX.
    Accepts formats like: 0712345678, 712345678, +254712345678, 254712345678.
    Leaves other countries mostly untouched (simple heuristic).
    """
    if not phone:
        return phone

    p = re.sub(r"\D+", "", phone)  # strip non-digits

    # If it already has a +, keep it (after removing spaces):
    if phone.strip().startswith("+"):
        return "+" + p

    # Kenyan patterns:
    if p.startswith("254") and len(p) == 12 and p[3] == "7":
        return f"+{p}"
    if p.startswith("0") and len(p) == 10 and p[1] == "7":
        return "+254" + p[1:]
    if len(p) == 9 and p[0] == "7":
        return "+254" + p  # e.g. 712345678

    # fallback: just slap + if it had no +
    return "+" + p if not phone.startswith("+") else phone
