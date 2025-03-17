
import logging

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkevs.v2 import *

from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

log = logging.getLogger("custodian.huaweicloud.resources.volume")


@resources.register('ecs')
class Ecs(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'ecs'
        enum_spec = ("list_servers_details", "servers", "ListServersDetailsRequest")
        id = 'id'
        tag = True


@Ecs.action_registry.register("start")
class EcsStart(HuaweiCloudBaseAction):
    """Deletes EVS Volumes.

    :Example:

    .. code-block:: yaml

        policies:
          - name: start-ecs-server
            resource: huaweicloud.ecs
            flters:
              - type: value
                key: metadata.__system__encrypted
                value: "0"
            actions:
              - start
    """

    schema = type_schema("start")

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = self.serverId
        response = client.action(request)
        log.info(f"Received Job ID:{response.job_id}")
        # TODO: need to track whether the job succeed
        response = None
        return response
