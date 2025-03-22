# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from huaweicloudsdksmn.v2 import *
from c7n.utils import type_schema
from c7n.exceptions import PolicyValidationError
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction

log = logging.getLogger("custodian.huaweicloud.resources.coc")

@resources.register('coc')
class Coc(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'coc'
        enum_spec = ("list_non_compliant", 'compliant', 'offset')
        id = 'id'
        tag = True

@Coc.action_registry.register("non-compliant-patch")
class NonCompliantAlarm(HuaweiCloudBaseAction):
    """Alarm non compliant patch.

    :Example:

    .. code-block:: yaml

         policies:
           - name: non-compliant-patch
             resource: huaweicloud.coc
             filters:
               - type: value
                 key: operating_system
                 value: CentOS
                 op: eq
               - type: value
                 key: region
                 value: cn-north-4
                 op: eq
               - type: value
                 key: compliant_status
                 value: non_compliant
             actions:
               - type: alarm
                 smn: true
                 region_id: cn-north-4
                 topic_urn: ********
                 subject: ********
                 message: ********
    """

    schema = type_schema("alarm",
                         smn={'type': 'boolean'},
                         region_id={'type': 'string'},
                         topic_urn={'type': 'string'},
                         subject={'type': 'string'},
                         message={'type': 'string'}
                         )
    def validate(self):
        smn = self.data.get('smn')
        if smn and not (self.data.get('region_id') and self.data.get('topic_urn') and self.data.get('subject')):
            raise PolicyValidationError("Can not create smn message when parameter is error")


    def perform_action(self, resource):
        count = resource.get('count')
        if count < 1:
            log.info("non compliant patch count is 0")
            return
        message_data = ''
        for instance_compliant in resource.get('instance_compliant'):
            ecs_name = instance_compliant.get('name')
            ecs_instance_id = instance_compliant.get('instance_id')
            non_compliant_count = instance_compliant.get('non_compliant_summary').get('non_compliant_count')
            message_data += f'ecs_name: {ecs_name}, ecs_instance_id: {ecs_instance_id}, non_compliant_count: {non_compliant_count};\n'
        smn = self.data.get('smn', False)
        topic_urn = self.data.get('topic_urn')
        if not (smn or topic_urn):
            raise PolicyValidationError("Can not create or update tracke when smn and obs both false")

        subject = self.data.get('subject')
        message = self.data.get('message')

        client = self.manager.get_client()
        message_body = PublishMessageRequestBody(
            subject = subject,
            message = message + '\n' + message_data
        )
        request = PublishMessageRequest(topic_urn=topic_urn, body=message_body)
        response = client.publish_message(request)
        log.info(f"The request id: {response.request_id}, message id:{response.message_id}")
        return response
