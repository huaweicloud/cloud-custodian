# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from huaweicloudsdkcore.exceptions import exceptions
# Note: Although SDK provides v4 version, AOM alarm rule related APIs only exist in v2 version
# v4 version mainly provides AgentManagement related features, without alarm rule management APIs
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
    """Huawei Cloud AOM Alarm Rule Resource Manager

    Used to manage and operate alarm rules of Huawei Cloud Application Operations Management (AOM)
    """

    class resource_type(TypeInfo):
        service = "aom"
        enum_spec = ("list_metric_or_event_alarm_rule", "alarm_rules", "offset")
        id = "alarm_rule_id"
        tag_resource_type = "alarm-rules"

    def augment(self, resources):
        # This method is called by the QueryResourceManager to allow
        # modification of resources after they are fetched from the API.
        # We will add a 'tags' field to each resource, formatted as a dictionary,
        # derived from 'custom_tags' within 'metric_alarm_spec.alarm_tags'.
        # This 'tags' field will be used by TMS (Tag Management Service) filters.

        for r_dict in resources:
            processed_tags = {}
            metric_spec = r_dict.get('metric_alarm_spec')
            if isinstance(metric_spec, dict):
                alarm_tags_list = metric_spec.get('alarm_tags')
                if isinstance(alarm_tags_list, list):
                    for alarm_tag_item_dict in alarm_tags_list:
                        if isinstance(alarm_tag_item_dict, dict):
                            custom_tags_str_list = alarm_tag_item_dict.get('custom_tags')
                            if isinstance(custom_tags_str_list, list):
                                for tag_str in custom_tags_str_list:
                                    if isinstance(tag_str, str) and '=' in tag_str:
                                        key, value = tag_str.split('=', 1)
                                        processed_tags[key] = value

            r_dict['tags'] = processed_tags
        return super(AomAlarm, self).augment(resources)


@AomAlarm.filter_registry.register('alarm-rule')
class AlarmRuleFilter(ValueFilter):
    """AOM Alarm Rule Filter

    Filter based on alarm rule properties

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
    """Delete AOM Alarm Rule

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
                log.info(f"Successfully deleted AOM alarm rule: {resource['alarm_rule_name']}")
            except exceptions.ClientRequestException as e:
                log.error(
                    f"Failed to delete AOM alarm rule: {resource['alarm_rule_name']}, "
                    f"error: {e.error_msg}")
                results.append({
                    'alarm_rule_name': resource['alarm_rule_name'],
                    'error': f"{e.status_code}:{e.error_code}:{e.error_msg}"
                })

        return results

    def perform_action(self, resource):
        pass


@AomAlarm.action_registry.register('update')
class UpdateAlarmRule(HuaweiCloudBaseAction):
    """Update AOM Alarm Rule

    Update AOM alarm rule according to API documentation, supporting updates to name, description,
    enable status, notifications, and other properties

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
                alarm_rule_description: "Updated alarm description"
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
                # Prepare update request
                request = self._build_update_request(resource)

                log.warning(resource)

                # Call API to update alarm rule
                response = client.add_or_update_metric_or_event_alarm_rule(request)
                results.append({
                    'resource_id': resource['alarm_rule_name'],
                    'status_code': response.status_code
                })
                log.info(f"Successfully updated AOM alarm rule: {resource['alarm_rule_name']}")
            except exceptions.ClientRequestException as e:
                log.error(
                    f"Failed to update AOM alarm rule: {resource['alarm_rule_name']}, "
                    f"error: {e.error_msg}")
                results.append({
                    'resource_id': resource['alarm_rule_name'],
                    'error': f"{e.status_code}:{e.error_code}:{e.error_msg}"
                })

        return results

    def _build_update_request(self, resource):
        """Build update request"""
        # Create request body
        body = AddOrUpdateAlarmRuleV4RequestBody()

        # Set alarm rule name - required
        body.alarm_rule_name = self.data.get('alarm_rule_name', resource['alarm_rule_name'])

        # Set alarm rule type - required
        body.alarm_rule_type = self.data.get('alarm_rule_type', resource['alarm_rule_type'])

        # Set optional parameters
        body.alarm_rule_description = self.data.get('alarm_rule_description',
                                                    resource['alarm_rule_description'])

        # Set rule enable status
        body.alarm_rule_enable = self.data.get('alarm_rule_enable', resource['alarm_rule_enable'])

        # Set Prometheus instance ID (optional)
        if 'prom_instance_id' in self.data:
            body.prom_instance_id = self.data['prom_instance_id']
        elif 'prom_instance_id' in resource:
            body.prom_instance_id = resource['prom_instance_id']

        # Set alarm notifications
        if 'alarm_notifications' in self.data:
            notification_data = self.data['alarm_notifications']
        else:
            notification_data = resource['alarm_notifications']

        notification = AlarmNotification()

        # Set notification type
        if 'notification_type' in notification_data:
            notification.notification_type = notification_data['notification_type']

        # Set route group enable status
        if 'route_group_enable' in notification_data:
            notification.route_group_enable = notification_data['route_group_enable']

        # Set route group rule name
        if 'route_group_rule' in notification_data:
            notification.route_group_rule = notification_data['route_group_rule']

        # Set notification enable status
        if 'notification_enable' in notification_data:
            notification.notification_enable = notification_data['notification_enable']

        # Set bind notification rule ID
        if 'bind_notification_rule_id' in notification_data:
            notification.bind_notification_rule_id = notification_data[
                'bind_notification_rule_id']

        # Set notify resolved status
        if 'notify_resolved' in notification_data:
            notification.notify_resolved = notification_data['notify_resolved']

        # Set notify triggered status
        if 'notify_triggered' in notification_data:
            notification.notify_triggered = notification_data['notify_triggered']

        # Set notification frequency
        if 'notify_frequency' in notification_data:
            notification.notify_frequency = notification_data['notify_frequency']

        body.alarm_notifications = notification

        # Set specifications according to alarm rule type
        if body.alarm_rule_type == 'metric':
            if 'metric_alarm_spec' in self.data:
                data_metric_alarm_spec = self.data['metric_alarm_spec']
            else:
                data_metric_alarm_spec = {}
            body.metric_alarm_spec = self._build_metric_alarm_spec(data_metric_alarm_spec,
                                                                   resource['metric_alarm_spec'])
        elif body.alarm_rule_type == 'event':
            if 'event_alarm_spec' in self.data:
                data_event_alarm_spec = self.data['event_alarm_spec']
            else:
                data_event_alarm_spec = {}
            body.event_alarm_spec = self._build_event_alarm_spec(data_event_alarm_spec,
                                                                 resource['event_alarm_spec'])

        # Create and return request
        return AddOrUpdateMetricOrEventAlarmRuleRequest(
            action_id="update-alarm-action",
            enterprise_project_id=resource['enterprise_project_id'],
            body=body
        )

    def _build_metric_alarm_spec(self, spec_data, resource_spec):
        """Build metric alarm specification"""
        metric_spec = MetricAlarmSpec()

        # Set monitor type
        if 'monitor_type' in spec_data:
            metric_spec.monitor_type = spec_data['monitor_type']
        elif 'monitor_type' in resource_spec:
            metric_spec.monitor_type = resource_spec['monitor_type']

        # Set alarm tags
        if 'alarm_tags' in spec_data and isinstance(spec_data['alarm_tags'], list):
            new_alarm_tags = []
            for alarm_tag in spec_data['alarm_tags']:
                new_tag = AlarmTags([], [], [])
                if isinstance(alarm_tag, dict):
                    for tag_item, tags in alarm_tag.items():
                        new_tags = []
                        if isinstance(tags, list):
                            for tag in tags:
                                if isinstance(tag, str):
                                    new_tags.append(tag)
                                if isinstance(tag, dict):
                                    if 'key' in tag and 'value' in tag:
                                        new_tags.append(f"{tag['key']}={tag['value']}")
                        if tag_item == 'auto_tags':
                            new_tag.auto_tags = new_tags
                        if tag_item == 'custom_tags':
                            new_tag.custom_tags = new_tags
                        if tag_item == 'custom_annotations':
                            new_tag.custom_annotations = new_tags
                new_alarm_tags.append(new_tag.to_dict())
            metric_spec.alarm_tags = new_alarm_tags
        else:
            metric_spec.alarm_tags = resource_spec['alarm_tags']

        # Set monitor objects
        if 'monitor_objects' in spec_data:
            metric_spec.monitor_objects = spec_data['monitor_objects']
        elif 'monitor_objects' in resource_spec:
            metric_spec.monitor_objects = resource_spec['monitor_objects']

        # Set recovery conditions
        if 'recovery_conditions' in spec_data:
            recovery = RecoveryCondition()
            recovery_data = spec_data['recovery_conditions']

            for key, value in recovery_data.items():
                setattr(recovery, key, value)

            metric_spec.recovery_conditions = recovery
        elif 'recovery_conditions' in resource_spec:
            recovery = RecoveryCondition()
            recovery_data = resource_spec['recovery_conditions']

            for key, value in recovery_data.items():
                setattr(recovery, key, value)

            metric_spec.recovery_conditions = recovery

        # Set trigger conditions
        if 'trigger_conditions' in spec_data and isinstance(spec_data['trigger_conditions'], list):
            conditions = []
            for condition_item in spec_data['trigger_conditions']:
                condition = TriggerCondition()
                for key, value in condition_item.items():
                    setattr(condition, key, value)
                conditions.append(condition)
            metric_spec.trigger_conditions = conditions
        elif 'trigger_conditions' in resource_spec and isinstance(
                resource_spec['trigger_conditions'], list):
            conditions = []
            for condition_item in resource_spec['trigger_conditions']:
                condition = TriggerCondition()
                for key, value in condition_item.items():
                    setattr(condition, key, value)
                conditions.append(condition)
            metric_spec.trigger_conditions = conditions

        return metric_spec

    def _build_event_alarm_spec(self, spec_data, resource_spec):
        """Build event alarm specification"""
        event_spec = EventAlarmSpec()

        # Set alarm rule source
        if 'alarm_source' in spec_data:
            event_spec.alarm_source = spec_data['alarm_source']
        elif 'alarm_source' in resource_spec:
            event_spec.alarm_source = resource_spec['alarm_source']

        # Set event source
        if 'event_source' in spec_data:
            event_spec.event_source = spec_data['event_source']
        elif 'event_source' in resource_spec:
            event_spec.event_source = resource_spec['event_source']

        # Set monitor objects
        if 'monitor_objects' in spec_data:
            event_spec.monitor_objects = spec_data['monitor_objects']
        elif 'monitor_objects' in resource_spec:
            event_spec.monitor_objects = resource_spec['monitor_objects']

        # Set trigger conditions
        if 'trigger_conditions' in spec_data and isinstance(spec_data['trigger_conditions'], list):
            conditions = []
            for condition_item in spec_data['trigger_conditions']:
                condition = EventTriggerCondition()
                for key, value in condition_item.items():
                    setattr(condition, key, value)
                conditions.append(condition)
            event_spec.trigger_conditions = conditions
        elif ('trigger_conditions' in resource_spec and
              isinstance(resource_spec['trigger_conditions'], list)):
            conditions = []
            for condition_item in resource_spec['trigger_conditions']:
                condition = EventTriggerCondition()
                for key, value in condition_item.items():
                    setattr(condition, key, value)
                conditions.append(condition)
            event_spec.trigger_conditions = conditions

        return event_spec

    def perform_action(self, resource):
        pass


@AomAlarm.action_registry.register('add')
class AddAlarmRule(HuaweiCloudBaseAction):
    """Add AOM Alarm Rule

    Add AOM metric or event alarm rule according to API documentation

    :example:

    .. code-block:: yaml

        policies:
          - name: add-metric-alarm
            resource: huaweicloud.aom-alarm
            actions:
              - type: add
                alarm_rule_name: "new-metric-alarm"
                alarm_rule_description: "New metric alarm rule"
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
                alarm_rule_description: "New event alarm rule"
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
        enterprise_project_id={'type': 'string'},
        required=['alarm_rule_name', 'alarm_rule_type']
    )

    def process(self, resources):
        # Adding alarm rule doesn't need existing resources, we directly create a new rule
        client = self.manager.get_client()

        try:
            # Build request
            request = self._build_add_request()

            # Call API to create alarm rule
            response = client.add_or_update_metric_or_event_alarm_rule(request)

            log.info(f"Successfully added AOM alarm rule: {self.data['alarm_rule_name']}")
            return [{
                'alarm_rule_name': self.data['alarm_rule_name'],
                'status_code': response.status_code
            }]
        except exceptions.ClientRequestException as e:
            log.error(
                f"Failed to add AOM alarm rule: {self.data['alarm_rule_name']}, "
                f"error: {e.error_msg}")
            return [{
                'alarm_rule_name': self.data['alarm_rule_name'],
                'error': f"{e.status_code}:{e.error_code}:{e.error_msg}"
            }]

    def _build_add_request(self):
        """Build add request"""
        # Create request body
        body = AddOrUpdateAlarmRuleV4RequestBody()

        # Set alarm rule name - required
        body.alarm_rule_name = self.data['alarm_rule_name']

        # Set alarm rule type - required
        body.alarm_rule_type = self.data['alarm_rule_type']

        # Set optional parameters
        if 'alarm_rule_description' in self.data:
            body.alarm_rule_description = self.data['alarm_rule_description']

        if 'alarm_rule_enable' in self.data:
            body.alarm_rule_enable = self.data['alarm_rule_enable']

        # Set Prometheus instance ID (optional)
        if 'prom_instance_id' in self.data:
            body.prom_instance_id = self.data['prom_instance_id']

        # Set alarm notifications
        if 'alarm_notifications' in self.data:
            notification = AlarmNotification()

            notification_data = self.data['alarm_notifications']

            # Set notification type
            if 'notification_type' in notification_data:
                notification.notification_type = notification_data['notification_type']

            # Set route group enable status
            if 'route_group_enable' in notification_data:
                notification.route_group_enable = notification_data['route_group_enable']

            # Set route group rule name
            if 'route_group_rule' in notification_data:
                notification.route_group_rule = notification_data['route_group_rule']

            # Set notification enable status
            if 'notification_enable' in notification_data:
                notification.notification_enable = notification_data['notification_enable']

            # Set bind notification rule ID
            if 'bind_notification_rule_id' in notification_data:
                notification.bind_notification_rule_id = notification_data[
                    'bind_notification_rule_id']

            # Set notify resolved status
            if 'notify_resolved' in notification_data:
                notification.notify_resolved = notification_data['notify_resolved']

            # Set notify triggered status
            if 'notify_triggered' in notification_data:
                notification.notify_triggered = notification_data['notify_triggered']

            # Set notification frequency
            if 'notify_frequency' in notification_data:
                notification.notify_frequency = notification_data['notify_frequency']

            body.alarm_notifications = notification

        # Set specifications according to alarm rule type
        if body.alarm_rule_type == 'metric' and 'metric_alarm_spec' in self.data:
            body.metric_alarm_spec = self._build_metric_alarm_spec(self.data['metric_alarm_spec'])
        elif body.alarm_rule_type == 'event' and 'event_alarm_spec' in self.data:
            body.event_alarm_spec = self._build_event_alarm_spec(self.data['event_alarm_spec'])

        if "enterprise_project_id" in self.data:
            enterprise_project_id = self.data['enterprise_project_id']
        else:
            enterprise_project_id = "0"

        # Create and return request
        return AddOrUpdateMetricOrEventAlarmRuleRequest(
            action_id="add-alarm-action",
            enterprise_project_id=enterprise_project_id,
            body=body
        )

    def _build_metric_alarm_spec(self, spec_data):
        """Build metric alarm specification"""
        metric_spec = MetricAlarmSpec()

        # Set monitor type
        if 'monitor_type' in spec_data:
            metric_spec.monitor_type = spec_data['monitor_type']

        # Set alarm tags
        if 'alarm_tags' in spec_data and isinstance(spec_data['alarm_tags'], list):
            new_alarm_tags = []
            for alarm_tag in spec_data['alarm_tags']:
                new_tag = AlarmTags([], [], [])
                if isinstance(alarm_tag, dict):
                    for tag_item, tags in alarm_tag.items():
                        new_tags = []
                        if isinstance(tags, list):
                            for tag in tags:
                                if isinstance(tag, str):
                                    new_tags.append(tag)
                                if isinstance(tag, dict):
                                    if 'key' in tag and 'value' in tag:
                                        new_tags.append(f"{tag['key']}={tag['value']}")
                        if tag_item == 'auto_tags':
                            new_tag.auto_tags = new_tags
                        if tag_item == 'custom_tags':
                            new_tag.custom_tags = new_tags
                        if tag_item == 'custom_annotations':
                            new_tag.custom_annotations = new_tags
                new_alarm_tags.append(new_tag.to_dict())
            metric_spec.alarm_tags = new_alarm_tags
        else:
            metric_spec.alarm_tags = [AlarmTags([], [], []).to_dict()]

        # Set monitor objects
        if 'monitor_objects' in spec_data:
            metric_spec.monitor_objects = spec_data['monitor_objects']

        # Set recovery conditions
        if 'recovery_conditions' in spec_data:
            recovery = RecoveryCondition()
            recovery_data = spec_data['recovery_conditions']

            for key, value in recovery_data.items():
                setattr(recovery, key, value)

            metric_spec.recovery_conditions = recovery

        # Set trigger conditions
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
        """Build event alarm specification"""
        event_spec = EventAlarmSpec()

        # Set alarm rule source
        if 'alarm_source' in spec_data:
            event_spec.alarm_source = spec_data['alarm_source']

        # Set event source
        if 'event_source' in spec_data:
            event_spec.event_source = spec_data['event_source']

        # Set monitor objects
        if 'monitor_objects' in spec_data:
            event_spec.monitor_objects = spec_data['monitor_objects']

        # Set trigger conditions
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
        pass
