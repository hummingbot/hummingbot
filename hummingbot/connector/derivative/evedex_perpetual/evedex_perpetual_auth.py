import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

import aiohttp
from eth_account import Account
from eth_account.messages import encode_defunct, encode_typed_data

from .evedex_perpetual_constants import ENDPOINTS

logger = logging.getLogger(__name__)


@dataclass
class TokenBundle:
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[float] = None
    user_exchange_id: Optional[str] = None
    
    def is_valid(self, buffer_seconds: int = 60) -> bool:
        if not self.access_token:
            return False
        
        if self.expires_at is None:
            return True
        
        current_time = time.time()
        return self.expires_at > (current_time + buffer_seconds)
    
    def clear(self):
        self.access_token = None
        self.refresh_token = None
        self.expires_at = None
        self.user_exchange_id = None


class EvedexPerpetualAuth:
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        wallet_address: Optional[str] = None,
        auth_base_url: Optional[str] = None,
    ):
        self._api_key = api_key
        self._api_secret = api_secret
        self._wallet_address = wallet_address
        self._auth_base_url = (auth_base_url or "").rstrip("/")
        self._wallet_signer = None
        
        if self._wallet_address and self._api_secret:
            try:
                self._wallet_signer = Account.from_key(self._api_secret)
                if self._wallet_signer.address.lower() != self._wallet_address.lower():
                    logger.warning(
                        "Provided wallet address %s does not match derived address %s",
                        self._wallet_address,
                        self._wallet_signer.address,
                    )
            except Exception as e:
                logger.error(f"Failed to initialize wallet signer: {e}")
                self._wallet_signer = None
        
        self._tokens = TokenBundle()
        self._refresh_lock = asyncio.Lock()
        self._last_refresh_attempt = 0.0
        self._min_refresh_interval = 5.0
        
    @property
    def has_credentials(self) -> bool:
        return bool(self._api_key or self._wallet_address)
    
    @property
    def user_exchange_id(self) -> Optional[str]:
        return self._tokens.user_exchange_id
    
    async def ensure_authenticated(self, session: Optional[aiohttp.ClientSession] = None) -> bool:
        if self._api_key and not self._wallet_address:
            return True
        
        if self._tokens.is_valid():
            return True
        
        if session is None:
            return False
        
        async with self._refresh_lock:
            if self._tokens.is_valid():
                return True
            
            now = time.time()
            if now - self._last_refresh_attempt < self._min_refresh_interval:
                logger.warning("Skipping token refresh due to rate limit")
                return False
            
            self._last_refresh_attempt = now
            
            if self._tokens.refresh_token:
                if await self._refresh_token(session):
                    return True
            
            if self._wallet_address:
                return await self._authenticate_siwe(session)
            
            return False
    
    async def _authenticate_siwe(self, session: aiohttp.ClientSession) -> bool:
        if not self._wallet_address:
            logger.error("Wallet address is required for SIWE authentication")
            return False
        
        if self._wallet_signer is None:
            logger.error("Wallet private key is required for SIWE authentication")
            return False
        
        try:
            nonce_data = await self._request_nonce(session)
        except Exception as e:
            logger.error(f"Failed to request SIWE nonce: {e}")
            return False
        
        try:
            signature, payload = self._build_siwe_auth_payload(nonce_data)
        except Exception as e:
            logger.error(f"Failed to sign SIWE message: {e}")
            return False
        
        payload["signature"] = signature
        
        url = f"{self._auth_base_url}{ENDPOINTS['auth_signup']}"
        headers = {"Content-Type": "application/json"}
        
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    self._update_tokens(data)
                    logger.info("Successfully authenticated via SIWE")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(
                        "SIWE authentication failed with status %s: %s",
                        response.status,
                        error_text,
                    )
                    return False
        except Exception as e:
            logger.error(f"SIWE authentication request error: {e}")
            return False
    
    async def _refresh_token(self, session: aiohttp.ClientSession) -> bool:
        if not self._tokens.refresh_token:
            return False
        
        try:
            url = f"{self._auth_base_url}{ENDPOINTS['auth_refresh']}"
            headers = {
                "Authorization": f"Bearer {self._tokens.refresh_token}",
                "Content-Type": "application/json",
            }
            
            async with session.post(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    self._update_tokens(data)
                    logger.info("Successfully refreshed access token")
                    return True
                else:
                    logger.warning(
                        f"Token refresh failed with status {response.status}"
                    )
                    self._tokens.clear()
                    return False
                    
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            self._tokens.clear()
            return False
    
    def _update_tokens(self, auth_response: Dict) -> None:
        self._tokens.access_token = auth_response.get("accessToken")
        self._tokens.refresh_token = auth_response.get("refreshToken")
        self._tokens.user_exchange_id = auth_response.get("userExchangeId")
        
        expires_in = auth_response.get("expiresIn")
        if expires_in:
            self._tokens.expires_at = time.time() + float(expires_in)
        else:
            self._tokens.expires_at = time.time() + 3600
        
        logger.debug(
            f"Updated tokens: expires_at={self._tokens.expires_at}, "
            f"user_id={self._tokens.user_exchange_id}"
        )
    
    def get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        
        if self._api_key:
            headers["x-api-key"] = self._api_key
        
        if self._tokens.access_token:
            headers["Authorization"] = f"Bearer {self._tokens.access_token}"
        
        return headers
    
    def get_ws_auth_payload(self) -> Optional[Dict]:
        if not self._tokens.access_token:
            return None
        
        return {
            "token": self._tokens.access_token,
        }
    
    def invalidate_tokens(self) -> None:
        logger.info("Invalidating authentication tokens")
        self._tokens.clear()
    
    async def _request_nonce(self, session: aiohttp.ClientSession) -> Dict:
        url = f"{self._auth_base_url}{ENDPOINTS['auth_nonce']}"
        payload = {
            "walletAddress": self._wallet_address,
        }
        headers = {"Content-Type": "application/json"}
        
        async with session.post(url, json=payload, headers=headers) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(
                    f"Nonce request failed with status {response.status}: {error_text}"
                )
            return await response.json()
    
    def _build_siwe_auth_payload(self, nonce_response: Dict) -> Tuple[str, Dict]:
        if self._wallet_signer is None:
            raise ValueError("Wallet signer not initialized")
        
        message = nonce_response.get("message")
        typed_data = nonce_response.get("typedData")
        nonce = nonce_response.get("nonce")
        chain_id = nonce_response.get("chainId")
        
        payload = {
            "walletAddress": self._wallet_address,
        }
        
        if typed_data:
            encoded = encode_typed_data(full_message=typed_data)
            signed = self._wallet_signer.sign_message(encoded)
            payload["typedData"] = typed_data
        else:
            if not message:
                message = self._build_default_siwe_message(nonce, chain_id)
            encoded = encode_defunct(text=message)
            signed = self._wallet_signer.sign_message(encoded)
            payload["message"] = message
        
        if nonce:
            payload["nonce"] = nonce
        if chain_id:
            payload["chainId"] = chain_id
        
        for key in ("issuedAt", "expirationTime", "notBefore", "requestId", "resources"):
            if key in nonce_response and nonce_response[key] is not None:
                payload[key] = nonce_response[key]
        
        signature = signed.signature.hex()
        return signature, payload
    
    def _build_default_siwe_message(self, nonce: Optional[str], chain_id: Optional[int]) -> str:
        domain = urlparse(self._auth_base_url).hostname or "evedex.tech"
        uri = self._auth_base_url or f"https://{domain}"
        issued_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        chain_id_value = chain_id or 1
        nonce_value = nonce or ""
        
        message = (
            f"{domain} wants you to sign in with your Ethereum account:\n"
            f"{self._wallet_address}\n\n"
            "Sign in to Evedex Perpetual\n\n"
            f"URI: {uri}\n"
            "Version: 1\n"
            f"Chain ID: {chain_id_value}\n"
            f"Nonce: {nonce_value}\n"
            f"Issued At: {issued_at}"
        )
        return message
