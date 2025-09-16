"""
Configuration helpers for Hummingbot client.
Minimal implementation to support connector development.
"""

from typing import Dict, Any, Optional


class ClientConfigAdapter:
    """
    Adapter for client configuration.
    Provides a simplified interface for accessing configuration values.
    """
    
    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        """
        Initialize the config adapter.
        
        Args:
            config_dict: Configuration dictionary
        """
        self._config = config_dict or {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
        """
        self._config[key] = value
    
    def update(self, config_dict: Dict[str, Any]) -> None:
        """
        Update configuration with new values.
        
        Args:
            config_dict: Dictionary of configuration updates
        """
        self._config.update(config_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.
        
        Returns:
            Configuration dictionary
        """
        return self._config.copy()
    
    @property
    def config(self) -> Dict[str, Any]:
        """Get the configuration dictionary."""
        return self._config.copy()


class ConfigVar:
    """
    Configuration variable definition.
    """
    
    def __init__(self, 
                 key: str, 
                 prompt: str, 
                 default: Any = None,
                 type_str: str = "str",
                 required: bool = True):
        """
        Initialize configuration variable.
        
        Args:
            key: Configuration key
            prompt: User prompt for this variable
            default: Default value
            type_str: Type string for validation
            required: Whether this variable is required
        """
        self.key = key
        self.prompt = prompt
        self.default = default
        self.type_str = type_str
        self.required = required
    
    def validate(self, value: Any) -> bool:
        """
        Validate a configuration value.
        
        Args:
            value: Value to validate
            
        Returns:
            True if valid, False otherwise
        """
        if self.required and value is None:
            return False
        
        # Basic type validation
        if self.type_str == "str" and value is not None:
            return isinstance(value, str)
        elif self.type_str == "int" and value is not None:
            try:
                int(value)
                return True
            except (ValueError, TypeError):
                return False
        elif self.type_str == "float" and value is not None:
            try:
                float(value)
                return True
            except (ValueError, TypeError):
                return False
        elif self.type_str == "bool" and value is not None:
            return isinstance(value, bool)
        
        return True


# Default configuration adapter
default_config_adapter = ClientConfigAdapter()
