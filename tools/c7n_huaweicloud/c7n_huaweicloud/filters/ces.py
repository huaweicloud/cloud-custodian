# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from c7n.filters import Filter
from c7n.utils import type_schema


class AlarmNameSpaceAndMetricFilter(Filter):
    schema = type_schema(
        'alarm-namespace-metric',
        required=['namespaces', 'metric_names'],
        namespaces={'type': 'array', 'items': {'type': 'string'}},  # 目标namespace列表
        metric_names={'type': 'array', 'items': {'type': 'string'}},  # 目标metric_name列表
        count={'type': 'array', 'items':
            {
                'type': 'number',
                'enum': [1, 2, 3, 4, 5, 10, 15, 30, 60, 90, 120, 180]
            }},  # 目标count列表
        period={'type': 'array', 'items':
            {
                'type': 'number',
                'enum': [0, 1, 300, 1200, 3600, 14400, 86400]
            }},  # 目标period列表
        comparison_operator={'type': 'array', 'items':
            {
                'type': 'string',
                'enum': [
                    '>', '>=', '=',
                    '!=', '<', '<=',
                    'cycle_decrease', 'cycle_increase', 'cycle_wave']
            }},  # 目标comparison_operator列表
    )

    def process(self, resources, event=None):
        matched = []
        for alarm in resources:
            # Namespace匹配
            namespace_match = alarm.get('namespace') in self.data['namespaces']
            if not namespace_match:
                continue

            # 策略匹配检查
            policies = alarm.get('policies', [])
            policy_match = any(
                self._check_policy(policy)
                for policy in policies
            )

            if policy_match:
                matched.append(alarm)
        return matched

    def _check_policy(self, policy):
        # 指标名称检查
        metric_match = policy.get('metric_name') in self.data['metric_names']
        if not metric_match:
            return False

        # 条件参数检查
        conditions = [
            ('count', self.data.get('count')),
            ('period', self.data.get('period')),
            ('comparison_operator', self.data.get('comparison_operator'))
        ]

        for field, allowed_values in conditions:
            if allowed_values and policy.get(field) not in allowed_values:
                return False

        return True
