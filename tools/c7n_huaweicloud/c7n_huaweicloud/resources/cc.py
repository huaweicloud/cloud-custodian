# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkcc.v3 import DeleteCloudConnectionRequest

from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo


log = logging.getLogger("custodian.huaweicloud.resources.cc")


@resources.register('cc-cloud-connection')
class CloudConnection(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'cc'
        enum_spec = ("list_cloud_connections", "cloud_connections", "marker")
        id = 'id'
        tag_resource_type = 'cc'


@CloudConnection.action_registry.register("delete")
class CloudConnectionDelete(HuaweiCloudBaseAction):
    """Delete Cloud Connection.

    :Example:

    .. code-block:: yaml
        policies:
          - name: delete-cc-cloud-connection
            resource: huaweicloud.cc-cloud-connection
            filters:
              - type: value
                key: need_delete
                value: true
            actions:
              - delete
    """

    schema = type_schema("delete")

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = DeleteCloudConnectionRequest(id=resource["id"])
        try:
            response = client.delete_cloud_connection(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response
