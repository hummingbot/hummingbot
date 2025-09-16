"""
Base authentication class for web assistant.
Minimal implementation to support connector development.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class AuthBase(ABC):
    """
    Base class for authentication implementations.
    """
    
    def __init__(self):
        """Initialize the authentication base."""
        pass
    
    @abstractmethod
    def header_for_authentication(self) -> Dict[str, str]:
        """
        Generate authentication headers.
        
        Returns:
            Dictionary of authentication headers
        """
        pass
    
    @abstractmethod
    def get_auth_headers(self, 
                        method: str, 
                        url: str, 
                        data: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """
        Generate authentication headers for a specific request.
        
        Args:
            method: HTTP method
            url: Request URL
            data: Request data
            
        Returns:
            Dictionary of authentication headers
        """
        pass
    
    def validate_credentials(self) -> bool:
        """
        Validate authentication credentials.
        
        Returns:
            True if credentials are valid, False otherwise
        """
        return True
