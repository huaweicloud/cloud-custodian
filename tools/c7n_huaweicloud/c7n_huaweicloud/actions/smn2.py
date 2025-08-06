# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import logging

import jmespath
from huaweicloudsdksmn.v2 import PublishMessageRequest, PublishMessageRequestBody

from c7n.utils import type_schema, local_session
from c7n_huaweicloud.actions import HuaweiCloudBaseAction


def register_smn2_actions(actions):
    actions.register('notify-message-from-event', NotifyMessageCustomizeAction)


class NotifyMessageCustomizeAction(HuaweiCloudBaseAction):
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
                  keyarr : ["status","accoutid"]
                  message: 'test message {status},'
    """

    log = logging.getLogger("custodian.huaweicloud.actions.smn2.NotifyMessageCustomizeAction")

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
            'keyArr': {'type': 'array'},
            'message': {'type': 'string'}
        }
    })

    def process(self, events):
        resource_type = self.manager.resource_type.service
        ids = None
        try:
            ids = get_resource_ids(events)
            smn_client = local_session(self.manager.session_factory).client("smn")
            keyArr = self.data.get('keyArr', [])

            body = PublishMessageRequestBody(
                subject=self.data.get('subject'),
                message=self.build_message(resource_type, ids, events, keyArr)
            )

            for topic_urn in self.data.get('topic_urn_list', []):
                request = PublishMessageRequest(topic_urn=topic_urn, body=body)
                smn_client.publish_message(request)
                self.log.debug(
                    f"[actions]-[notify-message] query the service:[POST /v2/{{project_id}}"
                    f"/notifications/topics/{topic_urn}/publish] is success.")
                self.log.info(
                    f"[actions]-[notify-message] The resource:{resource_type} with id:{ids} "
                    f"Publish message is success")
        except Exception as e:
            self.log.error(
                f"[actions]-[notify-message] The resource:{resource_type} with id:{ids} "
                f"Publish message to SMN Topics is failed, cause:{e}")
        return self.process_result(events)

    def build_message(self, resource_type, ids, events, keyArr):
        message = self.data.get('message')
        if keyArr is not None:
            for k in keyArr:
                kstr = "{" + k + "}"
                kv = jmespath.search(k, events[0])
                if kstr in message:
                    message = message.replace(kstr, kv)
        if '{resource_details}' not in message:
            return message
        resource_details = get_resource_details(resource_type, ids)
        if not ids:
            self.log.warning(f"[actions]-[notify-message] No id in resource: {resource_type}")
        return message.replace('{resource_details}', resource_details)

    def perform_action(self, resource):
        pass


def get_resource_ids(resources):
    return [data['id'] for data in resources if 'id' in data]


def get_resource_details(resource_type, ids):
    return '{resource_type}:{ids}'.format(resource_type=resource_type, ids=','.join(ids))
