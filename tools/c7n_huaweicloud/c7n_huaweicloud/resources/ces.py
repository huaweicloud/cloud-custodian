# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import os

from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.filters.ces import AlarmNameSpaceAndMetricFilter
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from huaweicloudsdkces.v2 import UpdateAlarmNotificationsRequest, Notification, \
    PutAlarmNotificationReq, BatchEnableAlarmRulesRequest, BatchEnableAlarmsRequestBody, \
    CreateAlarmRulesRequest, Policy, PostAlarmsReqV2, AlarmType
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdksmn.v2 import PublishMessageRequest, PublishMessageRequestBody

from c7n.actions import BaseAction
from c7n.filters.missing import Missing
from c7n.utils import type_schema, local_session

log = logging.getLogger("custodian.huaweicloud.resources.ces-alarm")


@resources.register('ces-alarm')
class Alarm(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'ces'
        enum_spec = ("list_alarm_rules", 'alarms', 'offset')
        id = 'alarm_id'
        tag_resource_type = None


Alarm.filter_registry.register('missing', Missing)
Alarm.filter_registry.register('alarm-namespace-metric', AlarmNameSpaceAndMetricFilter)


@Alarm.action_registry.register("alarm-update-notification")
class AlarmUpdateNotification(HuaweiCloudBaseAction):
    """Update CES Alarm notification settings.

    :Example:

    .. code-block:: yaml

    policies:
      - name: ces-alarm-have-smn-check
        description: "Filter all alarm rules that do not have notifications enabled.
                      Update the SMN notifications corresponding to these alarm settings"
        resource: huaweicloud.ces-alarm
        filters:
          - type: value
            key: notification_enabled
            value: false
        actions:
          - type: alarm-update-notification
            parameters:
              action_type: "notification"
              notification_list:
                - "urn:smn:cn-north-4:xxxxx:CES_notification_xxxxxxx"

    """

    schema = type_schema(
        "alarm-update-notification",
        required=["parameters"],
        **{
            "parameters": {
                "type": "object",
                "required": ["notification_list", "action_type"],
                "properties": {
                    "notification_list": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "action_type": {
                        "type": "string",
                        "enum": ["notification"]
                    }
                }
            }
        }
    )

    def perform_action(self, resource):
        params = self.data.get('parameters', {})
        action_type = params.get('action_type', 'notification')
        response = None
        client = local_session(self.manager.session_factory).client('ces')
        request = UpdateAlarmNotificationsRequest()
        request.alarm_id = resource["id"]
        list_ok_notifications_body = [
            Notification(
                type=action_type,
                notification_list=params['notification_list']
            )
        ]
        list_alarm_notifications_body = [
            Notification(
                type=action_type,
                notification_list=params['notification_list']
            )
        ]
        request.body = PutAlarmNotificationReq(
            notification_end_time="23:59",
            notification_begin_time="00:00",
            ok_notifications=list_ok_notifications_body,
            alarm_notifications=list_alarm_notifications_body,
            notification_enabled=True
        )
        try:
            response = client.update_alarm_notifications(request)
            log.info(f"Update alarm notification {response}")
        except exceptions.ClientRequestException as e:
            log.error(f"Update alarm notification failed: {e.error_msg}")
        return response


@Alarm.action_registry.register("batch-start-alarm-rules")
class BatchStartStoppedAlarmRules(BaseAction):
    """Update CES Alarm all start.

    :Example:

    .. code-block:: yaml

    policies:
      - name: alarm-action-enabled-check
        description: "Verify that all alarm rules must be enabled and enable the disabled alarms."
        resource: huaweicloud.ces-alarm
        filters:
          - type: value
            key: enabled
            value: false
        actions:
          - type: batch-start-alarm-rules
            parameters:
              subject: "CES alarm not activated Check email"
              message: "You have the following alarms that have not been started,
                      please check the system.The tasks have been started,
                      please log in to the system and check again."
              notification_list:
                - "urn:smn:cn-north-4:xxxxx:CES_notification_xxxxxxx"

    """

    schema = type_schema(
        "batch-start-alarm-rules",
        required=["parameters"],
        **{
            "parameters": {
                "type": "object",
                "required": ["notification_list", "subject", "message"],
                "properties": {
                    "notification_list": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "subject": {"type": "string"},
                    "message": {"type": "string"}
                }
            }
        }
    )

    def process(self, resources):
        if len(resources) == 0:
            return
        response = None
        batch_enable_alarm_rule_request = BatchEnableAlarmRulesRequest()
        list_alarm_ids = [str(item["id"]) for item in resources if "id" in item]
        batch_enable_alarm_rule_request.body = BatchEnableAlarmsRequestBody(
            alarm_enabled=True,
            alarm_ids=list_alarm_ids
        )
        params = self.data.get('parameters', {})
        subject = params.get('subject', 'subject')
        message = params.get('message', 'message')
        id_list = '\n'.join([f"- {alarm_id}" for alarm_id in list_alarm_ids])
        message += f"\nalarm list:\n{id_list}"
        message += f"\nregion: {os.getenv('HUAWEI_DEFAULT_REGION')}"
        body = PublishMessageRequestBody(
            subject=subject,
            message=message
        )
        try:
            client = local_session(self.manager.session_factory).client('ces')
            update_response = client.batch_enable_alarm_rules(batch_enable_alarm_rule_request)
            log.info(f"Batch start alarm, response: {update_response}")
            client = local_session(self.manager.session_factory).client('smn')
            for topic_urn in params['notification_list']:
                publish_message_request = PublishMessageRequest(topic_urn=topic_urn, body=body)
                log.info(f"Message send, request: {publish_message_request}")
                publish_message_response = client.publish_message(publish_message_request)
                log.info(f"Message send, response: {publish_message_response}")
        except exceptions.ClientRequestException as e:
            log.error(f"Batch start alarm failed: {e.error_msg}")
        return response


@Alarm.action_registry.register("create-kms-event-alarm-rule")
class CreateKmsEventAlarmRule(BaseAction):
    """Check CES isn't configured KMS change alarm rule.

    :Example:

    .. code-block:: yaml

    policies:
      - name: alarm-kms-disable-or-delete-key
        description: "Check whether the monitoring alarm for events that monitor
                      KMS disabling or scheduledkey deletion is configured.
                      If not, create the corresponding alarm."
        resource: huaweicloud.ces-alarm
        filters:
            - type: missing
              policy:
                resource: huaweicloud.ces-alarm
                filters:
                  - type: value
                    key: enabled
                    value: true
                    op: eq
                  - type: value
                    key: type
                    value: "EVENT.SYS"
                    op: eq
                  - type: value
                    key: namespace
                    value: "SYS.KMS"
                    op: eq
                  - type: list-item
                    key: resources
                    attrs:
                      - type: value
                        key: "dimensions"
                        value: []
                        op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'retireGrant')"
                    value: true
                    op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'revokeGrant')"
                    value: true
                    op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'disableKey')"
                    value: true
                    op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'scheduleKeyDeletion')"
                    value: true
                    op: eq
        actions:
          - type: create-kms-event-alarm-rule
            parameters:
              action_type: "notification"
              notification_list:
                - "urn:smn:cn-north-4:xxxxx:CES_notification_xxxxxxx"
          - type: notify-by-smn
            parameters:
              subject: "CES alarm not configured KMS event alarm"
              message: "The system detected that you have not configured KMS
                        event monitoring alarms, and has automatically created one for you.
                        Please log in to the system to view it."
              notification_list:
                - "urn:smn:cn-north-4:xxxxx:CES_notification_xxxxxxx"

    """

    schema = type_schema(
        "create-kms-event-alarm-rule",
        required=["parameters"],
        **{
            "parameters": {
                "type": "object",
                "required": ["notification_list", "action_type"],
                "properties": {
                    "notification_list": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "action_type": {
                        "type": "string",
                        "enum": ["notification"]
                    }
                }
            }
        }
    )

    def process(self, resources):
        params = self.data.get('parameters', {})
        action_type = params.get('action_type', 'notification')
        client = local_session(self.manager.session_factory).client('ces')
        request = CreateAlarmRulesRequest()

        list_ok_notifications_body = [
            Notification(
                type=action_type,
                notification_list=params['notification_list']
            )
        ]
        list_alarm_notifications_body = [
            Notification(
                type=action_type,
                notification_list=params['notification_list']
            )
        ]
        list_policies_body = [
            Policy(
                metric_name="retireGrant",
                period=0,
                filter="average",
                comparison_operator=">=",
                value=1,
                unit="count",
                count=1,
                suppress_duration=0,
                level=2
            ),
            Policy(
                metric_name="revokeGrant",
                period=0,
                filter="average",
                comparison_operator=">=",
                value=1,
                unit="count",
                count=1,
                suppress_duration=0,
                level=2
            ),
            Policy(
                metric_name="disableKey",
                period=0,
                filter="average",
                comparison_operator=">=",
                value=1,
                unit="count",
                count=1,
                suppress_duration=0,
                level=2
            ),
            Policy(
                metric_name="scheduleKeyDeletion",
                period=0,
                filter="average",
                comparison_operator=">=",
                value=1,
                unit="count",
                count=1,
                suppress_duration=0,
                level=2
            )
        ]
        request.body = PostAlarmsReqV2(
            notification_enabled=True,
            enabled=True,
            enterprise_project_id="0",
            notification_end_time="23:59",
            notification_begin_time="00:00",
            ok_notifications=list_ok_notifications_body,
            alarm_notifications=list_alarm_notifications_body,
            type=AlarmType.EVENT_SYS,
            policies=list_policies_body,
            namespace="SYS.KMS",
            description="alarm-kms-change",
            name="alarm-kms-change",
            resources=[]
        )
        try:
            response = client.create_alarm_rules(request)
            log.info(f"Create alarm {response}")
        except exceptions.ClientRequestException as e:
            log.error(f"Create alarm failed: {e.error_msg}")


@Alarm.action_registry.register("create-obs-event-alarm-rule")
class CreateObsEventAlarmRule(BaseAction):
    """Check CES isn't configured OBS change alarm rule.

    :Example:

    .. code-block:: yaml

    policies:
      - name: alarm-obs-bucket-policy-change
        description: "Check whether the alarm for the OBS bucket policy change
                     event is configured. If not, create a corresponding alarm."
        resource: huaweicloud.ces-alarm
        filters:
            - type: missing
              policy:
                resource: huaweicloud.ces-alarm
                filters:
                  - type: value
                    key: enabled
                    value: true
                    op: eq
                  - type: value
                    key: type
                    value: "EVENT.SYS"
                    op: eq
                  - type: value
                    key: namespace
                    value: "SYS.OBS"
                    op: eq
                  - type: list-item
                    key: resources
                    attrs:
                      - type: value
                        key: "dimensions"
                        value: []
                        op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'setBucketPolicy')"
                    value: true
                    op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'setBucketAcl')"
                    value: true
                    op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'deleteBucketPolicy')"
                    value: true
                    op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'deleteBucket')"
                    value: true
                    op: eq
        actions:
          - type: create-obs-event-alarm-rule
            parameters:
              action_type: "notification"
              notification_list:
                - "urn:smn:cn-north-4:xxxxx:CES_notification_xxxxxxx"

    """

    schema = type_schema(
        "create-obs-event-alarm-rule",
        required=["parameters"],
        **{
            "parameters": {
                "type": "object",
                "required": ["notification_list", "action_type"],
                "properties": {
                    "notification_list": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "action_type": {
                        "type": "string",
                        "enum": ["notification"]
                    }
                }
            }
        }
    )

    def process(self, resources):
        params = self.data.get('parameters', {})
        action_type = params.get('action_type', 'notification')
        client = local_session(self.manager.session_factory).client('ces')
        request = CreateAlarmRulesRequest()

        list_ok_notifications_body = [
            Notification(
                type=action_type,
                notification_list=params['notification_list']
            )
        ]
        list_alarm_notifications_body = [
            Notification(
                type=action_type,
                notification_list=params['notification_list']
            )
        ]
        list_policies_body = [
            Policy(
                metric_name="setBucketPolicy",
                period=0,
                filter="average",
                comparison_operator=">=",
                value=1,
                unit="count",
                count=1,
                suppress_duration=0,
                level=2
            ),
            Policy(
                metric_name="setBucketAcl",
                period=0,
                filter="average",
                comparison_operator=">=",
                value=1,
                unit="count",
                count=1,
                suppress_duration=0,
                level=2
            ),
            Policy(
                metric_name="deleteBucketPolicy",
                period=0,
                filter="average",
                comparison_operator=">=",
                value=1,
                unit="count",
                count=1,
                suppress_duration=0,
                level=2
            ),
            Policy(
                metric_name="deleteBucket",
                period=0,
                filter="average",
                comparison_operator=">=",
                value=1,
                unit="count",
                count=1,
                suppress_duration=0,
                level=2
            )
        ]
        request.body = PostAlarmsReqV2(
            notification_enabled=True,
            enabled=True,
            enterprise_project_id="0",
            notification_end_time="23:59",
            notification_begin_time="00:00",
            ok_notifications=list_ok_notifications_body,
            alarm_notifications=list_alarm_notifications_body,
            type=AlarmType.EVENT_SYS,
            policies=list_policies_body,
            namespace="SYS.OBS",
            description="alarm-obs-change",
            name="alarm-obs-change",
            resources=[]
        )
        try:
            response = client.create_alarm_rules(request)
            log.info(f"Create alarm {response}")
        except exceptions.ClientRequestException as e:
            log.error(f"Create alarm failed: {e.error_msg}")


@Alarm.action_registry.register("notify-by-smn")
class NotifyBySMN(BaseAction):
    """Notify user by huawei cloud SMN.

    :Example:

    .. code-block:: yaml

    policies:
      - name: alarm-resource-check
        description: "Check if the specified resource type is not bound to the specified
                      indicator CES alarm"
        resource: huaweicloud.ces-alarm
        filters:
            - type: missing
              policy:
                resource: huaweicloud.ces-alarm
                filters:
                  - type: alarm-namespace-metric
                    namespaces: ["SYS.KMS"]
                    metric_names: ["retireGrant", "disableKey"]
                    count: [1, 2, 3, 4, 5, 10, 15, 30, 60, 90, 120, 180]
                    period: [0, 1, 300, 1200, 3600, 14400, 86400]
                    comparison_operator: ['>', '>=', '=', '!=', '<', '<=',
                                          'cycle_decrease', 'cycle_increase', 'cycle_wave']
        actions:
          - type: notify-by-smn
            parameters:
              subject: "CES alarm not configured specified resource"
              message: "Currently, the Huawei Cloud CES system has not configured execution
                        resource alarms. Please log in to the system to view the configuration."
              notification_list:
                - "urn:smn:cn-north-4:xxxxx:CES_notification_xxxxxxx"

    """

    schema = type_schema(
        "notify-by-smn",
        required=["parameters"],
        **{
            "parameters": {
                "type": "object",
                "required": ["notification_list", "subject", "message"],
                "properties": {
                    "notification_list": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "subject": {"type": "string"},
                    "message": {"type": "string"}
                }
            }
        }
    )

    def process(self, resources):
        params = self.data.get('parameters', {})
        subject = params.get('subject', 'subject')
        message = params.get('message', 'message')
        list_alarm_ids = [str(item["id"]) for item in resources if "id" in item]
        id_list = '\n'.join([f"- {alarm_id}" for alarm_id in list_alarm_ids])
        if len(id_list) != 0:
            message += f"\nalarm list:\n{id_list}"
        message += f"\nregion: {os.getenv('HUAWEI_DEFAULT_REGION')}"
        body = PublishMessageRequestBody(
            subject=subject,
            message=message
        )
        for topic_urn in params['notification_list']:
            publish_message_request = PublishMessageRequest(topic_urn=topic_urn, body=body)
            log.info(f"Message send, request: {publish_message_request}")
            try:
                client = local_session(self.manager.session_factory).client('smn')
                publish_message_response = client.publish_message(publish_message_request)
                log.info(f"Message send, response: {publish_message_response}")
            except exceptions.ClientRequestException as e:
                log.error(f"Message send, failed: {e.error_msg}")


@Alarm.action_registry.register("create-vpc-event-alarm-rule")
class CreateVpcEventAlarmRule(BaseAction):
    """Check CES isn't configured VPC change alarm rule.

    :Example:

    .. code-block:: yaml

    policies:
      - name: alarm-vpc-change
        description: "Check whether the event monitoring alarm for monitoring VPC changes
                      is configured. If not, create the corresponding alarm."
        resource: huaweicloud.ces-alarm
        filters:
            - type: missing
              policy:
                resource: huaweicloud.ces-alarm
                filters:
                  - type: value
                    key: enabled
                    value: true
                    op: eq
                  - type: value
                    key: type
                    value: "EVENT.SYS"
                    op: eq
                  - type: value
                    key: namespace
                    value: "SYS.VPC"
                    op: eq
                  - type: list-item
                    key: resources
                    attrs:
                      - type: value
                        key: "dimensions"
                        value: []
                        op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'modifyVpc')"
                    value: true
                    op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'modifySubnet')"
                    value: true
                    op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'deleteSubnet')"
                    value: true
                    op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'modifyBandwidth')"
                    value: true
                    op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'deleteVpn')"
                    value: true
                    op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'modifyVpc')"
                    value: true
                    op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'modifyVpn')"
                    value: true
                    op: eq
        actions:
          - type: create-vpc-event-alarm-rule
            parameters:
              action_type: "notification"
              notification_list:
                - "urn:smn:cn-north-4:xxxxx:CES_notification_xxxxxxx"

    """

    schema = type_schema(
        "create-vpc-event-alarm-rule",
        required=["parameters"],
        **{
            "parameters": {
                "type": "object",
                "required": ["notification_list", "action_type"],
                "properties": {
                    "notification_list": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "action_type": {
                        "type": "string",
                        "enum": ["notification"]
                    }
                }
            }
        }
    )

    def process(self, resources):
        params = self.data.get('parameters', {})
        action_type = params.get('action_type', 'notification')
        client = local_session(self.manager.session_factory).client('ces')
        request = CreateAlarmRulesRequest()

        list_ok_notifications_body = [
            Notification(
                type=action_type,
                notification_list=params['notification_list']
            )
        ]
        list_alarm_notifications_body = [
            Notification(
                type=action_type,
                notification_list=params['notification_list']
            )
        ]
        list_policies_body = [
            Policy(
                metric_name="deleteVpc",
                period=0,
                filter="average",
                comparison_operator=">=",
                value=1,
                unit="count",
                count=1,
                suppress_duration=0,
                level=2
            ),
            Policy(
                metric_name="modifyVpn",
                period=0,
                filter="average",
                comparison_operator=">=",
                value=1,
                unit="count",
                count=1,
                suppress_duration=0,
                level=2
            ),
            Policy(
                metric_name="deleteVpn",
                period=0,
                filter="average",
                comparison_operator=">=",
                value=1,
                unit="count",
                count=1,
                suppress_duration=0,
                level=2
            ),
            Policy(
                metric_name="modifyVpc",
                period=0,
                filter="average",
                comparison_operator=">=",
                value=1,
                unit="count",
                count=1,
                suppress_duration=0,
                level=2
            ),
            Policy(
                metric_name="deleteSubnet",
                period=0,
                filter="average",
                comparison_operator=">=",
                value=1,
                unit="count",
                count=1,
                suppress_duration=0,
                level=2
            ),
            Policy(
                metric_name="modifySubnet",
                period=0,
                filter="average",
                comparison_operator=">=",
                value=1,
                unit="count",
                count=1,
                suppress_duration=0,
                level=2
            ),
            Policy(
                metric_name="modifyBandwidth",
                period=0,
                filter="average",
                comparison_operator=">=",
                value=1,
                unit="count",
                count=1,
                suppress_duration=0,
                level=2
            )
        ]
        request.body = PostAlarmsReqV2(
            notification_enabled=True,
            enabled=True,
            enterprise_project_id="0",
            notification_end_time="23:59",
            notification_begin_time="00:00",
            ok_notifications=list_ok_notifications_body,
            alarm_notifications=list_alarm_notifications_body,
            type=AlarmType.EVENT_SYS,
            policies=list_policies_body,
            namespace="SYS.VPC",
            description="alarm-vpc-change",
            name="alarm-vpc-change",
            resources=[]
        )
        try:
            response = client.create_alarm_rules(request)
            log.info(f"Create alarm {response}")
        except exceptions.ClientRequestException as e:
            log.error(f"Create alarm failed: {e.error_msg}")
