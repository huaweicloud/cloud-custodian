
import logging
import base64
import json
import zlib
import time
from typing import List
from concurrent.futures import as_completed

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkevs.v2 import *
from huaweicloudsdkecs.v2 import *
from huaweicloudsdkims.v2 import *
from huaweicloudsdkcbr.v1 import *

from c7n import utils
from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n.filters import *
from dateutil.parser import parse

log = logging.getLogger("custodian.huaweicloud.resources.ecs")


@resources.register('ecs')
class Ecs(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'ecs'
        enum_spec = ("list_servers_details", "servers", "offset")
        id = 'id'
        tag_resource_type = 'ecs'

@Ecs.action_registry.register("fetch-job-status")
class FetchJobStatus(HuaweiCloudBaseAction):
    
  schema = type_schema("fetch-job-status", job_id={'type': 'string'}, required=('job_id',))

  def process(self, resources):
      job_id = self.data.get('job_id')
      client = self.manager.get_client()
      request = ShowJobRequest(job_id=job_id)
      try:
        response = client.show_job(request)
      except exceptions.ClientRequestException as e:
        log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
        raise
      return json.dumps(response.to_dict())
  
  def perform_action(self, resource):
      return super().perform_action(resource)

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
    valid_origin_states = ('SHUTOFF',)
    schema = type_schema("instance-start")

    def process(self, resources):
        client = self.manager.get_client()
        instances = self.filter_resources(resources, 'status', self.valid_origin_states)
        if not instances:
            log.warning("No instance need start")
            return None
        request = self.init_request(instances)
        try:
          response = client.batch_start_servers(request)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return json.dumps(response.to_dict())

    def init_request(self, instances):
        serverIds : List[ServerId] = []
        for r in instances:
            serverIds.append(ServerId(id=r['id']))
        options = {"servers":serverIds}
        requestBody = BatchStartServersRequestBody(os_start=options)
        request = BatchStartServersRequest(body=requestBody)
        return request
    
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
    valid_origin_states = ('ACTIVE',)
    schema = type_schema("instance-stop", mode={'type': 'string'})

    def process(self, resources):
        client = self.manager.get_client()
        instances = self.filter_resources(resources, 'status', self.valid_origin_states)
        if not instances:
            log.warning("No instance need stop")
            return None
        request = self.init_request(instances)
        try:
          response = client.batch_stop_servers(request)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return json.dumps(response.to_dict())

    def init_request(self, resources):
        serverIds : List[ServerId] = []
        for r in resources:
            serverIds.append(ServerId(id=r['id']))
        options = {"servers":serverIds,"type": self.data.get('mode', 'SOFT')}
        requestBody = BatchStopServersRequestBody(os_stop=options)
        request = BatchStopServersRequest(body=requestBody)
        return request
    
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

    valid_origin_states = ('ACTIVE',)
    schema = type_schema("instance-reboot", mode={'type': 'string'})

    def process(self, resources):
        client = self.manager.get_client()
        instances = self.filter_resources(resources, 'status', self.valid_origin_states)
        if not instances:
            log.warning("No instance need stop")
            return None
        request = self.init_request(instances)
        try:
          response = client.batch_reboot_servers(request)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return json.dumps(response.to_dict())

    def init_request(self, resources):
        serverIds : List[ServerId] = []
        for r in resources:
            serverIds.append(ServerId(id=r['id']))
        options = {"servers":serverIds,"type": self.data.get('mode', 'SOFT')}
        requestBody = BatchRebootServersRequestBody(reboot=options)
        request = BatchRebootServersRequest(body=requestBody)
        return request
    
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

    schema = type_schema("instance-terminate")

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
      
@Ecs.action_registry.register("instance-delete-security-groups")
class DeleteSecurityGroup(HuaweiCloudBaseAction):
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
        option = NovaRemoveSecurityGroupOption(name=name)
        requestBody = NovaDisassociateSecurityGroupRequestBody(remove_security_group=option)
        request = NovaDisassociateSecurityGroupRequest(server_id=resource["id"], body=requestBody)
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
              - type: value
                key: id
                value: "bac642b0-a9ca-4a13-b6b9-9e41b35905b6"
            actions:
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
    """Set Profile For An Ecs Server Flavor.

    :Example:

    .. code-block:: yaml

        policies:
          - name: set-instance-profile
            resource: huaweicloud.ecs
            filters:
              - type: value
                key: id
                value: "bac642b0-a9ca-4a13-b6b9-9e41b35905b6"
            actions:
              - type: set-instance-profile
                metadata:
                  key: value
    """

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

@Ecs.action_registry.register("instance-whole-image")
class InstanceWholeImage(HuaweiCloudBaseAction):
    """Create whole image backup for an ECS instance.

    - `vault_id` CBR vault_id the instance was associated
    - `name` whole image name

    :Example:

    .. code-block:: yaml
       
       policies:
         - name: instance-whole-image
           resource: huaweicloud.ecs
           actions:
             - type: instance-whole-image
               name: "wholeImage"
               vault_id: "your CBR vault id"
               instance_id: "your instance id"       
    """

    schema = type_schema('instance-snapshot',
                         instance_id = {'type': 'string'},
                         name = {'type': 'string'},
                         vault_id = {'type': 'string'},
                         required=('instance_id','name', 'vault_id'))
    
    def perform_action(self, resource):
        return super().perform_action(resource)
    
    def process(self, resources):
        ims_client = self.manager.get_resource_manager('huaweicloud.ims')
        requestBody = CreateWholeImageRequestBody(name=self.data.get('name'), 
                                                  instance_id=self.data.get('instance_id'),
                                                  vault_id=self.data.get('vault_id'))
        request = CreateWholeImageRequest(body=requestBody)
        try:
          response = ims_client.create_whole_image(request)
          if response.status_code != 200:
              log.error("create whole image for instance %s fail" % self.data.get('instance_id'))
              return False
          return self.wait_backup(response['job_id'], ims_client)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
    
    def wait_backup(self, job_id, ims_client):
        while(True):
            status = self.fetch_ims_job_status(job_id, ims_client)
            if status is "SUCCESS":
                return True
            time.sleep(5)

    def fetch_ims_job_status(self, job_id, ims_client):
        request = ShowJobProgressRequest(job_id=job_id)
        try:
          response = ims_client.show_job_progress(request)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return response['status']

@Ecs.action_registry.register("instance-snapshot")
class InstanceSnapshot(HuaweiCloudBaseAction):
    """CBR backup the volumes attached to an ECS instance.

    - `vault_id` CBR vault_id the instance was associated
    - `incremental` false : full server volumes backup
                    true : incremental of server volumes backup

    :Example:

    .. code-block:: yaml
       
       policies:
         - name: instance-snapshot
           resource: huaweicloud.ecs
           actions:
             - type: instance-snapshot
               incremental: false               
    """

    schema = type_schema('instance-snapshot',
                         vault_id = {'type': 'string'},
                         incremental = {'type': 'boolean'})

    def perform_action(self, resource):
        return super().perform_action(resource)
    
    def process(self, resources):
        cbr_client = self.manager.get_resource_manager('huaweicloud.cbr')
        vaults = self.list_vault(cbr_client)
        vaults_resource_ids = self.fetch_vaults_resource_ids(vaults)
        response = self.back_up(resources, vaults_resource_ids, cbr_client)
        return response
    
    def back_up(self, resources, vaults_resource_ids, cbr_client):
        for r in resources:
            server_id = r['id']
            vault_id = vaults_resource_ids[server_id]
            if self.data.get('vault_id', None) is not None:
              if vault_id is not None:
                  return self.checkpoint_and_wait(r, vault_id, server_id, cbr_client)
              else:
                add_resource_response = self.add_vault_resource(vault_id, server_id, cbr_client)
                if add_resource_response.status_code != 200:
                    log.error("add instance %s to vault error" % server_id)
                    return False
                return self.checkpoint_and_wait(r, vault_id, server_id, cbr_client)
            else:
                add_resource_response = self.add_vault_resource(vault_id, server_id, cbr_client)
                if add_resource_response.status_code != 200:
                    log.error("add instance %s to vault error" % server_id)
                    return False
                return self.checkpoint_and_wait(r, vault_id, server_id, cbr_client)
          
    def wait_backup(self, vault_id, resource_id, cbr_client):
        while(True):
            response = self.list_op_log(resource_id, vault_id, cbr_client)
            op_logs = response['operation_logs']
            if not op_logs:
                time.slepp(3)
                continue
            return True

    def checkpoint_and_wait(self, r, vault_id, server_id, cbr_client):
        checkpoint_response = self.create_checkpoint_for_instance(r, vault_id, cbr_client)
        if checkpoint_response.status_code != 200:
            log.error("instance %s backup error" % server_id)
            return False
        return self.wait_backup(vault_id, server_id, cbr_client)

    def create_checkpoint_for_instance(self, r, vault_id, cbr_client):
        resource_details = list[Resource(id=r['id'], type="OS::Nova::Server")]
        params = CheckpointParam(resource_details=resource_details, incremental=self.data.get('incremental', True))
        backup = VaultBackup(vault_id=vault_id,parameters=params)
        try:
            response = self.create_checkpoint(cbr_client, backup)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return response

    def fetch_vaults_resource_ids(self, vaults):
        vaults_resource_ids = {}
        for vault in vaults:
            resources = vault['resources']
            for r in resources:
                if r['protect_status'] == 'available':
                    vaults_resource_ids.setdefault(vault['id'], r['id'])
        return vaults_resource_ids

    def list_vault(self, cbr_client):
        request = ListVaultRequest()
        try:
            response = cbr_client.list_vault(request)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return response
    
    def show_vault(self, cbr_client, vault_id):
        request = ShowVaultRequest(vault_id=vault_id)
        try:
            response = cbr_client.show_vault(request)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return response
    
    def add_vault_resource(self, cbr_client, vault_id, resources:ResourceCreate):
        requestBody = VaultAddResourceReq(resources=resources)
        request = AddVaultResourceRequest(vault_id=vault_id, body=requestBody)
        try:
            response = cbr_client.add_vault_resource(request)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return response
    
    def show_op_log_by_op_log_id(self, cbr_client, op_log_id):
        request = ShowOpLogRequest(operation_log_id=op_log_id)
        try:
            response = cbr_client.show_op_log(request)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return response
    
    def list_op_log(self, resource_id, vault_id, cbr_client):
        request = ListOpLogsRequest(status="running",vault_id=vault_id,resource_id=resource_id)
        try:
            response = cbr_client.list_op_logs(request)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return response
    
    def create_checkpoint(self, cbr_client, backup:VaultBackup):
        requestBody = VaultBackupReq(checkpoint=backup)
        request = CreateCheckpointRequest(body=requestBody)
        try:
            response = cbr_client.show_op_log(request)
        except exceptions.ClientRequestException as e:
          log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
          raise
        return response
        
    def vault_add_resource(self, vault_id, server_id, cbr_client):
        resource = ResourceCreate(id=server_id, type="OS::Nova::Server")
        requestBody = VaultAddResourceReq(resources=resource)
        request = AddVaultResourceRequest(vault_id=vault_id, body=requestBody)
        try:
            response = cbr_client.add_vault_resource(request)
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
    date_attribute = "created"

    schema = type_schema(
        'instance-uptime',
        op={'$ref': '#/definitions/filters_common/comparison_operators'},
        days={'type': 'number'})
    
@Ecs.filter_registry.register('instance-attribute')
class InstanceAttributeFilter(ValueFilter):
    """ECS Instance Value Filter on a given instance attribute.

    :Example:

    .. code-block:: yaml

        policies:
          - name: ec2-unoptimized-ebs
            resource: ec2
            filters:
              - type: instance-attribute
                attribute: OS-EXT-SRV-ATTR:user_data
                key: "Value"
                op: regex
                value: (?smi).*user=
    """

    valid_attrs = (
        'flavorId',
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
            userData = resource.get('OS-EXT-SRV-ATTR:user_data', '')
            flavorId = resource['flavor']['id']
            rootDeviceName = ['OS-EXT-SRV-ATTR:root_device_name']
            attributes = {'OS-EXT-SRV-ATTR:user_data': {'Value':deserialize_user_data(userData)},
                          'flavorId': {'Value':flavorId},
                          'OS-EXT-SRV-ATTR:root_device_name': {'Value':rootDeviceName}}
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
        
@Ecs.filter_registry.register('instance-evs')
class InstanceEvs(ValueFilter):
    """ECS instance with EVS volume.

    Filter ECS instances with EVS storage devices, not ephemeral 

    :Example:

    .. code-block:: yaml
       
       policies:
         - name: instance-evs
           resource: huaweicloud.ecs
           filters:
             - type: instance-evs
               key: encrypted
               op: eq
               value: false               
    """

    schema = type_schema('instance-evs', rinherit=ValueFilter.schema,
                         **{'skip-devices': {'type': 'array', 'items': {'type': 'string'}}})
    schema_alias = False

    def process(self, resources, event=None):
        self.volume_map = self.get_volume_mapping(resources)
        self.skip = self.data.get('skip-devices', [])
        self.operator = self.data.get(
          'operator', 'or') == 'or' and any or all
        return list(filter(self, resources))
    
    def get_volume_mapping(self, resources):
        volume_map = {}
        evsResources = self.manager.get_resource_manager('huaweicloud.volume').resources()
        for resource in resources:
            for evs in evsResources:
                evsServerIds = list(item['server_id'] for item in evs['attachments'])
                if resource['id'] in evsServerIds:
                    volume_map.setdefault(resource['id'], evs)
                    break
        return volume_map
    
    def __call__(self, i):
        volumes = self.volume_map.get(i['id'])
        if not volumes:
            return False
        if self.skip:
            for v in list(volumes):
                for a in v.get('id', []):
                    if a['id'] in self.skip:
                        volumes.remove(v)
        return self.match(volumes)

@Ecs.filter_registry.register('instance-vpc')
class InstanceVpc():
    """ECS instance with VPC.

    Filter ECS instances with VPC id

    :Example:

    .. code-block:: yaml
       
       policies:
         - name: instance-vpc
           resource: huaweicloud.ecs
           filters:
             - type: instance-vpc           
    """

    schema = type_schema('instance-vpc')
    schema_alias = False

    def process(self, resources, event=None):
        return self.get_vpcs(resources)

    def get_vpcs(self, resources):
        result = []
        vpcIds = list(item.metadata['vpc_id'] for item in resources)
        vpcs = self.manager.get_resource_manager('huaweicloud.vpc').resources()
        for resource in resources:
            for vpc in vpcs:
                vpcId = vpc['id']
                if vpcId in vpcIds:
                    result.append(resource)
                    break
        return result
