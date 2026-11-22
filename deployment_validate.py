from __future__ import annotations
import os, sys

def validate():
    if os.getenv("AYURSUTRA_ENV", "development").casefold() not in {"production", "prod"}: return []
    errors=[]
    for key in ("DATABASE_URL","AYURSUTRA_AUTH_JWT_SECRET","AYURSUTRA_AUTH_ALLOWED_ORIGIN","AYURFORM_ADMIN_EMAILS"):
        if not os.getenv(key): errors.append(f"Missing required production variable: {key}")
    if os.getenv("AYURFORM_DB_FALLBACK", "").casefold() == "sqlite": errors.append("SQLite fallback is forbidden in production")
    if os.getenv("AYURSUTRA_AUTH_COOKIE_SECURE", "1") != "1": errors.append("Secure cookies are required in production")
    if os.getenv("AYURSUTRA_ENABLE_DEV_COOKIE_TEST", "0") == "1": errors.append("Development cookie test must be disabled")
    return errors

def validate_or_raise():
    errors = validate()
    if errors:
        raise RuntimeError("Invalid production configuration: " + "; ".join(errors))
if __name__ == "__main__":
    errors=validate()
    if errors: print("\n".join(f"- {e}" for e in errors)); sys.exit(1)
    print("Configuration valid.")
