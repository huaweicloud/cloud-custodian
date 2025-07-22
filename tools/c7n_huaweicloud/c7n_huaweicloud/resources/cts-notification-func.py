# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from huaweicloudsdkcts.v3 import (UpdateNotificationRequest, UpdateNotificationRequestBody,
                                  NotificationUsers, Operations)
from huaweicloudsdkcore.exceptions import exceptions

from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

log = logging.getLogger("custodian.huaweicloud.resources.cts")


@resources.register('cts-notification-func')
class Notification(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'cts-notification-func'
        enum_spec = ("list_notifications", "notifications", "offset")
        id = 'notification_id'
        tag = True
        tag_resource_type = 'cts-notification-func'


@Notification.action_registry.register("update-notification")
class CtsUpdateNotification(HuaweiCloudBaseAction):
    """Update CTS Notification. CTS supports modifying existing Notification configurations by
     matching the notification_id field; the notification_id must already exist. When enabling
      notifications, you can configure the user list and the SMN service topic as needed
    :Example:
    .. code-block:: yaml
    policies:
        - name: update-cts-notification
          resource: huaweicloud.cts-notification-func
          filters:
            - type: value
              key: notification_name
              value: "keyOperate_info_zr1s"
          actions:
            - type: update-notification
              notification_id: "938c9c8a-804b-4c61-bf7b-5e8b1793ae64"
              topic_id: "urn:smn:cn-east-2:932cb325cbca47a59ec1ea930ecc0f29:testcc"
              status: "enabled"
              notification_name: "keyOperate_info_zr1s"
              notify_user_list:
                - user_group: "zhanghouxin"
                  user_list:
                    - "zhanghouxin"
              operations:
                - service_type: "AAD"
                  resource_type: "addprotocolrule"
                  trace_names:
                    - "addProtocolRule"
    """

    schema = type_schema(
        "update-notification",
        notification_id={"type": "string"},
        topic_id={"type": "string"},
        status={"type": "string", "enum": ["enabled", "disabled"]},
        notification_name={"type": "string"},
        notify_user_list={"type": "array", "items": {
            "type": "object",
            "properties": {
                "user_group": {"type": "string"},
                "user_list": {"type": "array", "items": {"type": "string"}}
            }
        }},
        operations={"type": "array", "items": {
            "type": "object",
            "properties": {
                "service_type": {"type": "string"},
                "resource_type": {"type": "string"},
                "trace_names": {"type": "array", "items": {"type": "string"}}
            }
        }}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        properties = {
            "notification_id": self.data.get("notification_id"),
            "topic_id": self.data.get("topic_id"),
            "status": self.data.get("status", "enabled"),
            "notification_name": self.data.get("notification_name"),
            "notify_user_list": self.data.get("notify_user_list", []),
            "operations": self.data.get("operations", [])
        }

        request = UpdateNotificationRequest()
        request.body = UpdateNotificationRequestBody(
            notification_id=properties["notification_id"],
            topic_id=properties["topic_id"],
            status=properties["status"],
            notification_name=properties["notification_name"],
            notify_user_list=[
                NotificationUsers(user_group=entry["user_group"], user_list=entry["user_list"])
                for entry in properties["notify_user_list"]
            ],
            operations=[
                Operations(
                    service_type=entry["service_type"],
                    resource_type=entry["resource_type"],
                    trace_names=entry["trace_names"]
                )
                for entry in properties["operations"]
            ],
            operation_type="customized"
        )

        try:
            response = client.update_notification(request)
            log.info(
                f"[actions]-[update_notification] The resource: [func notification] "
                f"with id:[{resource.get('id', 'empty')}] "
                f"update notification is success"
            )
            log.info(f"Successfully updated CTS notification: {response}")
        except exceptions.ClientRequestException as e:
            log.error(
                f"[actions]-[update_notification] The resource: [func notification] "
                f"with id:[{resource.get('id', 'empty')}] "
                f"update notification is failed"
            )
            log.error(f"cause: {e.status_code}, {e.request_id},"
                      f" {e.error_code}, {e.error_msg}")
            raise
        return response
