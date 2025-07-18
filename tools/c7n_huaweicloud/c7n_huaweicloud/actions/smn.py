# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import logging

from huaweicloudsdksmn.v2 import PublishMessageRequest, PublishMessageRequestBody

from c7n.utils import type_schema, local_session
from c7n_huaweicloud.actions import HuaweiCloudBaseAction


def register_smn_actions(actions):
    actions.register('notify-message', NotifyMessageAction)
    actions.register('notify-message-structure', NotifyMessageStructureAction)
    actions.register('notify-message-template', NotifyMessageTemplateAction)


class NotifyMessageAction(HuaweiCloudBaseAction):
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
                - type: notify-message
                  topic_urn_list:
                   - urn:smn:cn-north-4:xxxx:test
                  subject: 'test subject'
                  message: 'test message'
    """

    log = logging.getLogger("custodian.huaweicloud.actions.smn.NotifyMessageAction")

    schema = type_schema("notify-message", rinherit={
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

    def process(self, resources):
        resource_type = self.manager.resource_type.service
        ids = None
        try:
            ids = get_resource_ids(resources)
            smn_client = local_session(self.manager.session_factory).client("smn")
            body = PublishMessageRequestBody(
                subject=self.data.get('subject'),
                message=self.build_message(resource_type, ids)
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
        return self.process_result(resources)

    def build_message(self, resource_type, ids):
        message = self.data.get('message')
        if '{resource_details}' not in message:
            return message
        resource_details = get_resource_details(resource_type, ids)
        if not ids:
            self.log.warning(f"[actions]-[notify-message] No id in resource: {resource_type}")
        return message.replace('{resource_details}', resource_details)

    def perform_action(self, resource):
        pass


class NotifyMessageStructureAction(HuaweiCloudBaseAction):
    """Notify message structure to the specified smn topic.

    :example:

        .. code-block :: yaml
·
            policies:
            - name: notify-message-structure-example
              resource: huaweicloud.volume
              filters:
                - type: value
                  key: metadata.__system__encrypted
                  value: "0"
              actions:
                - type: notify-message-structure
                  topic_urn_list:
                   - urn:smn:cn-north-4:xxxx:test
                  subject: 'test subject'
                  message_structure: '{\"default\": \"test\",\"sms\": \"test\",\"email\": \"test\"}'
    """

    log = logging.getLogger("custodian.huaweicloud.actions.smn.NotifyMessageStructureAction")

    schema = type_schema("notify-message-structure", rinherit={
        'type': 'object',
        'additionalProperties': False,
        'required': ['type', 'message_structure', 'topic_urn_list'],
        'properties': {
            'type': {'enum': ['notify-message-structure']},
            "topic_urn_list": {
                "type": "array",
                "items": {"type": "string"}
            },
            'subject': {'type': 'string'},
            'message_structure': {'type': 'string'}
        }
    })

    def process(self, resources):
        resource_type = self.manager.resource_type.service
        ids = None
        try:
            ids = get_resource_ids(resources)
            smn_client = local_session(self.manager.session_factory).client("smn")
            body = PublishMessageRequestBody(
                subject=self.data.get('subject'),
                message_structure=self.build_message(resource_type, ids)
            )

            for topic_urn in self.data.get('topic_urn_list', []):
                request = PublishMessageRequest(topic_urn=topic_urn, body=body)
                smn_client.publish_message(request)
                self.log.debug(
                    f"[actions]-[notify-message-structure] query the service:[POST "
                    f"/v2/{{project_id}}/notifications/topics/{topic_urn}/publish] is success.")
                self.log.info(
                    f"[actions]-[notify-message-structure] The resource:{resource_type} with id:"
                    f"{ids} Publish message structure success")
        except Exception as e:
            self.log.error(
                f"[actions]-[notify-message-structure] The resource:{resource_type} with id:{ids}"
                f" Publish message structure to SMN Topics failed, cause:{e}")
        return self.process_result(resources)

    def build_message(self, resource_type, ids):
        message_structure = self.data.get('message_structure')
        if '{resource_details}' not in message_structure:
            return message_structure
        resource_details = get_resource_details(resource_type, ids)
        if not ids:
            self.log.warning(
                f"[actions]-[notify-message-structure] No id in resource: {resource_type}")
        return message_structure.replace('{resource_details}', resource_details)

    def perform_action(self, resource):
        pass


class NotifyMessageTemplateAction(HuaweiCloudBaseAction):
    """Notify message template to the specified smn topic.

    :example:

        .. code-block :: yaml
·
            policies:
            - name: notify-message-template-example
              resource: huaweicloud.volume
              filters:
                - type: value
                  key: metadata.__system__encrypted
                  value: "0"
              actions:
                - type: notify-message-template
                  topic_urn_list:
                   - urn:smn:cn-north-4:xxxx:test
                  subject: 'test subject'
                  message_template_name: test
                  message_template_variables:
                    key1: 123
                    key2: 456
    """

    log = logging.getLogger("custodian.huaweicloud.actions.smn.NotifyMessageTemplateAction")

    schema = type_schema("notify-message-template", rinherit={
        'type': 'object',
        'additionalProperties': False,
        'required': ['type', 'message_template_name', 'topic_urn_list'],
        'properties': {
            'type': {'enum': ['notify-message-template']},
            "topic_urn_list": {
                "type": "array",
                "items": {"type": "string"}
            },
            'subject': {'type': 'string'},
            'message_template_name': {'type': 'string'},
            'message_template_variables': {'type': 'object'}

        }
    })

    def process(self, resources):
        resource_type = self.manager.resource_type.service
        ids = None
        try:
            ids = get_resource_ids(resources)
            smn_client = local_session(self.manager.session_factory).client("smn")
            body = PublishMessageRequestBody(
                subject=self.data.get('subject'),
                message_template_name=self.data.get('message_template_name'),
                tags=self.build_message(resource_type, ids)
            )

            for topic_urn in self.data.get('topic_urn_list', []):
                request = PublishMessageRequest(topic_urn=topic_urn, body=body)
                smn_client.publish_message(request)
                self.log.debug(
                    f"[actions]-[notify-message-template] query the service:[POST "
                    f"/v2/{{project_id}}/notifications/topics/{topic_urn}/publish] is success.")
                self.log.info(
                    f"[actions]-[notify-message-template] The resource:{resource_type} with id:"
                    f"{ids} Publish message template success.")
        except Exception as e:
            self.log.error(
                f"[actions]-[notify-message-template] The resource:{resource_type} with id:{ids} "
                f"Publish message template to SMN Topics failed, cause:{e}")
        return self.process_result(resources)

    def build_message(self, resource_type, ids):
        message_template_variables = self.data.get('message_template_variables')
        for k, v in message_template_variables.items():
            if '{resource_details}' in v:
                resource_details = get_resource_details(resource_type, ids)
                if not ids:
                    self.log.warning(
                        f"[actions]-[notify-message-template] No id in resource: {resource_type}")
                message_template_variables[k] = v.replace('{resource_details}', resource_details)
        return message_template_variables

    def perform_action(self, resource):
        pass


def get_resource_ids(resources):
    return [data['id'] for data in resources if 'id' in data]


def get_resource_details(resource_type, ids):
    return '{resource_type}:{ids}'.format(resource_type=resource_type, ids=','.join(ids))
