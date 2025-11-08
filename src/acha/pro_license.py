"""
Pro License Verification System for ACHA.

Uses Ed25519 signatures for offline license validation.
No telemetry, no network calls.
"""

import base64
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Try to import PyNaCl for Ed25519 verification
try:
    import nacl.encoding
    import nacl.signing

    NACL_AVAILABLE = True
except ImportError:
    NACL_AVAILABLE = False


class LicenseError(Exception):
    """License validation error"""

    pass


class ProLicense:
    """Pro license validator using Ed25519 signatures"""

    # Fallback public key (base64-encoded Ed25519 public key)
    # In production, this would be your actual public key
    DEFAULT_PUBKEY_B64 = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="

    def __init__(self):
        """Initialize license validator"""
        self.pubkey_b64 = os.environ.get("ACHA_PRO_PUBKEY_B64", self.DEFAULT_PUBKEY_B64)
        self.license_data: dict | None = None
        self.is_valid = False
        self._load_license()

    def _load_license(self) -> None:
        """Load license from standard locations"""
        license_paths = [
            Path.home() / ".acha" / "license.json",
            Path("license.json"),
        ]

        for path in license_paths:
            if path.exists():
                try:
                    with open(path, encoding="utf-8") as f:
                        data = json.load(f)
                    if self._verify_license(data):
                        self.license_data = data
                        self.is_valid = True
                        return
                except Exception:
                    continue

        # No valid license found - running in Community mode
        self.is_valid = False

    def _verify_license(self, data: dict) -> bool:
        """Verify Ed25519 signature on license data"""
        if not NACL_AVAILABLE:
            # If PyNaCl not available, treat as community mode
            return False

        try:
            # Extract signature and payload
            signature_b64 = data.get("signature")
            payload = data.get("payload", {})

            if not signature_b64 or not payload:
                return False

            # Check expiration
            expires_at = payload.get("expires_at")
            if expires_at:
                expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if datetime.now(expiry.tzinfo) > expiry:
                    return False

            # Verify signature
            pubkey_bytes = base64.b64decode(self.pubkey_b64)
            verify_key = nacl.signing.VerifyKey(pubkey_bytes)

            # Canonical JSON for signing
            canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            signature_bytes = base64.b64decode(signature_b64)

            verify_key.verify(canonical_payload.encode("utf-8"), signature_bytes)
            return True

        except Exception:
            return False

    def require_pro(self, feature: str) -> None:
        """
        Require Pro license for a feature.
        Exits with code 2 and friendly message if unlicensed.
        """
        if not self.is_valid:
            print(
                f"\n⚠️  Pro Feature: {feature}\n",
                file=sys.stderr,
            )
            print(
                "This feature requires an ACHA Pro license.\n"
                "You're currently running in Community mode.\n",
                file=sys.stderr,
            )
            print("To unlock Pro features:", file=sys.stderr)
            print("  1. Obtain a license at: https://acha.example.com/pro", file=sys.stderr)
            print("  2. Place license.json in ~/.acha/ or your project root", file=sys.stderr)
            print("  3. Run this command again\n", file=sys.stderr)
            print("Community features (analyze, basic reports) remain free!\n", file=sys.stderr)
            sys.exit(2)

    def is_pro(self) -> bool:
        """Check if Pro license is active"""
        return self.is_valid

    def get_license_info(self) -> dict:
        """Get license metadata (safe for display)"""
        if not self.is_valid or not self.license_data:
            return {"mode": "community", "features": ["analyze", "json", "sarif"]}

        payload = self.license_data.get("payload", {})
        return {
            "mode": "pro",
            "licensee": payload.get("licensee", "Unknown"),
            "expires_at": payload.get("expires_at", "Never"),
            "features": [
                "analyze",
                "json",
                "sarif",
                "html",
                "fix",
                "apply",
                "baseline",
                "precommit",
                "parallel",
            ],
        }


# Global license instance
_license: ProLicense | None = None


def get_license() -> ProLicense:
    """Get global license instance"""
    global _license
    if _license is None:
        _license = ProLicense()
    return _license


def require_pro(feature: str) -> None:
    """Convenience function to require Pro license"""
    get_license().require_pro(feature)


def is_pro() -> bool:
    """Convenience function to check Pro status"""
    return get_license().is_pro()
