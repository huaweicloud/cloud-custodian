from c7n.filters.core import Filter
from c7n.filters.core import OPERATORS
from datetime import datetime, timedelta
from dateutil.parser import parse
from dateutil.tz import tzutc

class AgeFilter(Filter):
    """Filter resources by comparing their date attribute to a threshold."""
    
    # 定义支持的比较操作符（需要确保 OPERATORS 字典中有这些键）
    SUPPORTED_OPS = {'greater-than', 'less-than'}
    
    def __init__(self, data, manager=None):
        super().__init__(data, manager)
        self._threshold_date = None
        self._op = self._validate_op(data.get('op', 'greater-than'))
        
        # 时间阈值参数（天、小时、分钟）
        self.days = data.get('days', 0)
        self.hours = data.get('hours', 0)
        self.minutes = data.get('minutes', 0)

    def _validate_op(self, op):
        """验证操作符是否合法"""
        if op not in self.SUPPORTED_OPS:
            raise ValueError(f"Unsupported operator '{op}', use: {self.SUPPORTED_OPS}")
        return op

    def get_resource_date(self, resource):
        """从资源中提取日期并转换为 UTC 时区"""
        date_str = resource.get(self.date_attribute)
        if not date_str:
            return None
        
        # 解析日期字符串并附加 UTC 时区
        dt = parse(date_str)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=tzutc())
        return dt

    @property
    def threshold_date(self):
        """计算阈值日期（UTC 时区）"""
        if self._threshold_date is None:
            # 当前 UTC 时间
            now = datetime.now(tzutc())
            # 根据配置的时间参数计算阈值
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
            return False  # 无日期字段的资源默认过滤
        
        # 根据操作符比较阈值
        if self._op == 'greater-than':
            return resource_dt < self.threshold_date
        else:  # less-than
            return resource_dt > self.threshold_date