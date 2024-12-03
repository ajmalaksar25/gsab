from typing import Dict, Optional
import time
from ..exceptions.custom_exceptions import QuotaExceededError

class QuotaMonitor:
    """Monitors Google Sheets API quota usage."""
    
    # Default quotas (can be customized)
    DEFAULT_QUOTAS = {
        'read_requests_per_minute': 300,
        'write_requests_per_minute': 60
    }
    
    def __init__(self, custom_quotas: Optional[Dict[str, int]] = None):
        self.quotas = custom_quotas or self.DEFAULT_QUOTAS
        self._request_timestamps = {
            'read': [],
            'write': []
        }
        
    def check_quota(self, operation_type: str) -> None:
        """
        Check if operation would exceed quota.
        
        Args:
            operation_type: Type of operation ('read' or 'write')
        
        Raises:
            QuotaExceededError: If quota would be exceeded
        """
        current_time = time.time()
        timestamps = self._request_timestamps[operation_type]
        
        # Remove timestamps older than 1 minute
        while timestamps and current_time - timestamps[0] > 60:
            timestamps.pop(0)
            
        quota_key = f"{operation_type}_requests_per_minute"
        if len(timestamps) >= self.quotas[quota_key]:
            raise QuotaExceededError(
                f"Quota exceeded for {operation_type} operations. "
                f"Limit: {self.quotas[quota_key]} requests per minute"
            )
            
        timestamps.append(current_time) 