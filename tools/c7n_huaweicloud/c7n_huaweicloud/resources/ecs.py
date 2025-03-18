
import logging
from typing import List

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkevs.v2 import *
from huaweicloudsdkecs.v2 import *

from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

log = logging.getLogger("custodian.huaweicloud.resources.ecs")


@resources.register('ecs')
class Ecs(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'ecs'
        enum_spec = ("nova_list_servers_details", "servers", "NovaListServersDetailsRequest")
        id = 'id'
        tag = True


@Ecs.action_registry.register("start")
class EcsStart(HuaweiCloudBaseAction):
    """Start ECS server.

    :Example:

    .. code-block:: yaml

        policies:
          - name: start-ecs-server
            resource: huaweicloud.ecs
            filters:
              - type: value
                key: id
                value: "your server id"
            actions:
              - start
    """

    schema = type_schema("start")

    def perform_action(self, resource):
        client = self.manager.get_client()
        serverIds : List[ServerId] = [{"id":resource["id"]}]
        options = {"servers":serverIds}
        requestBody = BatchStartServersRequestBody(os_start=options)
        request = BatchStartServersRequest(body=requestBody)
        response = client.batch_start_servers(request)
        # TODO 异常处理、结果处理
        return response

@Ecs.action_registry.register("stop")
class EcsStart(HuaweiCloudBaseAction):
    """Deletes EVS Volumes.

    :Example:

    .. code-block:: yaml

        policies:
          - name: stop-ecs-server
            resource: huaweicloud.ecs
            filters:
              - type: value
                key: id
                value: "your server id"
            actions:
              - type: stop
                mode: "SOFT"
    """

    schema = type_schema("stop", mode={'type': 'string'})

    def perform_action(self, resource):
        client = self.manager.get_client()
        serverIds : List[ServerId] = [{"id":resource['id']}]
        options = {"servers":serverIds,"type": self.data.get('mode', 'SOFT')}
        requestBody = BatchStopServersRequestBody(os_stop=options)
        request = BatchStopServersRequest(body=requestBody)
        response = client.batch_stop_servers(request)
        # TODO 异常处理、结果处理
        return response
      
@Ecs.action_registry.register("reboot")
class EcsStart(HuaweiCloudBaseAction):
    """Deletes EVS Volumes.

    :Example:

    .. code-block:: yaml

        policies:
          - name: reboot-ecs-server
            resource: huaweicloud.ecs
            filters:
              - type: value
                key: id
                value: "your server id"
            actions:
              - type: reboot
                mode: "SOFT"
    """

    schema = type_schema("reboot", mode={'type': 'string'})

    def perform_action(self, resource):
        client = self.manager.get_client()
        serverIds : List[ServerId] = [{"id":resource['id']}]
        options = {"servers":serverIds,"type": self.data.get('mode', 'SOFT')}
        requestBody = BatchRebootServersRequestBody(reboot=options)
        request = BatchRebootServersRequest(body=requestBody)
        response = client.batch_stop_servers(request)
        # TODO 异常处理、结果处理
        return response