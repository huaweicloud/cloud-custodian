
import logging
import base64
import json
import zlib
from typing import List
from concurrent.futures import as_completed

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkevs.v2 import *
from huaweicloudsdkecs.v2 import *

from c7n import utils
from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n.filters import *
from c7n.filters.offhours import OffHour, OnHour
from dateutil.parser import parse

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

    def process(self, resources):
        client = self.manager.get_client()
        serverIds : List[ServerId] = []
        for r in resources:
            serverIds.append(ServerId(id=r['id']))
        options = {"servers":serverIds}
        requestBody = BatchStartServersRequestBody(os_start=options)
        request = BatchStartServersRequest(body=requestBody)
        try:
          response = client.batch_start_servers(request)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return json.dumps(response.to_dict())
    
    def perform_action(self, resource):
       return super().perform_action(resource)

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

    def process(self, resources):
        client = self.manager.get_client()
        serverIds : List[ServerId] = []
        for r in resources:
            serverIds.append(ServerId(id=r['id']))
        options = {"servers":serverIds,"type": self.data.get('mode', 'SOFT')}
        requestBody = BatchStopServersRequestBody(os_stop=options)
        request = BatchStopServersRequest(body=requestBody)
        try:
          response = client.batch_stop_servers(request)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return json.dumps(response.to_dict())
    
    def perform_action(self, resource):
       return super().perform_action(resource)

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

    def process(self, resources):
        client = self.manager.get_client()
        serverIds : List[ServerId] = []
        for r in resources:
            serverIds.append(ServerId(id=r['id']))
        options = {"servers":serverIds,"type": self.data.get('mode', 'SOFT')}
        requestBody = BatchRebootServersRequestBody(reboot=options)
        request = BatchRebootServersRequest(body=requestBody)
        try:
          response = client.batch_reboot_servers(request)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return json.dumps(response.to_dict())
    
    def perform_action(self, resource):
       return super().perform_action(resource)

      
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
                op: ge
                days: 1
    """
    date_attribute = "created"

    schema = type_schema(
        'instance-age',
        op={'$ref': '#/definitions/filters_common/comparison_operators'},
        days={'type': 'number'},
        hours={'type': 'number'},
        minutes={'type': 'number'})
    
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
                op: ge
                days: 1
    """
    date_attribute = "OS-SRV-USG:launched_at"

    schema = type_schema(
        'instance-uptime',
        op={'$ref': '#/definitions/filters_common/comparison_operators'},
        days={'type': 'number'})
    
@Ecs.filter_registry.register('instance-attribute')
class InstanceAttributeFilter(ValueFilter):
    """Automatically filter resources older or younger than a given date.

    :Example:

    .. code-block:: yaml

        policies:
          - name: ec2-unoptimized-ebs
            resource: ec2
            filters:
              - type: instance-attribute
                attribute: ebsOptimized
                key: "Value"
                value: false
    """

    valid_attrs = (
        'id',
        'flavor.id',
        'OS-EXT-SRV-ATTR:user_data',
        'OS-EXT-SRV-ATTR:root_device_name')

    schema = type_schema(
        'instance-attribute',
        rinherit=ValueFilter.schema,
        attribute={'enum': valid_attrs},
        required=('attribute',))
    schema_alias = False

    def process(self, resources, event=None):
        attribute = self.data['attribute']
        self.get_instance_attribute(resources, attribute)
        return [resource for resource in resources
                if self.match(resource['c7n:attribute-%s' % attribute])]

    def get_instance_attribute(self, resources, attribute):
        for resource in resources:
            id = resource.get('id')
            userData = resource.get('OS-EXT-SRV-ATTR:user_data', None)
            flavorId = resource['flavor']['id']
            rootDeviceName = ['OS-EXT-SRV-ATTR:root_device_name']
            attributes = {'id': id,
                          'OS-EXT-SRV-ATTR:user_data': userData,
                          'flavor.id': flavorId,
                          'OS-EXT-SRV-ATTR:root_device_name': rootDeviceName}
            resource['c7n:attribute-%s' % attribute] = attributes[attribute]

class InstanceImageBase:

    def prefetch_instance_images(self, instances):
        image_ids = [i['id'] for i in instances if 'image:id' not in i]
        self.image_map = self.get_local_image_mapping(image_ids)

    def get_base_image_mapping(self):
      
        return {i['id']: i for i in
                self.manager.get_resource_manager('huaweicloud.ims').resources()}

    def get_instance_image(self, instance):
        image = instance.get('image:id', None)
        if not image:
            image = instance['iamge:id'] = self.image_map.get(instance['id'], None)
        return image

    def get_local_image_mapping(self, image_ids):
        base_image_map = self.get_base_image_mapping()
        resources = {i: base_image_map[i] for i in image_ids if i in base_image_map}
        missing = list(set(image_ids) - set(resources.keys()))
        if missing:
            loaded = self.manager.get_resource_manager('huaweicloud.ims').get_resources(missing)
            resources.update({image['id']: image for image in loaded})
        return resources

@Ecs.filter_registry.register('image-age')
class ImageAgeFilter(AgeFilter, InstanceImageBase):
    """EC2 AMI age filter

    Filters EC2 instances based on the age of their AMI image (in days)

    :Example:

    .. code-block:: yaml

        policies:
          - name: ec2-ancient-ami
            resource: ec2
            filters:
              - type: image-age
                op: ge
                days: 90
    """

    date_attribute = "created_at"

    schema = type_schema(
        'image-age',
        op={'$ref': '#/definitions/filters_common/comparison_operators'},
        days={'type': 'number'})

    def process(self, resources, event=None):
        self.prefetch_instance_images(resources)
        return super(ImageAgeFilter, self).process(resources, event)

    def get_resource_date(self, i):
        image = self.get_instance_image(i)
        log.info(str(image))
        if image:
            return parse(image['created_at'])
        else:
            return parse("2000-01-01T01:01:01.000Z")


@Ecs.filter_registry.register('instance-image')
class InstanceImageFilter(ValueFilter, InstanceImageBase):

    schema = type_schema('instance-image', rinherit=ValueFilter.schema)
    schema_alias = False

    def process(self, resources, event=None):
        self.prefetch_instance_images(resources)
        return super(InstanceImageFilter, self).process(resources, event)

    def __call__(self, i):
        image = self.get_instance_image(i)
        if not image:
            return False
        return self.match(image)
    
 
@Ecs.filter_registry.register("ephemeral")
class InstanceEphemeralFilter(Filter):

    """EC2 instances with ephemeral storage

    Filters EC2 instances that have ephemeral storage (an instance-store backed
    root device)

    :Example:

    .. code-block:: yaml

        policies:
          - name: ephemeral
            resource: huaweicloud.ecs
            filters:
              - type: ephemeral

    """
   
    schema = type_schema('ephemeral')

    def __call__(self, i):
       return self.is_ephemeral(i)

    def is_ephemeral(self, i):
        performancetype = self.get_resource_flavor_performancetype(i["flavor"]["id"])
        if performancetype in ('highio', 'diskintensive'):
            return True
        return False
    
    def get_resource_flavor_performancetype(self, flavorId):
        request = NovaShowFlavorExtraSpecsRequest(flavor_id=flavorId)
        client = self.manager.get_client()
        try:
           response = client.nova_show_flavor_extra_specs(request)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return response.extra_specs["ecs:performancetype"]

def deserialize_user_data(user_data):
    data = base64.b64decode(user_data)
    # try raw and compressed
    try:
        return data.decode('utf8')
    except UnicodeDecodeError:
        return zlib.decompress(data, 16).decode('utf8')

@Ecs.filter_registry.register("instance-user-data")
class InstanceUserData(ValueFilter):
    """Filter on EC2 instances which have matching userdata.
    Note: It is highly recommended to use regexes with the ?sm flags, since Custodian
    uses re.match() and userdata spans multiple lines.

        :example:

        .. code-block:: yaml

            policies:
              - name: ecs_instance-user-data
                resource: ec2
                filters:
                  - type: instance-user-data
                    op: regex
                    value: (?smi).*user=
                actions:
                  - instance-stop
    """

   
    schema = type_schema('instance-user-data', rinherit=ValueFilter.schema)
    schema_alias = False
    batch_size = 50
    annotation = 'OS-EXT-SRV-ATTR:user_data'

    def __init__(self, data, manager):
        super(InstanceUserData, self).__init__(data, manager)
        self.data['key'] = "OS-EXT-SRV-ATTR:user_data"
    
    def process(self, resources, event=None):
        results = []
        with self.executor_factory(max_workers=3) as w:
             futures = {}
             for instance_set in utils.chunks(resources, self.batch_size):
                 futures[w.submit(self.process_instance_user_data, instance_set)] = instance_set

             for f in as_completed(futures):
                 if f.exception():
                    self.log.error("Error processing userdata on instance set %s", f.exception())
                 results.extend(f.result())
        return results
    
    def process_instance_user_data(self, resources):
        results = []
        for r in resources:
            try:
               result = self.get_instance_info_detail(r['id'])
            except exceptions.ClientRequestException as e:
                raise
            if result is None:
                r[self.annotation] = None
            else:
                r[self.annotation] = deserialize_user_data(result)
            if self.match(r):
                results.append(r)
        return results
    
    def get_instance_info_detail(self, serverId):
        request = ShowServerRequest(server_id=serverId)
        client = self.manager.get_client()
        try:
          response = client.show_server(request)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return response.server.os_ext_srv_att_ruser_data