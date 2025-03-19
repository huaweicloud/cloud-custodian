
import logging
from typing import List

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkevs.v2 import *
from huaweicloudsdkecs.v2 import *

from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.filters.ecsfilter import *

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
        try:
          response = client.batch_start_servers(request)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return response

@Ecs.action_registry.register("stop")
class EcsStop(HuaweiCloudBaseAction):
    """Stop Ecs Server.

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
        try:
          response = client.batch_stop_servers(request)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return response
      
@Ecs.action_registry.register("reboot")
class EcsReboot(HuaweiCloudBaseAction):
    """Reboot Ecs Server.

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
        try:
          response = client.batch_stop_servers(request)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return response
      
@Ecs.action_registry.register("terminate")
class EcsTerminate(HuaweiCloudBaseAction):
    """Terminate Ecs Server.

    :Example:

    .. code-block:: yaml

        policies:
          - name: terminate-ecs-server
            resource: huaweicloud.ecs
            filters:
              - type: value
                key: id
                value: "your server id"
            actions:
              - terminate
    """

    schema = type_schema("terminate", mode={'type': 'string'})

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = NovaDeleteServerRequest(server_id=resource["id"])
        try:
          response = client.nova_delete_server(request)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return response
      
@Ecs.action_registry.register("add-security-groups")
class AddSecurityGroup(HuaweiCloudBaseAction):
    """Add Security Groups For Ecs Server.

    :Example:

    .. code-block:: yaml

        policies:
          - name: add-security-groups
            resource: huaweicloud.ecs
            filters:
              - type: value
                key: id
                value: "your server id"
            actions:
              - add-security-groups
    """

    schema = type_schema("add-security-groups", name={'type': 'string'})

    def perform_action(self, resource):
        client = self.manager.get_client()
        name=self.data.get('name', None)
        if name == None:
          log.error("security group name is None")
          return None
        option = NovaAddSecurityGroupOption(name=name)
        requestBody = NovaAssociateSecurityGroupRequestBody(add_security_group=option)
        request = NovaAssociateSecurityGroupRequest(server_id=resource["id"], body=requestBody)
        try:
          response = client.nova_associate_security_group(request)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return response
      
@Ecs.action_registry.register("delete-security-groups")
class AddSecurityGroup(HuaweiCloudBaseAction):
    """Deletes Security Groups For Ecs Server.

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-security-groups
            resource: huaweicloud.ecs
            filters:
              - type: value
                key: id
                value: "your server id"
            actions:
              - type: delete-security-groups
                name: "test_group"
    """

    schema = type_schema("delete-security-groups", name={'type': 'string'})

    def perform_action(self, resource):
        client = self.manager.get_client()
        name=self.data.get('name', None)
        if name == None:
          log.error("security group name is None")
          return None
        option = NovaAddSecurityGroupOption(name=name)
        requestBody = NovaAssociateSecurityGroupRequestBody(add_security_group=option)
        request = NovaAssociateSecurityGroupRequest(server_id=resource["id"], body=requestBody)
        try:
          response = client.nova_disassociate_security_group(request)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return response


#---------------------------ECS Filter-------------------------------------#

@Ecs.filter_registry.register('instance-age')
class EcsAgeFilter(AgeFilter):
    """ECS Instance Age Filter: greater-than or less-than threshold date

    :Example:

    .. code-block:: yaml

        policies:
          - name: ecs-instances-age
            resource: huaweicloud.ecs
            filters:
              - type: instance-age
                op: greater-than
                days: 1
    """
    date_attribute = "created"

    schema = type_schema(
        'instance-age',
        op={'enum': ['greater-than', 'less-than']},
        days={'type': 'number', 'minimum': 0},
        hours={'type': 'number', 'minimum': 0},
        minutes={'type': 'number', 'minimum': 0}
    )