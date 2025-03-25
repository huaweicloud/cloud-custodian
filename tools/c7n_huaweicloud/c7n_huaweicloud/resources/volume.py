# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from huaweicloudsdkevs.v2 import DeleteVolumeRequest

from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

log = logging.getLogger("custodian.huaweicloud.resources.volume")


@resources.register('volume')
class Volume(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'evs'
        enum_spec = ("list_volumes", 'volumes', 'offset')
        id = 'id'
        tag_resource_type = 'disk'


@Volume.action_registry.register("delete")
class VolumeDelete(HuaweiCloudBaseAction):
    """Deletes EVS Volumes.

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-unencrypted-volume
            resource: huaweicloud.volume
            flters:
              - type: value
                key: metadata.__system__encrypted
                value: "0"
            actions:
              - delete
    """

    schema = type_schema("delete")

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = DeleteVolumeRequest(volume_id=resource["id"])
        response = client.delete_volume(request)
        log.info(f"Received Job ID:{response.job_id}")
        # TODO: need to track whether the job succeed
        response = None
        return response
