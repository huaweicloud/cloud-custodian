# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from huaweicloudsdksmn.v2 import *
from c7n.utils import type_schema, local_session
from c7n.exceptions import PolicyValidationError
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction

log = logging.getLogger("custodian.huaweicloud.resources.coc")

@resources.register('coc')
class Coc(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'coc'
        enum_spec = ('list_instance_compliant', 'instance_compliant', 'offset')
        id = 'id'
        offset_start_num = 1
        tag_resource_type = 'instance_compliant_tag'

@Coc.action_registry.register("non_compliant_alarm")
class NonCompliantAlarm(HuaweiCloudBaseAction):
    """Alarm non compliant patch.

    :Example:

    .. code-block:: yaml

         policies:
           - name: non-compliant-patch
             resource: huaweicloud.coc
             filters:
               - type: value
                 key: status
                 value: 'non_compliant'
                 op: eq
               - type: value
                 key: report_scene
                 value: 'ECS'
                 op: eq
               - type: value
                 key: operating_system
                 value: 'CentOS'
                 op: eq
               - type: value
                 key: region
                 value: 'cn-north-4'
                 op: eq
             actions:
               - type: non_compliant_alarm
                 smn: true
                 region_id: cn-north-4
                 topic_urn: ********
                 subject: ********
                 message: ********
    """

    schema = type_schema("non_compliant_alarm",
                         smn={'type': 'boolean'},
                         region_id={'type': 'string'},
                         topic_urn={'type': 'string'},
                         subject={'type': 'string'},
                         message={'type': 'string'}
                         )
    def validate(self):
        smn = self.data.get('smn', False)
        if smn and not (self.data.get('region_id') and self.data.get('topic_urn') and self.data.get('subject')):
            raise PolicyValidationError("Can not create smn message when parameter is error")


    def perform_action(self, resource):
        if not self.data.get('smn', False):
            log.info(f"The request id")
            return
        ecs_name = resource.get('name')
        region = resource.get('region')
        ecs_instance_id = resource.get('instance_id')
        non_compliant_count = resource.get('non_compliant_summary').get('non_compliant_count')
        message_data = (f'ecs_name: {ecs_name}, ecs_instance_id: {ecs_instance_id}, region: {region}, '
                        f'non_compliant_count: {non_compliant_count};\n')
        subject = self.data.get('subject')
        message = self.data.get('message')
        topic_urn = self.data.get('topic_urn')

        client = local_session(self.manager.session_factory).client('smn')
        message_body = PublishMessageRequestBody(
            subject = subject,
            message = message + '\n' + message_data
        )
        request = PublishMessageRequest(topic_urn=topic_urn, body=message_body)
        response = client.publish_message(request)
        log.info(f"Successfully create smn message, the smn message id:{response.message_id}")
        return response
