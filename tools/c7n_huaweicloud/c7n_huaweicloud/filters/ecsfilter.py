import logging
from c7n.filters.core import Filter
from c7n.filters.core import OPERATORS
from datetime import datetime, timedelta
from dateutil.parser import parse
from dateutil.tz import tzutc
from tzlocal import get_localzone

log = logging.getLogger("custodian.huaweicloud.filter.ecs")

class AgeFilter(Filter):
    """Filter resources by comparing their date attribute to a threshold."""
    
    # Supported comparison operators
    SUPPORTED_OPS = {'greater-than', 'less-than'}
    
    def __init__(self, data, manager=None):
        super().__init__(data, manager)
        self._threshold_date = None
        self._op = self._validate_op(data.get('op', 'greater-than'))
        
        # Time threshold parameter
        self.days = data.get('days', 0)
        self.hours = data.get('hours', 0)
        self.minutes = data.get('minutes', 0)

    def _validate_op(self, op):
        """Verify whether the operator is valid"""
        if op not in self.SUPPORTED_OPS:
            raise ValueError(f"Unsupported operator '{op}', use: {self.SUPPORTED_OPS}")
        return op

    def get_resource_date(self, resource):
        """Extract the date from the resource and convert to the UTC time zone"""
        date_str = resource.get(self.date_attribute)
        if not date_str:
            return None
        
        # Parse the date string and append the UTC time zone
        dt = parse(date_str)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=tzutc())
        return dt

    @property
    def threshold_date(self):
        if self._threshold_date is None:
            # Now time zone
            local_tz = get_localzone()
            now = datetime.now(local_tz)
            # Calculate thresholds
            delta = timedelta(
                days=self.days,
                hours=self.hours,
                minutes=self.minutes
            )
            self._threshold_date = now - delta
        return self._threshold_date

    def __call__(self, resource):
        resource_dt = self.get_resource_date(resource)
        if not resource_dt:
            return False
        if self._op == 'greater-than':
            return resource_dt < self.threshold_date
        else:  # less-than
            return resource_dt > self.threshold_date