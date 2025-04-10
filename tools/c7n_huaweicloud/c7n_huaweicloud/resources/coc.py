# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from huaweicloudsdksmn.v2 import PublishMessageRequest, PublishMessageRequestBody
from c7n.utils import type_schema, local_session
from c7n.exceptions import PolicyValidationError
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from huaweicloudsdkcore.exceptions import exceptions

log = logging.getLogger("custodian.huaweicloud.resources.coc")


@resources.register('coc')
class Coc(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'coc'
        enum_spec = ('list_instance_compliant', 'instance_compliant', 'offset')
        id = 'id'
        offset_start_num = 1
        tag_resource_type = None


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
        if smn and not (self.data.get('region_id') and self.data.get('topic_urn') and
                        self.data.get('subject') and self.data.get('message')):
            raise PolicyValidationError("Can not create smn alarm message when parameter is error.")

    def perform_action(self, resource):
        if not self.data.get('smn', False):
            log.info("Do not create smn alarm message.")
            return
        ecs_name = resource.get('name')
        region = resource.get('region')
        ecs_instance_id = resource.get('instance_id')
        non_compliant_count = resource.get('non_compliant_summary').get('non_compliant_count')
        message_data = (f'ecs_name: {ecs_name}, ecs_instance_id: {ecs_instance_id}, '
                        f'region: {region}, non_compliant_count: {non_compliant_count}')
        subject = self.data.get('subject')
        message = self.data.get('message')
        topic_urn = self.data.get('topic_urn')

        client = local_session(self.manager.session_factory).client('smn')
        message_body = PublishMessageRequestBody(
            subject=subject,
            message=message + '\n' + message_data
        )
        request = PublishMessageRequest(topic_urn=topic_urn, body=message_body)
        try:
            response = client.publish_message(request)
            log.info(f"Successfully create smn alarm message, the message id: "
                     f"{response.message_id}.")
        except exceptions.ClientRequestException as e:
            log.error(f"Create smn alarm message failed: {e.error_msg}")
