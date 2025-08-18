# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import logging

import jmespath
import re
from huaweicloudsdksmn.v2 import PublishMessageRequest, PublishMessageRequestBody

from c7n.utils import type_schema, local_session
from c7n_huaweicloud.actions import HuaweiCloudBaseAction


def register_smn2_actions(actions):
    actions.register('notify-message-from-event', NotifyMessageFromEvent)


class NotifyMessageFromEvent(HuaweiCloudBaseAction):
    """Notify message to the specified smn topic.

    :example:

        .. code-block :: yaml
·
            policies:
            - name: notify-message-example
              resource: huaweicloud.volume
              filters:
                - type: value
                  key: metadata.__system__encrypted
                  value: "0"
              actions:
                - type: notify-message-from-event
                  topic_urn_list:
                   - urn:smn:cn-north-4:xxxx:test
                  subject: 'test subject'
                  message: 'test message %cts.status%,%cts.status%'
    """

    log = logging.getLogger("custodian.huaweicloud.actions.smn2.NotifyMessageFromEvent")

    schema = type_schema("notify-message-from-event", rinherit={
        'type': 'object',
        'additionalProperties': False,
        'required': ['type', 'message', 'topic_urn_list'],
        'properties': {
            'type': {'enum': ['notify-message']},
            "topic_urn_list": {
                "type": "array",
                "items": {"type": "string"}
            },
            'subject': {'type': 'string'},
            'message': {'type': 'string'}
        }
    })

    def process(self, event):
        resource_type = self.manager.resource_type.service
        message = self.data.get('message')
        self.log.debug("event: %s", event)
        id = jmespath.search('cts.resource_id', event)
        try:
            smn_client = local_session(self.manager.session_factory).client("smn")

            keyArr = self.get_param(message)
            self.log.debug("keyArr: %s", keyArr)
            body = PublishMessageRequestBody(
                subject=self.data.get('subject'),
                message=self.build_message(resource_type, id, event, keyArr)
            )

            for topic_urn in self.data.get('topic_urn_list', []):
                request = PublishMessageRequest(topic_urn=topic_urn, body=body)
                smn_client.publish_message(request)
                self.log.debug(
                    f"[actions]-[notify-message] query the service:[POST /v2/{{project_id}}"
                    f"/notifications/topics/{topic_urn}/publish] is success.")
                self.log.info(
                    f"[actions]-[notify-message] The resource:{resource_type} with id:{id} "
                    f"Publish message is success")
        except Exception as e:
            self.log.error(
                f"[actions]-[notify-message] The resource:{resource_type} with id:{id} "
                f"Publish message to SMN Topics is failed, cause:{e}")
            raise e
        return self.process_result(event)

    def build_message(self, resource_type, id, event, keyArr):
        message = self.data.get('message')
        if keyArr is not None:
            for k in keyArr:
                kstr = "%" + k + "%"
                kv = jmespath.search(k, event)
                self.log.info(f"{kstr}:{kv}")
                if kstr in message:
                    if kv:
                        message = message.replace(kstr, kv)
                    else:
                        self.log.warning(f"[actions]-[notify-message]{kstr} is not exist!")

        if '{resource_details}' not in message:
            return message
        resource_details = get_resource_details(resource_type, id)
        if not id:
            self.log.warning(f"[actions]-[notify-message] No id in resource: {resource_type}")
        return message.replace('{resource_details}', resource_details)

    def perform_action(self, resource):
        pass

    def get_param(self, message):
        pattern = re.escape("%") + r'(.*?)' + re.escape("%")
        return re.findall(pattern, message)


def get_resource_details(resource_type, id):
    return '{resource_type}:{id}'.format(resource_type=resource_type, id=id)
