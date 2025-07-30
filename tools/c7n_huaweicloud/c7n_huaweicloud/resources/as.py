# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from c7n.filters.core import (
    Filter, AgeFilter,
)
from c7n.utils import local_session, type_schema

from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.actions.base import BaseAction

from huaweicloudsdkas.v1.model import (
    ResumeScalingGroupRequest, PauseScalingGroupRequest,
    UpdateScalingGroupRequest, DeleteScalingGroupRequest,
    DeleteScalingConfigRequest, ListScalingGroupsRequest,
    ListScalingConfigsRequest, ResumeScalingGroupOption,
    PauseScalingGroupOption
)
from huaweicloudsdkvpc.v2.model import (
    ShowSecurityGroupRequest, ShowSubnetRequest
)
from huaweicloudsdkelb.v2.model import (
    ShowPoolRequest
)
from huaweicloudsdkcore.exceptions import exceptions

log = logging.getLogger('custodian.huaweicloud.as')


@resources.register('as-group')
class AsGroup(QueryResourceManager):
    """Huawei Cloud Auto Scaling Group Resource

    :example:

    .. code-block:: yaml

        policies:
          - name: as-group-query
            resource: huaweicloud.as-group
    """
    class resource_type(TypeInfo):
        service = 'as-group'
        enum_spec = ('list_scaling_groups', 'scaling_groups', 'start_number')
        id = 'scaling_group_id'
        name = 'scaling_group_name'
        filter_name = 'scaling_group_name'
        filter_type = 'scalar'
        taggable = True
        tag_resource_type = 'scaling_group'


@AsGroup.filter_registry.register('by-image-id')
class ByImageIdFilter(Filter):
    """Filter Auto Scaling Groups by image ID

    :example:

    .. code-block:: yaml

        policies:
          - name: as-group-by-image-id
            resource: huaweicloud.as-group
            filters:
              - type: by-image-id
                image_id: 37ca2b35-6fc7-47ab-93c7-900324809c5c
    """
    schema = type_schema(
        'by-image-id',
        required=['image_id'],
        image_id={'type': 'string'}
    )
    permissions = ("as:scaling_configuration:list", "as:scaling_group:list")

    def process(self, resources, event=None):
        client = local_session(
            self.manager.session_factory).client('as-config')
        image_id = self.data.get('image_id')

        # First query scaling configurations using the specified image ID
        request = ListScalingConfigsRequest()
        request.image_id = image_id

        try:
            response = client.list_scaling_configs(request)
            scaling_configs = []

            if hasattr(response, 'scaling_configurations'):
                scaling_configs = response.scaling_configurations

            # Extract all configuration IDs
            config_ids = set()
            for config in scaling_configs:
                if hasattr(config, 'scaling_configuration_id'):
                    config_ids.add(config.scaling_configuration_id)

            if not config_ids:
                self.manager.log.info(
                    f"No scaling configurations found using image ID {image_id}")
                return []

            # Find scaling groups using these configurations
            results = []
            for resource in resources:
                config_id = resource.get('scaling_configuration_id')
                if config_id in config_ids:
                    resource['matched_image_id'] = image_id
                    results.append(resource)

            return results

        except Exception as e:
            self.manager.log.error(
                f"Failed to query scaling configurations with image ID {image_id}: {e}")
            return []


@AsGroup.filter_registry.register('instance-deficit')
class InstanceDeficitFilter(Filter):
    """Filter scaling groups with fewer instances than desired or minimum instance count

    :example:

    .. code-block:: yaml

        policies:
          - name: as-group-instance-deficit
            resource: huaweicloud.as-group
            filters:
              - type: instance-deficit
    """
    schema = type_schema('instance-deficit')
    permissions = ("as:scaling_instance:list",)

    def process(self, resources, event=None):
        results = []

        for resource in resources:
            # Get the current number of instances,
            # the desired number of instances, and the minimum number of instances.
            desire_instance_number = resource.get('desire_instance_number', 0)
            min_instance_number = resource.get('min_instance_number', 0)
            current_instance_number = resource.get(
                'current_instance_number', 0)

            # Check if it is less than the desired or minimum number of instances.
            if (current_instance_number < desire_instance_number or
                    current_instance_number < min_instance_number):
                resource['instance_deficit'] = True
                results.append(resource)

        return results


@AsGroup.filter_registry.register('invalid-resources')
class InvalidResourcesFilter(Filter):
    """Filter Auto Scaling Groups with invalid resources

    Identifies scaling groups with invalid subnets, ELB pools,
    or security groups based on the following conditions:
    1. Subnet no longer exists or is invalid
    2. Load balancer pool no longer exists or is invalid
    3. Security group no longer exists or is invalid

    If any of the above conditions is met, the scaling group is considered invalid.

    :example:

    .. code-block:: yaml

        policies:
          - name: as-group-with-invalid-resources
            resource: huaweicloud.as-group
            filters:
              - type: invalid-resources
    """
    schema = type_schema('invalid-resources')
    permissions = ("as:scaling_group:list", "as:scaling_configuration:list",
                   "vpc:subnets:get", "vpc:securityGroups:get", "elb:pools:get")

    def process(self, resources, event=None):
        if not resources:
            return []

        results = []

        # Step 1: Check invalid subnets
        invalid_subnet_groups = self._check_invalid_subnets(resources)
        results.extend(invalid_subnet_groups)

        # Step 2: Check invalid ELB pools
        invalid_elb_groups = self._check_invalid_elb_pools(resources)

        # Add groups with invalid ELB pools that are not already in results
        existing_group_ids = {r['scaling_group_id'] for r in results}
        for group in invalid_elb_groups:
            if group['scaling_group_id'] not in existing_group_ids:
                results.append(group)
                existing_group_ids.add(group['scaling_group_id'])

        # If we already have invalid groups from steps 1 and 2, no need to check security groups
        if results:
            return results

        # Step 3: Check invalid security groups only if no invalid resources found in steps 1 and 2
        invalid_sg_groups = self._check_invalid_security_groups(resources)
        results.extend(invalid_sg_groups)

        return results

    def _check_invalid_subnets(self, resources):
        """Check if scaling group networks are valid"""
        vpc_client = local_session(
            self.manager.session_factory).client('vpc_v2')
        invalid_groups = []
        for resource in resources:
            networks = resource.get('networks', [])
            has_invalid_subnet = False

            for network in networks:
                subnet_id = network.get('id')
                if not subnet_id:
                    continue

                try:
                    # Query subnet
                    request = ShowSubnetRequest()
                    request.subnet_id = subnet_id
                    vpc_client.show_subnet(request)
                except exceptions.ClientRequestException as e:
                    # If the response is empty or returns a 404 error code,
                    # it indicates an invalid subnet
                    self.manager.log.debug(
                        f"Invalid subnet ID {subnet_id}, error: {e.error_msg}")
                    has_invalid_subnet = True
                    break

            if has_invalid_subnet:
                resource['has_invalid_subnet'] = True
                invalid_groups.append(resource)

        return invalid_groups

    def _check_invalid_elb_pools(self, resources):
        """Check if scaling group load balancer pools are valid"""
        elb_client = local_session(
            self.manager.session_factory).client('elb_v2')
        invalid_groups = []

        for resource in resources:
            lbaas_listeners = resource.get('lbaas_listeners', [])
            has_invalid_pool = False

            for listener in lbaas_listeners:
                pool_id = listener.get('pool_id')
                if not pool_id:
                    continue

                try:
                    # Query ELB pool
                    request = ShowPoolRequest()
                    request.pool_id = pool_id
                    elb_client.show_pool(request)
                except exceptions.ClientRequestException as e:
                    # If the response is empty or returns a 404 error code,
                    # it indicates an invalid ELB pool
                    self.manager.log.debug(
                        f"Invalid ELB pool ID {pool_id}, error: {e.error_msg}")
                    has_invalid_pool = True
                    break

            if has_invalid_pool:
                resource['has_invalid_elb_pool'] = True
                invalid_groups.append(resource)

        return invalid_groups

    def _check_invalid_security_groups(self, resources):
        """Check if security groups in scaling group configuration are valid"""
        vpc_client = local_session(
            self.manager.session_factory).client('vpc_v2')
        config_client = local_session(
            self.manager.session_factory).client('as-config')
        invalid_groups = []

        # Get all resource scaling configuration IDs
        config_ids = {resource.get('scaling_configuration_id')
                      for resource in resources
                      if resource.get('scaling_configuration_id')}

        if not config_ids:
            return []

        # Query all scaling configurations
        configs = {}
        for config_id in config_ids:
            try:
                request = ListScalingConfigsRequest()
                request.scaling_configuration_id = config_id
                response = config_client.list_scaling_configs(request)

                if hasattr(response, 'scaling_configurations') and response.scaling_configurations:
                    configs[config_id] = response.scaling_configurations[0]
            except Exception as e:
                self.manager.log.error(
                    f"Failed to query scaling configuration {config_id}: {e}")

        # Check each scaling group's security groups
        for resource in resources:
            config_id = resource.get('scaling_configuration_id')
            if not config_id or config_id not in configs:
                continue

            config = configs[config_id]
            if (not hasattr(config, 'instance_config') or
                    not hasattr(config.instance_config, 'security_groups')):
                continue

            security_groups = config.instance_config.security_groups
            has_invalid_sg = False

            for sg in security_groups:
                sg_id = getattr(sg, 'id', None)
                if not sg_id:
                    continue

                try:
                    # Query security group
                    request = ShowSecurityGroupRequest()
                    request.security_group_id = sg_id
                    vpc_client.show_security_group(request)
                except exceptions.ClientRequestException as e:
                    # If the response is empty or returns a 404 error code,
                    # it indicates an invalid security group
                    self.manager.log.debug(
                        f"Invalid security group ID {sg_id}, error: {e.error_msg}")
                    has_invalid_sg = True
                    break

            if has_invalid_sg:
                resource['has_invalid_security_group'] = True
                invalid_groups.append(resource)

        return invalid_groups


@AsGroup.filter_registry.register('by-unencrypted-config')
class ByUnencryptedConfigFilter(Filter):
    """Filter scaling groups using unencrypted configurations

    Identifies scaling groups that use configurations with __system__encrypted=0

    :example:

    .. code-block:: yaml

        policies:
          - name: as-group-with-unencrypted-config
            resource: huaweicloud.as-group
            filters:
              - type: by-unencrypted-config
    """
    schema = type_schema('by-unencrypted-config')
    permissions = ("as:scaling_configuration:list", "as:scaling_group:list")

    def process(self, resources, event=None):
        client = local_session(
            self.manager.session_factory).client('as-config')

        try:
            # Query all scaling configurations
            request = ListScalingConfigsRequest()
            response = client.list_scaling_configs(request)
            scaling_configs = []

            if hasattr(response, 'scaling_configurations'):
                scaling_configs = response.scaling_configurations

            # Extract all unencrypted configuration IDs
            unencrypted_config_ids = set()
            for config in scaling_configs:
                if (hasattr(config, 'instance_config') and
                        hasattr(config.instance_config, 'disk')):
                    disks = config.instance_config.disk
                    is_unencrypted = True
                    # Check each disk's metadata for encryption status
                    for disk in disks:
                        if hasattr(disk, 'metadata'):
                            metadata = disk.metadata
                            encrypted_value = getattr(
                                metadata, 'system__encrypted', '0')
                            if encrypted_value == '1':
                                is_unencrypted = False
                                break

                    if is_unencrypted and hasattr(config, 'scaling_configuration_id'):
                        unencrypted_config_ids.add(
                            config.scaling_configuration_id)

            if not unencrypted_config_ids:
                self.manager.log.info(
                    "No unencrypted scaling configurations found")
                return []

            # Find scaling groups using these configurations
            results = []
            for resource in resources:
                config_id = resource.get('scaling_configuration_id')
                if config_id in unencrypted_config_ids:
                    resource['unencrypted_config'] = True
                    results.append(resource)

            return results

        except Exception as e:
            self.manager.log.error(
                f"Failed to query unencrypted scaling configurations: {e}")
            return []


@AsGroup.filter_registry.register('by-user-data')
class ByUserDataFilter(Filter):
    """Filter scaling groups by user_data

    First queries scaling configurations with the specified user_data,
    then finds matching scaling groups

    :example:

    .. code-block:: yaml

        policies:
          - name: as-group-by-user-data
            resource: huaweicloud.as-group
            filters:
              - type: by-user-data
                user_data: "IyEvYmluL2Jhc2gK"  # Base64 encoded user data
    """
    schema = type_schema(
        'by-user-data',
        required=['user_data'],
        user_data={'type': 'string'}
    )
    permissions = ("as:scaling_configuration:list", "as:scaling_group:list")

    def process(self, resources, event=None):
        client = local_session(
            self.manager.session_factory).client('as-config')
        user_data = self.data.get('user_data')

        try:
            # Query all scaling configurations
            request = ListScalingConfigsRequest()
            response = client.list_scaling_configs(request)
            scaling_configs = []

            if hasattr(response, 'scaling_configurations'):
                scaling_configs = response.scaling_configurations

            # Extract all configuration IDs with matching user_data
            matched_config_ids = set()
            for config in scaling_configs:
                if (hasattr(config, 'instance_config') and
                    hasattr(config.instance_config, 'user_data') and
                        config.instance_config.user_data == user_data):
                    if hasattr(config, 'scaling_configuration_id'):
                        matched_config_ids.add(config.scaling_configuration_id)

            if not matched_config_ids:
                self.manager.log.info(
                    "No scaling configurations found with the specified user_data")
                return []

            # Find scaling groups using these configurations
            results = []
            for resource in resources:
                config_id = resource.get('scaling_configuration_id')
                if config_id in matched_config_ids:
                    resource['matched_user_data'] = True
                    results.append(resource)

            return results

        except Exception as e:
            self.manager.log.error(
                f"Failed to query scaling configurations with the specified user_data: {e}")
            return []


@AsGroup.filter_registry.register('by-vpc')
class ByVpcFilter(Filter):
    """Filter scaling groups by VPC ID

    :example:

    .. code-block:: yaml

        policies:
          - name: as-group-by-vpc
            resource: huaweicloud.as-group
            filters:
              - type: by-vpc
                vpc_id: 7d9055d9-f179-4f4a-b9e6-99a7f9811f8c
    """
    schema = type_schema(
        'by-vpc',
        required=['vpc_id'],
        vpc_id={'type': 'string'}
    )
    permissions = ("as:scaling_group:list",)

    def process(self, resources, event=None):
        vpc_id = self.data.get('vpc_id')
        results = []

        for resource in resources:
            # Check if VPC ID matches
            if resource.get('vpc_id') == vpc_id:
                results.append(resource)

        return results


@AsGroup.filter_registry.register('by-network')
class ByNetworkFilter(Filter):
    """Filter scaling groups by network ID

    Filters scaling groups that include the specified network ID in their networks list

    :example:

    .. code-block:: yaml

        policies:
          - name: as-group-by-network
            resource: huaweicloud.as-group
            filters:
              - type: by-network
                network_id: 5d9055d9-f179-4f4a-b9e6-99a7f9811f8c
    """
    schema = type_schema(
        'by-network',
        required=['network_id'],
        network_id={'type': 'string'}
    )
    permissions = ("as:scaling_group:list",)

    def process(self, resources, event=None):
        network_id = self.data.get('network_id')
        results = []

        for resource in resources:
            networks = resource.get('networks', [])

            # Check if networks list contains the specified network_id
            for network in networks:
                if network.get('id') == network_id:
                    results.append(resource)
                    break

        return results


@AsGroup.action_registry.register('delete')
class DeleteAsGroup(BaseAction):
    """Delete Auto Scaling Group

    :example:

    .. code-block:: yaml

        policies:
          - name: delete-as-group
            resource: huaweicloud.as-group
            filters:
              - type: value
                key: scaling_group_status
                value: INSERVICE
            actions:
              - type: delete
                force: "yes"
    """
    schema = type_schema(
        'delete',
        force={'type': 'string'}
    )
    permissions = ("as:scaling_group:delete",)

    def process(self, resources):
        client = local_session(self.manager.session_factory).client('as-group')
        force = self.data.get('force', 'no')

        for resource in resources:
            self.process_resource(client, resource, force)

    def process_resource(self, client, resource, force):
        group_id = resource['scaling_group_id']

        # Create delete request
        request = DeleteScalingGroupRequest()
        request.scaling_group_id = group_id
        request.force_delete = force

        try:
            client.delete_scaling_group(request)
            self.manager.log.info(
                f"Successfully deleted scaling group: {group_id}")
        except Exception as e:
            self.manager.log.error(
                f"Failed to delete scaling group {group_id}: {e}")


@AsGroup.action_registry.register('enable')
class EnableAsGroup(BaseAction):
    """Enable Auto Scaling Group

    :example:

    .. code-block:: yaml

        policies:
          - name: enable-as-group
            resource: huaweicloud.as-group
            filters:
              - type: value
                key: scaling_group_status
                value: PAUSED
            actions:
              - type: enable
    """
    schema = type_schema('enable')
    permissions = ("as:scaling_group:resume",)

    def process(self, resources):
        if not resources:
            return

        client = local_session(self.manager.session_factory).client('as-group')

        # Enable each scaling group
        for resource in resources:
            group_id = resource['scaling_group_id']

            # Create enable request
            request = ResumeScalingGroupRequest()
            request.scaling_group_id = group_id

            body = ResumeScalingGroupOption()
            body.action = "resume"
            request.body = body

            try:
                client.resume_scaling_group(request)
                self.manager.log.info(
                    f"Successfully enabled scaling group: {group_id}")
            except Exception as e:
                self.manager.log.error(
                    f"Failed to enable scaling group {group_id}: {e}")


@AsGroup.action_registry.register('disable')
class DisableAsGroup(BaseAction):
    """Disable Auto Scaling Group

    :example:

    .. code-block:: yaml

        policies:
          - name: disable-as-group
            resource: huaweicloud.as-group
            filters:
              - type: value
                key: scaling_group_status
                value: INSERVICE
            actions:
              - type: disable
    """
    schema = type_schema('disable')
    permissions = ("as:scaling_group:pause",)

    def process(self, resources):
        if not resources:
            return

        client = local_session(self.manager.session_factory).client('as-group')

        # Disable each scaling group
        for resource in resources:
            group_id = resource['scaling_group_id']

            # Create disable request
            request = PauseScalingGroupRequest()
            request.scaling_group_id = group_id

            body = PauseScalingGroupOption()
            body.action = "pause"
            request.body = body

            try:
                client.pause_scaling_group(request)
                self.manager.log.info(
                    f"Successfully disabled scaling group: {group_id}")
            except Exception as e:
                self.manager.log.error(
                    f"Failed to disable scaling group {group_id}: {e}")


@AsGroup.action_registry.register('update')
class UpdateAsGroup(BaseAction):
    """Update Auto Scaling Group

    :example:

    .. code-block:: yaml

        policies:
          - name: update-as-group
            resource: huaweicloud.as-group
            filters:
              - type: value
                key: scaling_group_status
                value: INSERVICE
            actions:
              - type: update
                min_instance_number: 1
                max_instance_number: 10
                desire_instance_number: 2
    """
    schema = type_schema(
        'update',
        scaling_group_name={'type': 'string', 'minLength': 1, 'maxLength': 64},
        min_instance_number={'type': 'integer', 'minimum': 0},
        max_instance_number={'type': 'integer', 'minimum': 0},
        desire_instance_number={'type': 'integer', 'minimum': 0},
        cool_down_time={'type': 'integer', 'minimum': 0, 'maximum': 86400},
        health_periodic_audit_method={'enum': ['ELB_AUDIT', 'NOVA_AUDIT']},
        health_periodic_audit_time={'type': 'integer'},
        health_periodic_audit_grace_period={'type': 'integer', 'minimum': 0},
        instance_terminate_policy={'enum': [
            'OLD_CONFIG_OLD_INSTANCE',
            'OLD_CONFIG_NEW_INSTANCE',
            'OLD_INSTANCE',
            'NEW_INSTANCE'
        ]},
        scaling_configuration_id={'type': 'string'},
        notifications={'type': 'array', 'items': {'type': 'string'}},
        enterprise_project_id={'type': 'string'},
        multi_az_priority_policy={
            'enum': ['EQUILIBRIUM_DISTRIBUTE', 'PICK_FIRST']},
        available_zones={'type': 'array', 'items': {'type': 'string'}},
        networks={'type': 'array', 'items': {'type': 'object', 'properties': {
            'id': {'type': 'string'},
            'ipv6_enable': {'type': 'boolean'},
            'ipv6_bandwidth': {'type': 'object',
                               'properties': {'id': {'type': 'string'}}, 'required': ['id']},
            'allowed_address_pairs': {'type': 'array', 'items':
                    {'type': 'object', 'properties': {'ip_address': {'type': 'string'}}}}
        }, 'required': ['id']}},
        security_groups={'type': 'array', 'items': {'type': 'object', 'properties': {
            'id': {'type': 'string'}}, 'required': ['id']}},
        lbaas_listeners={'type': 'array', 'items': {'type': 'object', 'properties': {
            'pool_id': {'type': 'string'},
            'protocol_port': {'type': 'integer'},
            'weight': {'type': 'integer'},
            'protocol_version': {'type': 'string'}
        }, 'required': ['pool_id', 'protocol_port']}},
        iam_agency_name={'type': 'string'}
    )
    permissions = ("as:scaling_group:update",)

    def process(self, resources):
        client = local_session(self.manager.session_factory).client('as-group')

        for resource in resources:
            self.process_resource(client, resource)

    def process_resource(self, client, resource):
        group_id = resource['scaling_group_id']

        # 创建更新请求
        request = UpdateScalingGroupRequest()
        request.scaling_group_id = group_id

        # Build update parameters
        body = {}
        for key in self.schema['properties']:
            if key != 'type' and key in self.data:
                # Convert key format (snake_case to camelCase)
                body[key] = self.data[key]

        request.body = body

        try:
            client.update_scaling_group(request)
            self.manager.log.info(
                f"Successfully updated scaling group: {group_id}")
        except Exception as e:
            self.manager.log.error(
                f"Failed to update scaling group {group_id}: {e}")


@resources.register('as-config')
class AsConfig(QueryResourceManager):
    """Huawei Cloud Auto Scaling Configuration Resource

    :example:

    .. code-block:: yaml

        policies:
          - name: as-config-query
            resource: huaweicloud.as-config
    """
    class resource_type(TypeInfo):
        service = 'as-config'
        enum_spec = ('list_scaling_configs',
                     'scaling_configurations', 'start_number')
        id = 'scaling_configuration_id'
        name = 'scaling_configuration_name'
        filter_name = 'scaling_configuration_name'
        filter_type = 'scalar'
        taggable = False


@AsConfig.filter_registry.register('not-in-use')
class NotInUseFilter(Filter):
    """Filter unused scaling configurations

    :example:

    .. code-block:: yaml

        policies:
          - name: as-config-not-in-use
            resource: huaweicloud.as-config
            filters:
              - type: not-in-use
    """
    schema = type_schema('not-in-use')
    permissions = ("as:scaling_group:list",)

    def get_scaling_groups(self):
        client = local_session(self.manager.session_factory).client('as-group')
        request = ListScalingGroupsRequest()
        response = client.list_scaling_groups(request)

        scaling_groups = []
        if hasattr(response, 'scaling_groups'):
            scaling_groups = response.scaling_groups

        return scaling_groups

    def process(self, resources, event=None):
        scaling_groups = self.get_scaling_groups()

        # Extract all configurations IDs in use
        in_use_configs = set()
        for group in scaling_groups:
            if hasattr(group, 'scaling_configuration_id') and group.scaling_configuration_id:
                in_use_configs.add(group.scaling_configuration_id)

        results = []
        for resource in resources:
            config_id = resource.get('scaling_configuration_id')
            # Only keep configurations not in use
            if config_id not in in_use_configs:
                resource['in_use'] = False
                results.append(resource)

        return results


@AsConfig.action_registry.register('delete')
class DeleteAsConfig(BaseAction):
    """Delete Auto Scaling Configuration

    :example:

    .. code-block:: yaml

        policies:
          - name: delete-as-config
            resource: huaweicloud.as-config
            filters:
              -type: value,
                key: scaling_configuration_id,
                value: test-scaling-configuration-id
            actions:
              - type: delete
    """
    schema = type_schema('delete')
    permissions = ("as:scaling_configuration:delete",)

    def process(self, resources):
        client = local_session(
            self.manager.session_factory).client('as-config')

        for resource in resources:
            self.process_resource(client, resource)

    def process_resource(self, client, resource):
        config_id = resource['scaling_configuration_id']

        # Create delete request
        request = DeleteScalingConfigRequest()
        request.scaling_configuration_id = config_id

        try:
            client.delete_scaling_config(request)
            self.manager.log.info(
                f"Successfully deleted scaling configuration: {config_id}")
        except Exception as e:
            self.manager.log.error(
                f"Failed to delete scaling configuration {config_id}: {e}")


@AsConfig.filter_registry.register('age')
class AsConfigAgeFilter(AgeFilter):
    """Auto Scaling Configuration Resource Creation Time Filter

    Filters resources based on the creation time of the Auto Scaling Configuration resource.

    :example:
    Find Auto Scaling Configuration resources created more than 90 days ago:

    .. code-block:: yaml

        policies:
          - name: as-config-older-than-90-days
            resource: huaweicloud.as-config
            filters:
              - type: age                   # Filter type
                days: 90                    # Specify days
                op: gt                      # gt means "greater than" (earlier than)
                                            # Other available operators: lt (later than), ge, le
    """
    # Define this filter's input pattern
    schema = type_schema(
        'age',  # Filter type name
        # Define comparison operation, referencing common filter definition
        op={'$ref': '#/definitions/filters_common/comparison_operators'},
        # Define time unit parameter
        days={'type': 'number'},  # Days
        hours={'type': 'number'},  # Hours
        minutes={'type': 'number'}  # Minutes
    )

    # Specify the name of the date attribute in the resource dictionary
    date_attribute = "create_time"


@resources.register('as-policy')
class AsPolicy(QueryResourceManager):
    """Huawei Cloud Auto Scaling Policy Resource

    :example:

    .. code-block:: yaml

        policies:
          - name: as-policy-query
            resource: huaweicloud.as-policy
    """
    class resource_type(TypeInfo):
        service = 'as-policy'
        enum_spec = ('list_all_scaling_v2_policies',
                     'scaling_policies', 'start_number')
        id = 'scaling_policy_id'
        name = 'scaling_policy_name'
        filter_name = 'scaling_policy_name'
        filter_type = 'scalar'
        taggable = False
