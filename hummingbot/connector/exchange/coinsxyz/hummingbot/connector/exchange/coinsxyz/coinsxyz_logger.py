"""
Advanced Logging System for Coins.xyz Exchange Connector

This module provides comprehensive request/response logging capabilities
with security filtering, performance monitoring, and debugging support.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from hummingbot.connector.exchange.coinsxyz import coinsxyz_constants as CONSTANTS


class CoinsxyzRequestLogger:
    """
    Advanced request/response logger with security filtering and performance monitoring.
    
    This class provides comprehensive logging capabilities for API requests and responses,
    including security filtering to prevent sensitive data leakage, performance monitoring,
    and structured logging for debugging purposes.
    """
    
    # Sensitive fields that should be filtered from logs
    SENSITIVE_FIELDS = {
        'signature', 'apikey', 'api_key', 'secret', 'secret_key',
        'password', 'token', 'auth', 'authorization', 'x-coins-apikey'
    }
    
    # Fields that should be truncated if too long
    TRUNCATE_FIELDS = {
        'symbols', 'data', 'result', 'response'
    }
    
    # Maximum length for truncated fields
    MAX_FIELD_LENGTH = 1000
    
    def __init__(self, logger_name: str = None):
        """
        Initialize the request logger.
        
        :param logger_name: Name for the logger instance
        """
        self._logger = logging.getLogger(logger_name or __name__)
        self._request_counter = 0
        self._performance_stats = {
            'total_requests': 0,
            'total_response_time': 0.0,
            'fastest_request': float('inf'),
            'slowest_request': 0.0,
            'error_count': 0,
            'success_count': 0
        }
    
    def log_request(self, 
                   method: str, 
                   url: str, 
                   headers: Optional[Dict[str, str]] = None,
                   params: Optional[Dict[str, Any]] = None,
                   data: Optional[Dict[str, Any]] = None,
                   request_id: Optional[str] = None) -> str:
        """
        Log an outgoing API request with security filtering.
        
        :param method: HTTP method (GET, POST, etc.)
        :param url: Request URL
        :param headers: Request headers
        :param params: URL parameters
        :param data: Request body data
        :param request_id: Optional request ID for correlation
        :return: Generated request ID for correlation
        """
        if request_id is None:
            self._request_counter += 1
            request_id = f"req_{self._request_counter:06d}"
        
        # Parse URL for cleaner logging
        parsed_url = urlparse(url)
        endpoint = parsed_url.path
        
        # Filter sensitive data
        safe_headers = self._filter_sensitive_data(headers or {})
        safe_params = self._filter_sensitive_data(params or {})
        safe_data = self._filter_sensitive_data(data or {})
        
        # Create request log entry
        log_entry = {
            'request_id': request_id,
            'timestamp': time.time(),
            'direction': 'REQUEST',
            'method': method,
            'endpoint': endpoint,
            'url': f"{parsed_url.scheme}://{parsed_url.netloc}{endpoint}",
            'headers': safe_headers,
            'params': safe_params,
            'data': safe_data if safe_data else None
        }
        
        # Log at appropriate level
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug(f"🚀 API Request [{request_id}]: {method} {endpoint}")
            self._logger.debug(f"   Full details: {json.dumps(log_entry, indent=2, default=str)}")
        else:
            self._logger.info(f"🚀 API Request [{request_id}]: {method} {endpoint}")
        
        return request_id
    
    def log_response(self,
                    request_id: str,
                    status_code: int,
                    response_data: Optional[Dict[str, Any]] = None,
                    response_headers: Optional[Dict[str, str]] = None,
                    response_time: Optional[float] = None,
                    error: Optional[Exception] = None) -> None:
        """
        Log an API response with performance metrics.
        
        :param request_id: Request ID for correlation
        :param status_code: HTTP status code
        :param response_data: Response body data
        :param response_headers: Response headers
        :param response_time: Request duration in seconds
        :param error: Exception if request failed
        """
        # Update performance statistics
        self._update_performance_stats(status_code, response_time, error)
        
        # Filter and truncate response data
        safe_response_data = self._filter_and_truncate_data(response_data or {})
        safe_response_headers = self._filter_sensitive_data(response_headers or {})
        
        # Determine log level and status
        if error:
            status_emoji = "❌"
            log_level = logging.ERROR
            status_text = f"ERROR ({status_code})"
        elif 200 <= status_code < 300:
            status_emoji = "✅"
            log_level = logging.DEBUG if status_code == 200 else logging.INFO
            status_text = f"SUCCESS ({status_code})"
        elif 400 <= status_code < 500:
            status_emoji = "⚠️"
            log_level = logging.WARNING
            status_text = f"CLIENT_ERROR ({status_code})"
        else:
            status_emoji = "🔥"
            log_level = logging.ERROR
            status_text = f"SERVER_ERROR ({status_code})"
        
        # Create response log entry
        log_entry = {
            'request_id': request_id,
            'timestamp': time.time(),
            'direction': 'RESPONSE',
            'status_code': status_code,
            'status_text': status_text,
            'response_time': response_time,
            'headers': safe_response_headers,
            'data': safe_response_data,
            'error': str(error) if error else None
        }
        
        # Log response
        response_time_str = f" ({response_time:.3f}s)" if response_time else ""
        
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.log(log_level, f"{status_emoji} API Response [{request_id}]: {status_text}{response_time_str}")
            self._logger.debug(f"   Full details: {json.dumps(log_entry, indent=2, default=str)}")
        else:
            self._logger.log(log_level, f"{status_emoji} API Response [{request_id}]: {status_text}{response_time_str}")
            
            # Log error details at INFO level for visibility
            if error:
                self._logger.info(f"   Error: {str(error)}")
            
            # Log important response data at INFO level
            if safe_response_data and not error:
                self._log_important_response_data(safe_response_data)
    
    def log_performance_summary(self) -> None:
        """Log performance statistics summary."""
        stats = self._performance_stats
        
        if stats['total_requests'] == 0:
            self._logger.info("📊 No API requests recorded yet")
            return
        
        avg_response_time = stats['total_response_time'] / stats['total_requests']
        success_rate = (stats['success_count'] / stats['total_requests']) * 100
        
        summary = {
            'total_requests': stats['total_requests'],
            'success_count': stats['success_count'],
            'error_count': stats['error_count'],
            'success_rate': f"{success_rate:.1f}%",
            'avg_response_time': f"{avg_response_time:.3f}s",
            'fastest_request': f"{stats['fastest_request']:.3f}s" if stats['fastest_request'] != float('inf') else "N/A",
            'slowest_request': f"{stats['slowest_request']:.3f}s"
        }
        
        self._logger.info("📊 API Performance Summary:")
        self._logger.info(f"   {json.dumps(summary, indent=4)}")
    
    def _filter_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter sensitive data from dictionaries.
        
        :param data: Dictionary to filter
        :return: Filtered dictionary with sensitive data masked
        """
        if not isinstance(data, dict):
            return data
        
        filtered = {}
        for key, value in data.items():
            key_lower = key.lower()
            
            if any(sensitive in key_lower for sensitive in self.SENSITIVE_FIELDS):
                # Mask sensitive data
                if isinstance(value, str) and len(value) > 8:
                    filtered[key] = f"{value[:4]}...{value[-4:]}"
                else:
                    filtered[key] = "***MASKED***"
            elif isinstance(value, dict):
                # Recursively filter nested dictionaries
                filtered[key] = self._filter_sensitive_data(value)
            else:
                filtered[key] = value
        
        return filtered
    
    def _filter_and_truncate_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter sensitive data and truncate large fields.
        
        :param data: Dictionary to process
        :return: Processed dictionary
        """
        # First filter sensitive data
        filtered = self._filter_sensitive_data(data)
        
        # Then truncate large fields
        for key, value in filtered.items():
            if key.lower() in self.TRUNCATE_FIELDS:
                if isinstance(value, (list, dict)):
                    value_str = json.dumps(value, default=str)
                    if len(value_str) > self.MAX_FIELD_LENGTH:
                        truncated = value_str[:self.MAX_FIELD_LENGTH]
                        filtered[key] = f"{truncated}... [TRUNCATED - {len(value_str)} chars total]"
                elif isinstance(value, str) and len(value) > self.MAX_FIELD_LENGTH:
                    filtered[key] = f"{value[:self.MAX_FIELD_LENGTH]}... [TRUNCATED - {len(value)} chars total]"
        
        return filtered
    
    def _update_performance_stats(self, status_code: int, response_time: Optional[float], error: Optional[Exception]) -> None:
        """Update internal performance statistics."""
        self._performance_stats['total_requests'] += 1
        
        if error or status_code >= 400:
            self._performance_stats['error_count'] += 1
        else:
            self._performance_stats['success_count'] += 1
        
        if response_time is not None:
            self._performance_stats['total_response_time'] += response_time
            self._performance_stats['fastest_request'] = min(self._performance_stats['fastest_request'], response_time)
            self._performance_stats['slowest_request'] = max(self._performance_stats['slowest_request'], response_time)
    
    def _log_important_response_data(self, response_data: Dict[str, Any]) -> None:
        """Log important response data at INFO level for visibility."""
        # Log key metrics from different endpoint types
        if 'serverTime' in response_data:
            self._logger.info(f"   Server time: {response_data['serverTime']}")
        
        if 'symbols' in response_data:
            symbols_count = len(response_data['symbols']) if isinstance(response_data['symbols'], list) else 0
            self._logger.info(f"   Symbols count: {symbols_count}")
        
        if 'bids' in response_data and 'asks' in response_data:
            bids_count = len(response_data['bids']) if isinstance(response_data['bids'], list) else 0
            asks_count = len(response_data['asks']) if isinstance(response_data['asks'], list) else 0
            self._logger.info(f"   Order book: {bids_count} bids, {asks_count} asks")
        
        if 'balances' in response_data:
            balances_count = len(response_data['balances']) if isinstance(response_data['balances'], list) else 0
            self._logger.info(f"   Account balances: {balances_count} assets")
        
        if 'orderId' in response_data:
            self._logger.info(f"   Order ID: {response_data['orderId']}")
        
        if 'status' in response_data:
            self._logger.info(f"   Status: {response_data['status']}")
        
        # Log error information if present
        if 'code' in response_data and response_data['code'] < 0:
            self._logger.info(f"   API Error Code: {response_data['code']}")
            if 'msg' in response_data:
                self._logger.info(f"   API Error Message: {response_data['msg']}")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get current performance statistics.
        
        :return: Dictionary with performance metrics
        """
        stats = self._performance_stats.copy()
        
        if stats['total_requests'] > 0:
            stats['avg_response_time'] = stats['total_response_time'] / stats['total_requests']
            stats['success_rate'] = (stats['success_count'] / stats['total_requests']) * 100
        else:
            stats['avg_response_time'] = 0.0
            stats['success_rate'] = 0.0
        
        if stats['fastest_request'] == float('inf'):
            stats['fastest_request'] = 0.0
        
        return stats
    
    def reset_stats(self) -> None:
        """Reset performance statistics."""
        self._performance_stats = {
            'total_requests': 0,
            'total_response_time': 0.0,
            'fastest_request': float('inf'),
            'slowest_request': 0.0,
            'error_count': 0,
            'success_count': 0
        }
        self._request_counter = 0


class CoinsxyzDebugLogger:
    """
    Debug-specific logger for detailed troubleshooting.
    
    This class provides additional debugging capabilities including
    request/response correlation, timing analysis, and detailed
    error tracking for development and troubleshooting purposes.
    """
    
    def __init__(self, logger_name: str = None):
        """Initialize debug logger."""
        self._logger = logging.getLogger(f"{logger_name or __name__}.debug")
        self._active_requests = {}  # Track active requests for correlation
    
    def start_request_tracking(self, request_id: str, method: str, endpoint: str) -> None:
        """Start tracking a request for timing and correlation."""
        self._active_requests[request_id] = {
            'method': method,
            'endpoint': endpoint,
            'start_time': time.time(),
            'status': 'ACTIVE'
        }
        
        self._logger.debug(f"🔄 Started tracking request [{request_id}]: {method} {endpoint}")
    
    def finish_request_tracking(self, request_id: str, status_code: int, error: Optional[Exception] = None) -> Optional[float]:
        """Finish tracking a request and return duration."""
        if request_id not in self._active_requests:
            self._logger.warning(f"⚠️  Request [{request_id}] not found in active tracking")
            return None
        
        request_info = self._active_requests.pop(request_id)
        duration = time.time() - request_info['start_time']
        
        status = "ERROR" if error else "SUCCESS"
        self._logger.debug(f"🏁 Finished tracking request [{request_id}]: {status} in {duration:.3f}s")
        
        return duration
    
    def log_request_correlation(self, request_id: str, related_data: Dict[str, Any]) -> None:
        """Log additional data correlated with a request."""
        self._logger.debug(f"🔗 Request correlation [{request_id}]: {json.dumps(related_data, default=str)}")
    
    def log_timing_breakdown(self, request_id: str, timing_data: Dict[str, float]) -> None:
        """Log detailed timing breakdown for a request."""
        self._logger.debug(f"⏱️  Timing breakdown [{request_id}]:")
        for phase, duration in timing_data.items():
            self._logger.debug(f"   {phase}: {duration:.3f}s")
    
    def get_active_requests(self) -> Dict[str, Dict[str, Any]]:
        """Get currently active (unfinished) requests."""
        return self._active_requests.copy()
