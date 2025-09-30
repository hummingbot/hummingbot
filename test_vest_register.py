#!/usr/bin/env python3
"""
Vest API Registration Test Script
Based on official Vest API documentation: https://docs.vestmarkets.com/vest-api#authentication

This script demonstrates proper API key registration for the Vest trading platform.
"""

import json
import logging
import secrets
import time
from typing import Dict, Tuple

import requests
from eth_account import Account
from eth_account.messages import encode_typed_data

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration - Try original documented URLs with corrected signature method
VEST_PRODUCTION_URL = "https://server-prod.hz.vestmarkets.com/v2"
VEST_DEVELOPMENT_URL = "https://server-dev.hz.vestmarkets.com/v2"
VEST_PRODUCTION_CONTRACT = "0x919386306C47b2Fe1036e3B4F7C40D22D2461a23"  # Production VestRouterV2
VEST_DEVELOPMENT_CONTRACT = "0x8E4D87AEf4AC4D5415C35A12319013e34223825B"  # Development VestRouterV2
PRIMARY_PRIVATE_KEY = ""  # Replace with your actual private key


class VestAPIRegistration:
    """Handle Vest API key registration process"""

    def __init__(self, primary_private_key: str, use_production: bool = False):
        """
        Initialize with primary account private key

        Args:
            primary_private_key: Private key for the primary account (must start with 0x)
            use_production: Whether to use production endpoint (default: False for testing)
        """
        if not primary_private_key.startswith('0x'):
            raise ValueError("Private key must start with '0x'")

        self.primary_account = Account.from_key(primary_private_key)
        self.primary_addr = self.primary_account.address.lower()
        self.use_production = use_production
        self.base_url = VEST_PRODUCTION_URL if use_production else VEST_DEVELOPMENT_URL
        self.contract_address = VEST_PRODUCTION_CONTRACT if use_production else VEST_DEVELOPMENT_CONTRACT

        logger.info(f"Primary address: {self.primary_addr}")
        logger.info(f"Using {'production' if use_production else 'development'} endpoint")
        logger.info(f"Contract address: {self.contract_address}")

    def generate_signing_key(self) -> Tuple[str, str]:
        """Generate a new signing key pair"""
        priv = secrets.token_hex(32)
        signing_private_key = "0x" + priv
        signing_account = Account.from_key(signing_private_key)
        signing_addr = signing_account.address.lower()

        logger.info(f"Generated signing address: {signing_addr}")
        return signing_private_key, signing_addr

    def create_eip712_signature(self, signing_addr: str, expiry_time: int) -> str:
        """
        Create EIP-712 signature for registration - Based on working sample code

        Args:
            signing_addr: Signing address to approve
            expiry_time: Expiry time in milliseconds

        Returns:
            Hex signature string
        """
        logger.info("Creating EIP-712 signature using working sample method...")

        # EIP-712 domain data - exact format from working sample
        domain = {
            "name": "VestRouterV2",
            "version": "0.0.1",
            "verifyingContract": self.contract_address
        }

        # Types definition for SignerProof
        types = {
            "SignerProof": [
                {"name": "approvedSigner", "type": "address"},
                {"name": "signerExpiry", "type": "uint256"}
            ]
        }

        # Message data - use lowercase addresses as in sample
        proof_args = {
            "approvedSigner": signing_addr.lower(),
            "signerExpiry": expiry_time
        }

        logger.info(f"Domain: {domain}")
        logger.info(f"Proof args: {proof_args}")

        # Create signable message and sign
        signable_msg = encode_typed_data(domain, types, proof_args)
        signature = Account.sign_message(signable_msg, self.primary_account.key).signature.hex()

        logger.info("EIP-712 signature created successfully")
        logger.info(f"Signature: {signature[:20]}...")
        logger.info(f"Signature length: {len(signature)} characters")
        return signature

    def register_api_key(self, expiry_days: int = 7) -> Dict:
        """
        Register for API key with Vest

        Args:
            expiry_days: Number of days until signing key expires

        Returns:
            Registration response containing apiKey and accGroup
        """
        try:
            # Generate signing key
            signing_private_key, signing_addr = self.generate_signing_key()

            # Calculate expiry time (current time + expiry_days in milliseconds)
            expiry_time = int(time.time() * 1000) + (expiry_days * 24 * 3600 * 1000)

            # Create signature
            signature = self.create_eip712_signature(signing_addr, expiry_time)

            # Prepare registration payload
            registration_data = {
                "primaryAddr": self.primary_addr,
                "signingAddr": signing_addr,
                "signature": signature,
                "expiryTime": expiry_time,
                "networkType": 0  # Ethereum mainnet
            }

            # Send registration request with proper headers as in sample
            url = f"{self.base_url}/register"
            logger.info(f"Sending registration request to: {url}")

            print(f"Registration data: {json.dumps(registration_data, indent=2)}")

            # Headers based on working sample script
            headers = {
                "Content-Type": "application/json",
                "Origin": "http://localhost:3000",
                "xrestservermm": "restserver0",  # ACC_GRP = 0 in sample
            }

            response = requests.post(
                url,
                json=registration_data,
                headers=headers,
                timeout=10
            )

            logger.info(f"Response status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                logger.info("✅ Registration successful!")
                logger.info(f"API Key: {result.get('apiKey', 'N/A')}")
                logger.info(f"Account Group: {result.get('accGroup', 'N/A')}")

                # Store signing key for future use
                result['signingPrivateKey'] = signing_private_key
                result['signingAddr'] = signing_addr
                result['expiryTime'] = expiry_time

                return result
            else:
                logger.error(f"❌ Registration failed: {response.text}")
                return {"error": response.text, "status_code": response.status_code}

        except Exception as e:
            logger.error(f"❌ Registration error: {str(e)}")
            return {"error": str(e)}

    def save_credentials(self, credentials: Dict, filename: str = "vest_credentials.json"):
        """Save API credentials to file"""
        try:
            with open(filename, 'w') as f:
                json.dump(credentials, f, indent=2)
            logger.info(f"✅ Credentials saved to {filename}")
        except Exception as e:
            logger.error(f"❌ Failed to save credentials: {str(e)}")


def main():
    """Main test function"""
    # ⚠️  IMPORTANT: Replace with your actual private key
    # This should be the private key for your primary account that holds funds

    if PRIMARY_PRIVATE_KEY == "0x...":
        logger.error("❌ Please set your PRIMARY_PRIVATE_KEY before running this script")
        return

    try:
        # Initialize registration handler (use production endpoint)
        registrar = VestAPIRegistration(PRIMARY_PRIVATE_KEY, use_production=True)

        # Attempt registration
        logger.info("🚀 Starting Vest API registration process...")
        result = registrar.register_api_key(expiry_days=7)

        if "apiKey" in result:
            logger.info("🎉 Registration completed successfully!")

            # Save credentials for future use
            registrar.save_credentials(result)

            # Display important information
            print("\n" + "=" * 50)
            print("📋 REGISTRATION SUMMARY")
            print("=" * 50)
            print(f"API Key: {result['apiKey']}")
            print(f"Primary Address: {registrar.primary_addr}")
            print(f"Signing Address: {result['signingAddr']}")
            print(f"Private Key: {PRIMARY_PRIVATE_KEY}")

            print(f"Account Group: {result['accGroup']}")
            print(f"Expiry Time: {result['expiryTime']} ({time.ctime(result['expiryTime']/1000)})")
            print("=" * 50)

            # Test API key
            test_api_key(result['apiKey'], registrar.base_url)

        else:
            logger.error("❌ Registration failed. Check the error details above.")

    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}")


def test_api_key(api_key: str, base_url: str):
    """Test the obtained API key"""
    try:
        logger.info("🧪 Testing API key with account info endpoint...")

        headers = {
            'X-API-KEY': api_key,
            'Content-Type': 'application/json'
        }

        # Test with account info endpoint
        response = requests.get(f"{base_url}/account", headers=headers, timeout=10)

        if response.status_code == 200:
            logger.info("✅ API key is working correctly!")
            logger.info(f"Account info: {response.json()}")
        else:
            logger.warning(f"⚠️  API key test returned status {response.status_code}: {response.text}")

    except Exception as e:
        logger.warning(f"⚠️  API key test failed: {str(e)}")


if __name__ == "__main__":
    main()
