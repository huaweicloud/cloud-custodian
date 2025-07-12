# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import logging

from huaweicloudsdkcore.exceptions import exceptions
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
        ids = ','.join(data['id'] for data in resources)
        try:
            smn_client = local_session(self.manager.session_factory).client("smn")
            body = PublishMessageRequestBody(
                subject=self.data.get('subject'),
                message=self.build_message(resource_type, ids)
            )

            for topic_urn in self.data.get('topic_urn_list', []):
                publish_message_request = PublishMessageRequest(topic_urn=topic_urn, body=body)
                publish_message_response = smn_client.publish_message(publish_message_request)
                self.log.info(
                    f"[actions]-The resource:{resource_type} with id:[{ids}] "
                    f"Publish message success, request: {publish_message_request}, "
                    f"response: {publish_message_response}")
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"[actions]-The resource:{resource_type} with id:[{ids}] "
                f"Publish message to SMN Topics is failed, exceptions:{e}")
        return self.process_result(resources)

    def build_message(self, resource_type, ids):
        message = self.data.get('message')
        if '{resource_details}' not in message:
            return message
        resource_details = get_resource_details(resource_type, ids)
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
        ids = ','.join(data['id'] for data in resources)
        try:
            smn_client = local_session(self.manager.session_factory).client("smn")
            body = PublishMessageRequestBody(
                subject=self.data.get('subject'),
                message_structure=self.build_message(resource_type, ids)
            )

            for topic_urn in self.data.get('topic_urn_list', []):
                publish_message_request = PublishMessageRequest(topic_urn=topic_urn, body=body)
                publish_message_response = smn_client.publish_message(publish_message_request)
                self.log.info(
                    f"[actions]-The resource:{resource_type} with id:[{ids}] "
                    f"Publish message structure success, request: {publish_message_request}, "
                    f"response: {publish_message_response}")
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"[actions]-The resource:{resource_type} with id:[{ids}] "
                f"Publish message structure to SMN Topics failed, exceptions:{e}")
        return self.process_result(resources)

    def build_message(self, resource_type, ids):
        message_structure = self.data.get('message_structure')
        if '{resource_details}' not in message_structure:
            return message_structure
        resource_details = get_resource_details(resource_type, ids)
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
        ids = ','.join(data['id'] for data in resources)
        try:
            smn_client = local_session(self.manager.session_factory).client("smn")
            body = PublishMessageRequestBody(
                subject=self.data.get('subject'),
                message_template_name=self.data.get('message_template_name'),
                tags=self.build_message(resource_type, ids)
            )

            for topic_urn in self.data.get('topic_urn_list', []):
                publish_message_request = PublishMessageRequest(topic_urn=topic_urn, body=body)
                publish_message_response = smn_client.publish_message(publish_message_request)
                self.log.info(
                    f"[actions]-The resource:{resource_type} with id:[{ids}] "
                    f"Publish message template success, request: {publish_message_request}, "
                    f"response: {publish_message_response}")
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"[actions]-The resource:{resource_type} with id:[{ids}] "
                f"Publish message template to SMN Topics failed, exceptions:{e}")
        return self.process_result(resources)

    def build_message(self, resource_type, ids):
        message_template_variables = self.data.get('message_template_variables')
        for k, v in message_template_variables.items():
            if '{resource_details}' in v:
                resource_details = get_resource_details(resource_type, ids)
                message_template_variables[k] = v.replace('{resource_details}', resource_details)
        return message_template_variables

    def perform_action(self, resource):
        pass


def get_resource_details(resource_type, ids):
    return '{resource_type}:{ids}'.format(resource_type=resource_type, ids=ids)
