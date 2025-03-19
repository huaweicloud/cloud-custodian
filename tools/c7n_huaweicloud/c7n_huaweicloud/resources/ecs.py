
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
        enum_spec = ("list_servers_details", "servers", "offset")
        id = 'id'
        tag = True


@Ecs.action_registry.register("instance-start")
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
              - instance-start
    """

    schema = type_schema("instance-start")

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

@Ecs.action_registry.register("instance-stop")
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
              - type: instance-stop
                mode: "SOFT"
    """

    schema = type_schema("instance-stop", mode={'type': 'string'})

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
      
@Ecs.action_registry.register("instance-reboot")
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
              - type: instance-reboot
                mode: "SOFT"
    """

    schema = type_schema("instance-reboot", mode={'type': 'string'})

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
      
@Ecs.action_registry.register("instance-terminate")
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
              - instance-terminate
    """

    schema = type_schema("instance-terminate", mode={'type': 'string'})

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = NovaDeleteServerRequest(server_id=resource["id"])
        try:
          response = client.nova_delete_server(request)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return response
      
@Ecs.action_registry.register("instance-add-security-groups")
class AddSecurityGroup(HuaweiCloudBaseAction):
    """Add Security Groups For An Ecs Server.

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
              - instance-add-security-groups
    """

    schema = type_schema("instance-add-security-groups", name={'type': 'string'}, required=('name',))

    def perform_action(self, resource):
        client = self.manager.get_client()
        name=self.data.get('name', None)
        option = NovaAddSecurityGroupOption(name=name)
        requestBody = NovaAssociateSecurityGroupRequestBody(add_security_group=option)
        request = NovaAssociateSecurityGroupRequest(server_id=resource["id"], body=requestBody)
        try:
          response = client.nova_associate_security_group(request)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return response
      
@Ecs.action_registry.register("instance-delete-security-groups")
class AddSecurityGroup(HuaweiCloudBaseAction):
    """Deletes Security Groups For An Ecs Server.

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
              - type: instance-delete-security-groups
                name: "test_group"
    """

    schema = type_schema("instance-delete-security-groups", name={'type': 'string'})

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
      
@Ecs.action_registry.register("instance-resize")
class Resize(HuaweiCloudBaseAction):
    """Resize An Ecs Server Flavor.

    :Example:

    .. code-block:: yaml

        policies:
          - name: resize
            resource: huaweicloud.ecs
            filters:
              - type: instance-resize
                flavor_ref: "x1.1u.4g"
                mode: "withStopServer"
    """
    
    schema = type_schema("instance-resize", flavor_ref={'type': 'string'},
                         dedicated_host_id={'type': 'string'},
                         is_auto_pay={'type': 'string'},
                         mode={'type': 'string'},
                         hwcpu_threads={'type': 'int'},
                         dry_run={'type' : 'boolean'})
  
    def perform_action(self, resource):
        client = self.manager.get_client()
        extendParam = ResizeServerExtendParam(is_auto_pay=self.data.get('is_auto_pay', None))
        cpuOptions = CpuOptions(hwcpu_threads=self.data.get('hwcpu_threads', None))
        flavorRef=self.data.get('flavor_ref', None)
        dedicatedHostId = self.data.get('dedicated_host_id', None)
        mode = self.data.get('mode', None)
        if flavorRef == None:
          log.error("flavor_ref con not be None")
          return None
        option = ResizePrePaidServerOption(flavor_ref=flavorRef, dedicated_host_id=dedicatedHostId, 
                                           extendparam=extendParam, mode=mode, cpu_options=cpuOptions)
        requestBody = ResizeServerRequestBody(resize=option, dry_run=self.data.get('dry_run', None))
        request = ResizeServerRequest(server_id=resource['id'], body=requestBody)
        try:
          response = client.resize_server(request)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return response
      
@Ecs.action_registry.register("set-instance-profile")
class SetInstanceProfile(HuaweiCloudBaseAction):
  
  schema = type_schema("set-instance-profile", metadata={'type': 'object'})
  
  def perform_action(self, resource):
      client = self.manager.get_client()
      metadata = self.data.get('metadata', None)
      requestBody = UpdateServerMetadataRequestBody(metadata=metadata)
      request = UpdateServerMetadataRequest(server_id=resource['id'], body=requestBody)
      try:
        response = client.update_server_metadata(request)
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
    date_attribute = "OS-SRV-USG:launched_at"

    schema = type_schema(
        'instance-age',
        op={'enum': ['greater-than', 'less-than']},
        days={'type': 'number', 'minimum': 0},
        hours={'type': 'number', 'minimum': 0},
        minutes={'type': 'number', 'minimum': 0}
    )
    
@Ecs.filter_registry.register('instance-uptime')
class EcsAgeFilter(AgeFilter):
    """Automatically filter resources older or younger than a given date.

    :Example:

    .. code-block:: yaml

        policies:
          - name: ecs-instances-age
            resource: huaweicloud.ecs
            filters:
              - type: instance-uptime
                op: greater-than
                days: 1
    """
    date_attribute = "OS-SRV-USG:launched_at"

    schema = type_schema(
        'instance-uptime',
        op={'enum': ['greater-than', 'less-than']},
        days={'type': 'number', 'minimum': 0}
    )