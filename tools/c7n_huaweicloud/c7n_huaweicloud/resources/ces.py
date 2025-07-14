# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import os

from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.filters.ces import AlarmNameSpaceAndMetricFilter, AlarmNotificationFilter
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from huaweicloudsdkces.v2 import UpdateAlarmNotificationsRequest, Notification, \
    PutAlarmNotificationReq, BatchEnableAlarmRulesRequest, BatchEnableAlarmsRequestBody, \
    CreateAlarmRulesRequest, Policy, PostAlarmsReqV2, AlarmType, ListAlarmRulesRequest
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdksmn.v2 import PublishMessageRequest, PublishMessageRequestBody, \
    ListTopicsRequest

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

    def get_resources(self, query):
        return self.get_api_resources(query)

    def _fetch_resources(self, query):
        return self.get_api_resources(query)

    def get_api_resources(self, resource_ids):
        session = local_session(self.session_factory)
        client = session.client(self.resource_type.service)
        resources = []
        offset, limit = 0, 100
        while True:
            request = ListAlarmRulesRequest()
            request.offset = offset
            request.limit = limit
            try:
                response = client.list_alarm_rules(request)
                current_resources = eval(
                    str(response.alarms)
                        .replace("null", "None")
                        .replace("false", "False")
                        .replace("true", "True")
                )
                for resource in current_resources:
                    if "id" not in resource:  # 检查是否缺少id字段
                        if "alarm_id" in resource:  # 使用alarm_id填充
                            resource["id"] = resource["alarm_id"]
                        else:
                            log.warning(f"Resource missing both id and alarm_id: {resource}")
                            resource["id"] = f"generated_{hash(str(resource))}"
                    resources.append(resource)
            except exceptions.ClientRequestException as e:
                log.error(f"[actions]- list_alarm_rules - The resource:ces-alarm "
                          f"with id:[] query alarm rules is failed. cause: {e.error_msg} ")
                raise e

            offset += limit
            if not response.count or offset >= len(response.alarms):
                break

        return resources


Alarm.filter_registry.register('missing', Missing)
Alarm.filter_registry.register('alarm-namespace-metric', AlarmNameSpaceAndMetricFilter)
Alarm.filter_registry.register('alarm-notification', AlarmNotificationFilter)


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
          - type: alarm-notification
            notification_list: ["urn:smn:cn-north-4:xxxxx:CES_notification_xxxxxxx"]
        actions:
          - type: alarm-update-notification
            parameters:
              action_type: "notification"
              notification_name: "Email_Notification_to_Owner"
              notification_list:
                - "urn:smn:cn-north-4:xxxxx:CES_notification_xxxxxxx"

    """

    schema = type_schema(
        "alarm-update-notification",
        required=["parameters"],
        **{
            "parameters": {
                "type": "object",
                "required": ["action_type"],
                "properties": {
                    "notification_name": {
                        "type": "string",
                    },
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
        actionName = "alarm-update-notification"
        resourceType = "ces-alarm"
        doSomeThing = "Update alarm notification"
        alarm_id = resource["alarm_id"]
        params = self.data.get('parameters', {})
        action_type = params.get('action_type', 'notification')
        response = None
        alarm_topic_urns = None
        ok_topic_urns = None
        alarm_contact_notification_list = None
        ok_contact_notification_list = None
        smnClient = local_session(self.manager.session_factory).client('smn')
        notification_name = params.get('notification_name')
        notification_list = params.get('notification_list')
        if notification_name is not None:
            request = ListTopicsRequest()
            request.name = notification_name
            response = smnClient.list_topics(request)
            alarm_topic_urns = [topic.topic_urn for topic in response.topics]
            ok_topic_urns = [topic.topic_urn for topic in response.topics]
        elif notification_list is not None:
            alarm_topic_urns = notification_list
            ok_topic_urns = notification_list
        else:
            log.error(f"[actions]- {actionName}- The resource:{resourceType} "
                      f"with id:[{alarm_id}]  {doSomeThing}  is failed. cause: "
                      f"Update alarm notification need setting notification_name, "
                      f"notification_list param")
            raise RuntimeError("missing notification_name, notification_list param")
        alarm_notifications = resource["alarm_notifications"]
        for item in alarm_notifications:
            if item["type"] == "notification":
                alarm_topic_urns += item["notification_list"]
            if item["type"] == "contact":
                alarm_contact_notification_list = item["notification_list"]

        ok_notifications = resource["ok_notifications"]
        for item in ok_notifications:
            if item["type"] == "notification":
                ok_topic_urns += item["notification_list"]
            if item["type"] == "contact":
                ok_contact_notification_list = item["notification_list"]

        request = UpdateAlarmNotificationsRequest()
        request.alarm_id = resource["alarm_id"]
        list_ok_notifications_body = [
            Notification(
                type=action_type,
                notification_list=ok_topic_urns
            )
        ]
        if ok_contact_notification_list is not None:
            ok_notifications = Notification(
                type="contact",
                notification_list=ok_contact_notification_list
            )
            list_ok_notifications_body.append(ok_notifications)

        list_alarm_notifications_body = [
            Notification(
                type=action_type,
                notification_list=alarm_topic_urns
            )
        ]
        if alarm_contact_notification_list is not None:
            alarm_notifications = Notification(
                type="contact",
                notification_list=alarm_contact_notification_list
            )
            list_alarm_notifications_body.append(alarm_notifications)

        request.body = PutAlarmNotificationReq(
            notification_end_time="23:59",
            notification_begin_time="00:00",
            ok_notifications=list_ok_notifications_body,
            alarm_notifications=list_alarm_notifications_body,
            notification_enabled=True
        )
        try:
            client = local_session(self.manager.session_factory).client('ces')
            response = client.update_alarm_notifications(request)
            log.info(f"[actions]- {actionName} The resource:{resourceType} "
                     f"with id:[{alarm_id}]  {doSomeThing}  is success. ")
        except exceptions.ClientRequestException as e:
            log.error(f"[actions]- {actionName}- The resource:{resourceType} "
                      f"with id:[{alarm_id}]  {doSomeThing}  is failed. cause: {e.error_msg} ")
            raise e
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

    """

    schema = type_schema(
        "batch-start-alarm-rules"
    )

    def process(self, resources):
        if len(resources) == 0:
            return
        response = None
        actionName = "batch-start-alarm-rules"
        resourceType = "ces-alarm"
        doSomeThing = "Batch start alarm rules"
        batch_enable_alarm_rule_request = BatchEnableAlarmRulesRequest()
        list_alarm_ids = [str(item["alarm_id"]) for item in resources if "alarm_id" in item]
        batch_enable_alarm_rule_request.body = BatchEnableAlarmsRequestBody(
            alarm_enabled=True,
            alarm_ids=list_alarm_ids
        )
        try:
            client = local_session(self.manager.session_factory).client('ces')
            client.batch_enable_alarm_rules(batch_enable_alarm_rule_request)
            log.info(f"[actions]- {actionName} The resource:{resourceType} "
                     f"with id:[{list_alarm_ids}]  {doSomeThing}  is success. ")
        except exceptions.ClientRequestException as e:
            log.error(f"[actions]- {actionName}- The resource:{resourceType} "
                      f"with id:[{list_alarm_ids}]  {doSomeThing}  is failed. "
                      f"cause: {e.error_msg} ")
            raise e
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
        actionName = "create-kms-event-alarm-rule"
        resourceType = "ces-alarm"
        doSomeThing = "Create KMS event alarm rule"
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
            log.info(f"[actions]- {actionName} The resource:{resourceType} "
                     f"with id:[{response.alarm_id}]  {doSomeThing}  is success. ")
        except exceptions.ClientRequestException as e:
            log.error(f"[actions]- {actionName}- The resource:{resourceType} "
                      f"with id:alarm-kms-change  {doSomeThing}  is failed. cause: {e.error_msg} ")
            raise e


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
        actionName = "create-obs-event-alarm-rule"
        resourceType = "ces-alarm"
        doSomeThing = "Create OBS event alarm rule"
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
            log.info(f"[actions]- {actionName} The resource:{resourceType} "
                     f"with id:[{response.alarm_id}]  {doSomeThing}  is success. ")
        except exceptions.ClientRequestException as e:
            log.error(f"[actions]- {actionName}- The resource:{resourceType} "
                      f"with id:alarm-obs-change  {doSomeThing}  is failed. cause: {e.error_msg} ")
            raise e


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
        actionName = "notify-by-smn"
        resourceType = "ces-alarm"
        doSomeThing = "Notify by SMN"
        params = self.data.get('parameters', {})
        subject = params.get('subject', 'subject')
        message = params.get('message', 'message')
        list_alarm_ids = [str(item["alarm_id"]) for item in resources if "alarm_id" in item]
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
            try:
                client = local_session(self.manager.session_factory).client('smn')
                client.publish_message(publish_message_request)
                log.info(f"[actions]- {actionName} The resource:{resourceType} "
                         f"with id:[{list_alarm_ids}]  {doSomeThing}  is success. ")
            except exceptions.ClientRequestException as e:
                log.error(f"[actions]- {actionName}- The resource:{resourceType} "
                          f"with id:[{list_alarm_ids}]  {doSomeThing}  is failed. "
                          f"cause: {e.error_msg} ")
                raise e


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
        actionName = "create-vpc-event-alarm-rule"
        resourceType = "ces-alarm"
        doSomeThing = "Create VPC event alarm rule"
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
            log.info(f"[actions]- {actionName} The resource:{resourceType} "
                     f"with id:[{response.alarm_id}]  {doSomeThing}  is success. ")
        except exceptions.ClientRequestException as e:
            log.error(f"[actions]- {actionName}- The resource:{resourceType} "
                      f"with id:alarm-vpc-change  {doSomeThing}  is failed. cause: {e.error_msg} ")
            raise e
