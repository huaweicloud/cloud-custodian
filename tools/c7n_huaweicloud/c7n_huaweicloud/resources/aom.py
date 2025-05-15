# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from huaweicloudsdkcore.exceptions import exceptions
# 注意：虽然SDK提供了v4版本，但AOM的告警规则相关API仅存在于v2版本中
# v4版本主要提供了AgentManagement相关功能，不包含告警规则管理相关API
from huaweicloudsdkaom.v2 import (
    DeleteMetricOrEventAlarmRuleRequest, DeleteAlarmRuleV4RequestBody,
    AddOrUpdateMetricOrEventAlarmRuleRequest, AddOrUpdateAlarmRuleV4RequestBody,
    AlarmNotification, MetricAlarmSpec, EventAlarmSpec,
    AlarmTags, TriggerCondition, RecoveryCondition, EventTriggerCondition
)

from c7n.utils import type_schema
from c7n.filters import ValueFilter
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction

log = logging.getLogger('custodian.huaweicloud.resources.aom')


@resources.register('aom-alarm')
class AomAlarm(QueryResourceManager):
    """华为云AOM告警规则资源管理器

    用于管理和操作华为云应用运维管理服务(AOM)的告警规则
    """

    class resource_type(TypeInfo):
        service = "aom"
        enum_spec = ("list_metric_or_event_alarm_rule", "alarm_rules", None)
        id = "alarm_rule_id"
        tag_resource_type = "aom"


@AomAlarm.filter_registry.register('alarm-rule')
class AlarmRuleFilter(ValueFilter):
    """AOM告警规则过滤器

    根据告警规则的属性进行过滤

    :example:

    .. code-block:: yaml

        policies:
          - name: aom-alarm-rule-filter
            resource: huaweicloud.aom-alarm
            filters:
              - type: alarm-rule
                key: name
                op: eq
                value: "test-alarm"
    """
    schema = type_schema('alarm-rule', rinherit=ValueFilter.schema)
    schema_alias = False

    def process(self, resources, event=None):
        return [r for r in resources if self.match(r)]


@AomAlarm.action_registry.register('delete')
class DeleteAlarmRule(HuaweiCloudBaseAction):
    """删除AOM告警规则

    :example:

    .. code-block:: yaml

        policies:
          - name: delete-aom-alarm
            resource: huaweicloud.aom-alarm
            filters:
              - type: alarm-rule
                key: name
                value: "test-alarm"
            actions:
              - delete
    """
    schema = type_schema('delete')

    def process(self, resources):
        client = self.manager.get_client()
        results = []

        for resource in resources:
            try:
                request = DeleteMetricOrEventAlarmRuleRequest(
                    body=DeleteAlarmRuleV4RequestBody(alarm_rules=[resource["alarm_rule_name"]]))
                response = client.delete_metric_or_event_alarm_rule(request)
                results.append({
                    'alarm_rule_name': resource['alarm_rule_name'],
                    'status_code': response.status_code
                })
                log.info(f"删除AOM告警规则成功: {resource['alarm_rule_name']}")
            except exceptions.ClientRequestException as e:
                log.error(
                    f"删除AOM告警规则失败: {resource['alarm_rule_name']}, 错误: {e.error_msg}")
                results.append({
                    'alarm_rule_name': resource['alarm_rule_name'],
                    'error': f"{e.status_code}:{e.error_code}:{e.error_msg}"
                })

        return results

    def perform_action(self, resource):
        # 由于我们在process方法中已经处理了每个资源，所以这里不需要额外的操作
        pass


@AomAlarm.action_registry.register('update')
class UpdateAlarmRule(HuaweiCloudBaseAction):
    """更新AOM告警规则

    根据API文档更新AOM告警规则，支持更新告警规则的名称、描述、是否启用、告警通知等属性

    :example:

    .. code-block:: yaml

        policies:
          - name: update-aom-alarm
            resource: huaweicloud.aom-alarm
            filters:
              - type: alarm-rule
                key: name
                value: "test-alarm"
            actions:
              - type: update
                alarm_rule_name: "updated-alarm-name"
                alarm_rule_description: "更新的告警描述"
                alarm_rule_enable: true
                alarm_notifications:
                  notification_type: "direct"
                  notify_triggered: true
                  notify_resolved: false
                  route_group_enable: false
                  route_group_rule: ""
                  notification_enable: true
                  bind_notification_rule_id: "notification-rule-id"
                  notify_frequency: 0
                alarm_rule_type: "event"
                metric_alarm_spec:
                  monitor_type: "all_metric"
                  alarm_tags:
                    - key: "tag_key"
                      value: "tag_value"
                  trigger_conditions:
                    - metric_name: "cpu_usage"
                      metric_namespace: "PAAS.CONTAINER"
                      period: 60000
                      statistic: "average"
                      comparison_operator: ">"
                      threshold: 80
                      filter: "resource_group_id=default_resource_group_id"
                      count: 3
                      severity: 2
                event_alarm_spec:
                  alarm_source: "systemEvent"
                  event_source: "AOM"
                  monitor_objects:
                    - event_type: "fault"
                      event_severity: "warning"
                  trigger_conditions:
                    - count: 1
                      severity: 2
                prom_instance_id: ""
    """
    schema = type_schema(
        'update',
        alarm_rule_name={'type': 'string'},
        alarm_rule_description={'type': 'string'},
        alarm_rule_enable={'type': 'boolean'},
        alarm_notifications={'type': 'object'},
        alarm_rule_type={'type': 'string', 'enum': ['metric', 'event']},
        metric_alarm_spec={'type': 'object'},
        event_alarm_spec={'type': 'object'},
        prom_instance_id={'type': 'string'}
    )

    def process(self, resources):
        client = self.manager.get_client()
        results = []

        for resource in resources:
            try:
                # 准备更新请求
                request = self._build_update_request(resource)

                # 调用API更新告警规则
                response = client.add_or_update_metric_or_event_alarm_rule(request)
                results.append({
                    'resource_id': resource['alarm_rule_name'],
                    'status_code': response.status_code
                })
                log.info(f"更新AOM告警规则成功: {resource['alarm_rule_name']}")
            except exceptions.ClientRequestException as e:
                log.error(
                    f"更新AOM告警规则失败: {resource['alarm_rule_name']}, 错误: {e.error_msg}")
                results.append({
                    'resource_id': resource['alarm_rule_name'],
                    'error': f"{e.status_code}:{e.error_code}:{e.error_msg}"
                })

        return results

    def _build_update_request(self, resource):
        """构建更新请求"""
        # 创建请求主体
        body = AddOrUpdateAlarmRuleV4RequestBody()

        # 设置告警规则名称 - 必填
        body.alarm_rule_name = self.data.get('alarm_rule_name', resource['alarm_rule_name'])

        # 设置告警规则类型 - 必填
        body.alarm_rule_type = self.data.get('alarm_rule_type', resource['alarm_rule_type'])

        # 设置可选参数
        if 'alarm_rule_description' in self.data:
            body.alarm_rule_description = self.data['alarm_rule_description']

        if 'alarm_rule_enable' in self.data:
            body.alarm_rule_enable = self.data['alarm_rule_enable']

        # 设置Prometheus实例ID（可选）
        if 'prom_instance_id' in self.data:
            body.prom_instance_id = self.data['prom_instance_id']

        # 设置告警通知
        if 'alarm_notifications' in self.data:
            notification = AlarmNotification()

            notification_data = self.data['alarm_notifications']

            # 设置通知类型
            if 'notification_type' in notification_data:
                notification.notification_type = notification_data['notification_type']

            # 设置分组规则启用状态
            if 'route_group_enable' in notification_data:
                notification.route_group_enable = notification_data['route_group_enable']

            # 设置分组规则名称
            if 'route_group_rule' in notification_data:
                notification.route_group_rule = notification_data['route_group_rule']

            # 设置通知启用状态
            if 'notification_enable' in notification_data:
                notification.notification_enable = notification_data['notification_enable']

            # 设置绑定的通知规则ID
            if 'bind_notification_rule_id' in notification_data:
                notification.bind_notification_rule_id = notification_data[
                    'bind_notification_rule_id']

            # 设置告警解决是否通知
            if 'notify_resolved' in notification_data:
                notification.notify_resolved = notification_data['notify_resolved']

            # 设置告警触发是否通知
            if 'notify_triggered' in notification_data:
                notification.notify_triggered = notification_data['notify_triggered']

            # 设置通知频率
            if 'notify_frequency' in notification_data:
                notification.notify_frequency = notification_data['notify_frequency']

            body.alarm_notifications = notification

        # 根据告警规则类型设置相应的规格
        if body.alarm_rule_type == 'metric' and 'metric_alarm_spec' in self.data:
            body.metric_alarm_spec = self._build_metric_alarm_spec(self.data['metric_alarm_spec'])
        elif body.alarm_rule_type == 'event' and 'event_alarm_spec' in self.data:
            body.event_alarm_spec = self._build_event_alarm_spec(self.data['event_alarm_spec'])

        # 创建并返回请求
        return AddOrUpdateMetricOrEventAlarmRuleRequest(
            action_id="update-alarm-action",
            body=body
        )

    def _build_metric_alarm_spec(self, spec_data):
        """构建指标告警规格"""
        metric_spec = MetricAlarmSpec()

        # 设置监控类型
        if 'monitor_type' in spec_data:
            metric_spec.monitor_type = spec_data['monitor_type']

        # 设置告警标签
        if 'alarm_tags' in spec_data and isinstance(spec_data['alarm_tags'], list):
            tags = []
            for tag_item in spec_data['alarm_tags']:
                tag = AlarmTags()
                if 'key' in tag_item:
                    tag.key = tag_item['key']
                if 'value' in tag_item:
                    tag.value = tag_item['value']
                tags.append(tag)
            metric_spec.alarm_tags = tags

        # 设置监控对象
        if 'monitor_objects' in spec_data:
            metric_spec.monitor_objects = spec_data['monitor_objects']

        # 设置恢复条件
        if 'recovery_conditions' in spec_data:
            recovery = RecoveryCondition()
            recovery_data = spec_data['recovery_conditions']

            for key, value in recovery_data.items():
                setattr(recovery, key, value)

            metric_spec.recovery_conditions = recovery

        # 设置触发条件
        if 'trigger_conditions' in spec_data and isinstance(spec_data['trigger_conditions'], list):
            conditions = []
            for condition_item in spec_data['trigger_conditions']:
                condition = TriggerCondition()
                for key, value in condition_item.items():
                    setattr(condition, key, value)
                conditions.append(condition)
            metric_spec.trigger_conditions = conditions

        return metric_spec

    def _build_event_alarm_spec(self, spec_data):
        """构建事件告警规格"""
        event_spec = EventAlarmSpec()

        # 设置告警规则来源
        if 'alarm_source' in spec_data:
            event_spec.alarm_source = spec_data['alarm_source']

        # 设置告警来源
        if 'event_source' in spec_data:
            event_spec.event_source = spec_data['event_source']

        # 设置监控对象
        if 'monitor_objects' in spec_data:
            event_spec.monitor_objects = spec_data['monitor_objects']

        # 设置触发条件
        if 'trigger_conditions' in spec_data and isinstance(spec_data['trigger_conditions'], list):
            conditions = []
            for condition_item in spec_data['trigger_conditions']:
                condition = EventTriggerCondition()
                for key, value in condition_item.items():
                    setattr(condition, key, value)
                conditions.append(condition)
            event_spec.trigger_conditions = conditions

        return event_spec

    def perform_action(self, resource):
        # 这个方法在此action中不会被调用，因为我们在process方法中已经处理了每个资源
        pass


@AomAlarm.action_registry.register('add')
class AddAlarmRule(HuaweiCloudBaseAction):
    """添加AOM告警规则

    根据API文档添加AOM指标类或事件类告警规则

    :example:

    .. code-block:: yaml

        policies:
          - name: add-metric-alarm
            resource: huaweicloud.aom-alarm
            actions:
              - type: add
                alarm_rule_name: "new-metric-alarm"
                alarm_rule_description: "新的指标告警规则"
                alarm_rule_type: "metric"
                alarm_rule_enable: true
                alarm_notifications:
                  notification_type: "direct"
                  route_group_enable: false
                  route_group_rule: ""
                  notification_enable: true
                  bind_notification_rule_id: "notification-rule-id"
                  notify_resolved: false
                  notify_triggered: true
                  notify_frequency: 0
                metric_alarm_spec:
                  monitor_type: "all_metric"
                  alarm_tags:
                    - key: "tag_key"
                      value: "tag_value"
                  trigger_conditions:
                    - metric_name: "cpu_usage"
                      metric_namespace: "PAAS.CONTAINER"
                      period: 60000
                      statistic: "average"
                      comparison_operator: ">"
                      threshold: 80
                      filter: "resource_group_id=default_resource_group_id"
                      count: 3
                      severity: 2

        policies:
          - name: add-event-alarm
            resource: huaweicloud.aom-alarm
            actions:
              - type: add
                alarm_rule_name: "new-event-alarm"
                alarm_rule_description: "新的事件告警规则"
                alarm_rule_type: "event"
                alarm_rule_enable: true
                alarm_notifications:
                  notification_type: "direct"
                  route_group_enable: false
                  route_group_rule: ""
                  notification_enable: true
                  bind_notification_rule_id: "notification-rule-id"
                  notify_resolved: false
                  notify_triggered: true
                  notify_frequency: 0
                event_alarm_spec:
                  alarm_source: "systemEvent"
                  event_source: "AOM"
                  monitor_objects:
                    - event_type: "fault"
                      event_severity: "warning"
                  trigger_conditions:
                    - count: 1
                      severity: 2
                prom_instance_id: ""
    """
    schema = type_schema(
        'add',
        alarm_rule_name={'type': 'string'},
        alarm_rule_description={'type': 'string'},
        alarm_rule_enable={'type': 'boolean'},
        alarm_notifications={'type': 'object'},
        alarm_rule_type={'type': 'string', 'enum': ['metric', 'event']},
        metric_alarm_spec={'type': 'object'},
        event_alarm_spec={'type': 'object'},
        prom_instance_id={'type': 'string'},
        required=['alarm_rule_name', 'alarm_rule_type']
    )

    def process(self, resources):
        # 添加告警规则不需要现有资源，我们直接创建一个新的规则
        client = self.manager.get_client()

        try:
            # 构建请求
            request = self._build_add_request()

            # 调用API创建告警规则
            response = client.add_or_update_metric_or_event_alarm_rule(request)

            log.info(f"添加AOM告警规则成功: {self.data['alarm_rule_name']}")
            return [{
                'alarm_rule_name': self.data['alarm_rule_name'],
                'status_code': response.status_code
            }]
        except exceptions.ClientRequestException as e:
            log.error(f"添加AOM告警规则失败: {self.data['alarm_rule_name']}, 错误: {e.error_msg}")
            return [{
                'alarm_rule_name': self.data['alarm_rule_name'],
                'error': f"{e.status_code}:{e.error_code}:{e.error_msg}"
            }]

    def _build_add_request(self):
        """构建添加请求"""
        # 创建请求主体
        body = AddOrUpdateAlarmRuleV4RequestBody()

        # 设置告警规则名称 - 必填
        body.alarm_rule_name = self.data['alarm_rule_name']

        # 设置告警规则类型 - 必填
        body.alarm_rule_type = self.data['alarm_rule_type']

        # 设置可选参数
        if 'alarm_rule_description' in self.data:
            body.alarm_rule_description = self.data['alarm_rule_description']

        if 'alarm_rule_enable' in self.data:
            body.alarm_rule_enable = self.data['alarm_rule_enable']

        # 设置Prometheus实例ID（可选）
        if 'prom_instance_id' in self.data:
            body.prom_instance_id = self.data['prom_instance_id']

        # 设置告警通知
        if 'alarm_notifications' in self.data:
            notification = AlarmNotification()

            notification_data = self.data['alarm_notifications']

            # 设置通知类型
            if 'notification_type' in notification_data:
                notification.notification_type = notification_data['notification_type']

            # 设置分组规则启用状态
            if 'route_group_enable' in notification_data:
                notification.route_group_enable = notification_data['route_group_enable']

            # 设置分组规则名称
            if 'route_group_rule' in notification_data:
                notification.route_group_rule = notification_data['route_group_rule']

            # 设置通知启用状态
            if 'notification_enable' in notification_data:
                notification.notification_enable = notification_data['notification_enable']

            # 设置绑定的通知规则ID
            if 'bind_notification_rule_id' in notification_data:
                notification.bind_notification_rule_id = notification_data[
                    'bind_notification_rule_id']

            # 设置告警解决是否通知
            if 'notify_resolved' in notification_data:
                notification.notify_resolved = notification_data['notify_resolved']

            # 设置告警触发是否通知
            if 'notify_triggered' in notification_data:
                notification.notify_triggered = notification_data['notify_triggered']

            # 设置通知频率
            if 'notify_frequency' in notification_data:
                notification.notify_frequency = notification_data['notify_frequency']

            body.alarm_notifications = notification

        # 根据告警规则类型设置相应的规格
        if body.alarm_rule_type == 'metric' and 'metric_alarm_spec' in self.data:
            body.metric_alarm_spec = self._build_metric_alarm_spec(self.data['metric_alarm_spec'])
        elif body.alarm_rule_type == 'event' and 'event_alarm_spec' in self.data:
            body.event_alarm_spec = self._build_event_alarm_spec(self.data['event_alarm_spec'])

        # 创建并返回请求
        return AddOrUpdateMetricOrEventAlarmRuleRequest(
            action_id="add-alarm-action",
            body=body
        )

    def _build_metric_alarm_spec(self, spec_data):
        """构建指标告警规格"""
        metric_spec = MetricAlarmSpec()

        # 设置监控类型
        if 'monitor_type' in spec_data:
            metric_spec.monitor_type = spec_data['monitor_type']

        # 设置告警标签
        if 'alarm_tags' in spec_data and isinstance(spec_data['alarm_tags'], list):
            tags = []
            for tag_item in spec_data['alarm_tags']:
                tag = AlarmTags()
                if 'key' in tag_item:
                    tag.key = tag_item['key']
                if 'value' in tag_item:
                    tag.value = tag_item['value']
                tags.append(tag)
            metric_spec.alarm_tags = tags

        # 设置监控对象
        if 'monitor_objects' in spec_data:
            metric_spec.monitor_objects = spec_data['monitor_objects']

        # 设置恢复条件
        if 'recovery_conditions' in spec_data:
            recovery = RecoveryCondition()
            recovery_data = spec_data['recovery_conditions']

            for key, value in recovery_data.items():
                setattr(recovery, key, value)

            metric_spec.recovery_conditions = recovery

        # 设置触发条件
        if 'trigger_conditions' in spec_data and isinstance(spec_data['trigger_conditions'], list):
            conditions = []
            for condition_item in spec_data['trigger_conditions']:
                condition = TriggerCondition()
                for key, value in condition_item.items():
                    setattr(condition, key, value)
                conditions.append(condition)
            metric_spec.trigger_conditions = conditions

        return metric_spec

    def _build_event_alarm_spec(self, spec_data):
        """构建事件告警规格"""
        event_spec = EventAlarmSpec()

        # 设置告警规则来源
        if 'alarm_source' in spec_data:
            event_spec.alarm_source = spec_data['alarm_source']

        # 设置告警来源
        if 'event_source' in spec_data:
            event_spec.event_source = spec_data['event_source']

        # 设置监控对象
        if 'monitor_objects' in spec_data:
            event_spec.monitor_objects = spec_data['monitor_objects']

        # 设置触发条件
        if 'trigger_conditions' in spec_data and isinstance(spec_data['trigger_conditions'], list):
            conditions = []
            for condition_item in spec_data['trigger_conditions']:
                condition = EventTriggerCondition()
                for key, value in condition_item.items():
                    setattr(condition, key, value)
                conditions.append(condition)
            event_spec.trigger_conditions = conditions

        return event_spec

    def perform_action(self, resource):
        # 这个方法在此action中不会被调用，因为我们不是对现有资源执行操作
        pass
