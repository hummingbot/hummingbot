#!/usr/bin/env python
import os
from typing import TYPE_CHECKING, Any, List, Optional

from hummingbot.client.command.gateway_api_manager import begin_placeholder_mode
from hummingbot.core.gateway.gateway_status_monitor import GatewayStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.gateway_config_utils import build_config_dict_display

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


def ensure_gateway_online(func):
    def wrapper(self, *args, **kwargs):
        if self._gateway_monitor.gateway_status is GatewayStatus.OFFLINE:
            self.logger().error("Gateway is offline")
            return
        return func(self, *args, **kwargs)
    return wrapper


class GatewayConfigCommand:
    """Commands for managing gateway configuration."""

    @ensure_gateway_online
    def gateway_config(self, namespace: str = None, action: str = None, args: List[str] = None):
        """
        Gateway configuration management.
        Usage:
            gateway config [namespace]                       - Show configuration for namespace
            gateway config <namespace> update                 - Update configuration (interactive)
            gateway config <namespace> update <path> <value>  - Update configuration (direct)
        """
        if args is None:
            args = []

        if namespace is None:
            # Show help when no namespace is provided
            self.notify("\nUsage:")
            self.notify("  gateway config [namespace]                       - Show configuration")
            self.notify("  gateway config <namespace> update                 - Update configuration (interactive)")
            self.notify("  gateway config <namespace> update <path> <value>  - Update configuration (direct)")
            self.notify("\nExamples:")
            self.notify("  gateway config ethereum-mainnet")
            self.notify("  gateway config uniswap")
            self.notify("  gateway config ethereum-mainnet update")
            self.notify("  gateway config solana-mainnet update nodeURL https://api.mainnet-beta.solana.com")
        elif action is None:
            # Format: gateway config <namespace>
            # Show configuration for the specified namespace
            safe_ensure_future(
                GatewayConfigCommand._show_gateway_configuration(self, namespace=namespace),
                loop=self.ev_loop
            )
        elif action == "update":
            if len(args) >= 2:
                # Non-interactive mode: gateway config <namespace> update <path> <value>
                path = args[0]
                # Join remaining args as the value (in case value contains spaces)
                value = " ".join(args[1:])
                safe_ensure_future(
                    GatewayConfigCommand._update_gateway_configuration_direct(self, namespace, path, value),
                    loop=self.ev_loop
                )
            else:
                # Interactive mode: gateway config <namespace> update
                safe_ensure_future(
                    GatewayConfigCommand._update_gateway_configuration_interactive(self, namespace),
                    loop=self.ev_loop
                )
        else:
            # If action is not "update", it might be a namespace typo
            self.notify(f"\nError: Invalid action '{action}'. Use 'update' to modify configuration.")
            self.notify("\nUsage:")
            self.notify("  gateway config <namespace>                       - Show configuration")
            self.notify("  gateway config <namespace> update                 - Update configuration (interactive)")
            self.notify("  gateway config <namespace> update <path> <value>  - Update configuration (direct)")

    async def _show_gateway_configuration(
        self,  # type: HummingbotApplication
        namespace: Optional[str] = None,
    ):
        """Show gateway configuration for a namespace."""
        host = self.client_config_map.gateway.gateway_api_host
        port = self.client_config_map.gateway.gateway_api_port
        try:
            config_dict = await self._get_gateway_instance().get_configuration(namespace=namespace)
            # Format the title
            title_parts = ["Gateway Configuration"]
            if namespace:
                title_parts.append(f"namespace: {namespace}")
            title = f"\n{' - '.join(title_parts)}:"

            self.notify(title)
            lines = []
            build_config_dict_display(lines, config_dict)
            self.notify("\n".join(lines))

        except Exception:
            remote_host = ':'.join([host, port])
            self.notify(f"\nError: Connection to Gateway {remote_host} failed")

    async def _update_gateway_configuration(
        self,  # type: HummingbotApplication
        namespace: str,
        key: str,
        value: Any
    ):
        """Update a single gateway configuration value."""
        try:
            response = await self._get_gateway_instance().update_config(
                namespace=namespace,
                path=key,
                value=value
            )
            self.notify(response["message"])
        except Exception:
            self.notify(
                "\nError: Gateway configuration update failed. See log file for more details."
            )

    async def _update_gateway_configuration_direct(
        self,  # type: HummingbotApplication
        namespace: str,
        path: str,
        value: str
    ):
        """Direct mode for gateway config update with validation."""
        try:
            # Get the current configuration to validate the path
            config_dict = await self._get_gateway_instance().get_configuration(namespace=namespace)

            if not config_dict:
                self.notify(f"No configuration found for namespace: {namespace}")
                return

            # Get available config keys
            config_keys = list(config_dict.keys())

            # Validate the path
            if path not in config_keys:
                self.notify(f"\nError: Invalid configuration path '{path}'")
                self.notify(f"Valid paths are: {', '.join(config_keys)}")
                return

            # Get current value for type validation
            current_value = config_dict.get(path)
            self.notify(f"\nUpdating {namespace}.{path}")
            self.notify(f"Current value: {current_value}")
            self.notify(f"New value: {value}")

            # Validate the value based on the current value type
            validated_value = await GatewayConfigCommand._validate_config_value(
                self,
                path,
                value,
                current_value,
                namespace
            )

            if validated_value is None:
                return

            # Update the configuration
            await GatewayConfigCommand._update_gateway_configuration(
                self,
                namespace,
                path,
                validated_value
            )

        except Exception as e:
            self.notify(f"Error updating configuration: {str(e)}")

    async def _update_gateway_configuration_interactive(
        self,  # type: HummingbotApplication
        namespace: str
    ):
        """Interactive mode for gateway config update with path validation."""
        try:
            # First get the current configuration to show available paths
            config_dict = await self._get_gateway_instance().get_configuration(namespace=namespace)

            if not config_dict:
                self.notify(f"No configuration found for namespace: {namespace}")
                return

            # Display current configuration
            self.notify(f"\nCurrent configuration for {namespace}:")
            lines = []
            build_config_dict_display(lines, config_dict)
            self.notify("\n".join(lines))

            # Get available config keys
            config_keys = list(config_dict.keys())

            # Enter interactive mode
            with begin_placeholder_mode(self):
                try:
                    # Update completer's config path options
                    if hasattr(self.app.input_field.completer, '_gateway_config_path_options'):
                        self.app.input_field.completer._gateway_config_path_options = config_keys

                    # Loop to allow retry on invalid path
                    while True:
                        # Prompt for path
                        self.notify(f"\nAvailable configuration paths: {', '.join(config_keys)}")
                        path = await self.app.prompt(prompt="Enter configuration path (or 'exit' to cancel): ")

                        if self.app.to_stop_config or not path or path.lower() == 'exit':
                            self.notify("Configuration update cancelled")
                            return

                        # Validate the path
                        if path not in config_keys:
                            self.notify(f"\nError: Invalid configuration path '{path}'")
                            self.notify(f"Valid paths are: {', '.join(config_keys)}")
                            self.notify("Please try again.")
                            continue  # Allow retry

                        # Valid path, break the loop
                        break

                    # Show current value
                    current_value = config_dict.get(path, "Not found")
                    self.notify(f"\nCurrent value for '{path}': {current_value}")

                    # Loop to allow retry on invalid value
                    while True:
                        # Prompt for new value
                        value = await self.app.prompt(prompt="Enter new value (or 'exit' to cancel): ")

                        if self.app.to_stop_config or not value or value.lower() == 'exit':
                            self.notify("Configuration update cancelled")
                            return

                        # Validate the value based on the current value type
                        validated_value = await GatewayConfigCommand._validate_config_value(
                            self,
                            path,
                            value,
                            current_value,
                            namespace
                        )

                        if validated_value is None:
                            self.notify("Please try again.")
                            continue  # Allow retry

                        # Valid value, break the loop
                        break

                    # Update the configuration
                    await GatewayConfigCommand._update_gateway_configuration(
                        self,
                        namespace,
                        path,
                        validated_value
                    )

                finally:
                    self.placeholder_mode = False
                    self.app.hide_input = False
                    self.app.change_prompt(prompt=">>> ")

        except Exception as e:
            self.notify(f"Error in interactive config update: {str(e)}")

    async def _validate_config_value(
        self,  # type: HummingbotApplication
        path: str,
        value: str,
        current_value: Any,
        namespace: str = None
    ) -> Optional[Any]:
        """
        Validate and convert the config value based on the current value type.
        Also performs special validation for path values and network values.
        """
        try:
            # Special validation for path-like configuration keys
            path_keywords = ['path', 'dir', 'directory', 'folder', 'location']
            is_path_config = any(keyword in path.lower() for keyword in path_keywords)

            # Type conversion based on current value
            if isinstance(current_value, bool):
                # Boolean conversion
                if value.lower() in ['true', 'yes', '1']:
                    return True
                elif value.lower() in ['false', 'no', '0']:
                    return False
                else:
                    self.notify(f"Error: Expected boolean value (true/false), got '{value}'")
                    return None

            elif isinstance(current_value, int):
                # Integer conversion
                try:
                    return int(value)
                except ValueError:
                    self.notify(f"Error: Expected integer value, got '{value}'")
                    return None

            elif isinstance(current_value, float):
                # Float conversion
                try:
                    return float(value)
                except ValueError:
                    self.notify(f"Error: Expected numeric value, got '{value}'")
                    return None

            elif isinstance(current_value, str):
                # String value - check if it's a path
                if is_path_config:
                    # Validate path
                    expanded_path = os.path.expanduser(value)
                    if not os.path.exists(expanded_path):
                        self.notify(f"\nError: Path does not exist: {expanded_path}")
                        self.notify("Please enter a valid path.")
                        return None
                    # Return the original value (not expanded) as Gateway handles expansion
                    return value
                elif path.lower() == "defaultnetwork" and namespace:
                    # Special validation for defaultNetwork - must be a valid network for the chain
                    # Await the async validation
                    available_networks = await self._get_gateway_instance().get_available_networks_for_chain(

                        namespace  # namespace is the chain name
                    )

                    if available_networks and value not in available_networks:
                        self.notify(f"\nError: Invalid network '{value}' for {namespace}")
                        self.notify("Valid networks are: " + ", ".join(available_networks))
                        return None

                    return value
                else:
                    # Regular string
                    return value

            elif isinstance(current_value, list):
                # List conversion - try to parse as comma-separated values
                if value.startswith('[') and value.endswith(']'):
                    # JSON-style list
                    import json
                    try:
                        return json.loads(value)
                    except json.JSONDecodeError:
                        self.notify("Error: Invalid list format. Use JSON format like: ['item1', 'item2']")
                        return None
                else:
                    # Comma-separated values
                    return [item.strip() for item in value.split(',')]

            else:
                # Unknown type - return as string
                return value

        except Exception as e:
            self.notify(f"Error validating value: {str(e)}")
            return None
