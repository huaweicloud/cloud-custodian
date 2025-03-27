# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdker.v3 import UpdateEnterpriseRouterRequest
from huaweicloudsdker.v3 import UpdateEnterpriseRouter
from huaweicloudsdker.v3 import UpdateEnterpriseRouterRequestBody

from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

log = logging.getLogger("custodian.huaweicloud.resources.er")


@resources.register('er')
class ERInstance(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'er'
        enum_spec = ("list_enterprise_routers", 'instances', "offset")
        id = 'id'
        tag_resource_type = 'er-instance-tags'


@ERInstance.action_registry.register("update")
class EnterpriseRouterCreate(HuaweiCloudBaseAction):
    """Update Enterprise Router.

    :Example:

    .. code-block:: yaml
        policies:
          - name: update-enterprise-router
            resource: huaweicloud.er
            filters:
              - type: value
                key: auto_accept_shared_attachments
                value: true
            actions:
              - update
    """

    schema = type_schema("update")

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = UpdateEnterpriseRouterRequest(er_id=resource["id"])
        instancebody = UpdateEnterpriseRouter(auto_accept_shared_attachments=False)
        request.body = UpdateEnterpriseRouterRequestBody(instance=instancebody)

        try:
            response = client.update_enterprise_router(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response
