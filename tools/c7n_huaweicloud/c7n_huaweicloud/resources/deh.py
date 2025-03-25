# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from huaweicloudsdkdeh.v1 import UpdateDedicatedHostRequest, ReqUpdateDeh, ReqUpdateDehMessage

from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

log = logging.getLogger("custodian.huaweicloud.resources.deh")


@resources.register('deh')
class Deh(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'deh'
        enum_spec = ("list_dedicated_hosts", 'dedicated_hosts', 'offset')
        id = 'dedicated_host_id'
        tag_resource_type = 'dedicated-host-tags'


@Deh.action_registry.register("update-dedicated-host")
class UpdateDedicatedHost(HuaweiCloudBaseAction):
    """Update Dedicated Host.

    :Example:

    .. code-block:: yaml

        policies:
          - name: update-dedicated-host
            resource: huaweicloud.deh
            filters:
              - type: value
                key: name
                value: "test"
            actions:
              - type: update-dedicated-host
                dedicated_host:
                    name: "update"
                    auto_placement: "off"
    """

    schema = type_schema(
        "update-dedicated-host",
        required=['dedicated_host'],
        **{
            "dedicated_host": {
                "type": "object",
                "properties": {
                    "auto_placement": {"type": "string", "enum": ["on", "off"]},
                    "name": {"type": "string"},
                }
            },
        }
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = UpdateDedicatedHostRequest()
        request.dedicated_host_id = resource['dedicated_host_id']
        dedicated_host = self.data.get("dedicated_host", None)
        if dedicated_host:
            request.body = ReqUpdateDeh(
                dedicated_host=ReqUpdateDehMessage(
                    auto_placement=dedicated_host.get("auto_placement", None),
                    name=dedicated_host.get("name", None),
                )
            )
        response = client.update_dedicated_host(request)
        return response
