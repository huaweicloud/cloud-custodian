# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from huaweicloudsdkcore.exceptions import exceptions
from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from huaweicloudsdkantiddos.v1 import UpdateDDosRequest, UpdateAntiDDosServiceRequestBody

log = logging.getLogger("custodian.huaweicloud.resources.antiddos")


@resources.register('antiddos-eip')
class Eip(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'antiddos'
        enum_spec = ("list_d_dos_status", 'ddosStatus', 'offset')
        id = 'floating_ip_id'
        tag_resource_type = 'antiddos-ip'


@Eip.action_registry.register('enable')
class EipEnableAntiDDoS(HuaweiCloudBaseAction):
    """Enable Anti-DDoS for unprotected EIP.

    :Example:

    .. code-block:: yaml

        policies:
          - name: eip-enable-antiddos
            resource: huaweicloud.antiddos-eip
            flters:
              - type: value
                key: status
                value: "notConfig"
            actions:
              - enable
    """

    schema = type_schema("enable")

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = UpdateDDosRequest()
        request.floating_ip_id = resource.get('floating_ip_id')
        request.body = UpdateAntiDDosServiceRequestBody(
            traffic_pos_id=9,
            http_request_pos_id=1,
            enable_l7=False,
            cleaning_access_pos_id=8,
            app_type_id=0
        )
        try:
            response = client.update_d_dos(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response
