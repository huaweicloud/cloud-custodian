# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkapig.v2 import (
    # API interface related
    DeleteApiV2Request,
    UpdateApiV2Request,
    ListApisV2Request,
    ShowDetailsOfApiV2Request,

    # Environment related
    UpdateEnvironmentV2Request,
    DeleteEnvironmentV2Request,
    ListEnvironmentsV2Request,

    # Domain related
    UpdateDomainV2Request,

    # Group related
    ListApiGroupsV2Request,
    ShowDetailsOfApiGroupV2Request,

    # Instance related
    ListInstancesV2Request,
)

from c7n.filters.core import AgeFilter
from c7n.utils import type_schema, local_session
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction

log = logging.getLogger('custodian.huaweicloud.apig')


# APIG Instance Resource Management
@resources.register('apig-instance')
class InstanceResource(QueryResourceManager):
    """Huawei Cloud API Gateway Instance Resource Management

    :example:

    .. code-block:: yaml

        policies:
          - name: apig-instance-list
            resource: huaweicloud.apig-instance
            filters:
              - type: value
                key: status
                value: Running
    """

    class resource_type(TypeInfo):
        service = 'apig-instance'
        enum_spec = ('list_instances_v2', 'instances', 'offset')
        id = 'id'
        name = 'instance_name'
        filter_name = 'instance_name'
        filter_type = 'scalar'
        taggable = True
        tag_resource_type = 'apig'

    def process_resources(self, resources):
        """Process resource data, ensure fields like project_id exist"""
        processed_resources = []
        
        for resource in resources:
            resource_dict = {}
            
            # Extract data from original attributes first
            if hasattr(resource, '__dict__') and hasattr(resource, '_field_names'):
                # Process SDK object mode
                for field in resource._field_names:
                    if hasattr(resource, field):
                        value = getattr(resource, field)
                        # Ensure values are serializable basic types
                        if isinstance(value, (str, int, float, bool, type(None))) or (
                            isinstance(value, (list, dict)) and not any(
                                hasattr(item, '__dict__') for item in value) if isinstance(value, list) else True
                        ):
                            resource_dict[field] = value
            else:
                # Process dictionary mode
                for key, value in resource.items() if isinstance(resource, dict) else []:
                    # Ensure values are serializable basic types
                    if isinstance(value, (str, int, float, bool, type(None))) or (
                        isinstance(value, (list, dict)) and not any(
                            hasattr(item, '__dict__') for item in value) if isinstance(value, list) else True
                    ):
                        resource_dict[key] = value
            
            # Ensure basic fields exist
            resource_dict['id'] = getattr(
                resource, 'id', resource.get('id', ''))
            resource_dict['instance_name'] = getattr(
                resource, 'instance_name', resource.get('instance_name', ''))
            
            # Add other important fields
            if hasattr(resource, 'project_id') or (isinstance(resource, dict) and 'project_id' in resource):
                resource_dict['project_id'] = getattr(
                    resource, 'project_id', resource.get('project_id', ''))
            if hasattr(resource, 'type') or (isinstance(resource, dict) and 'type' in resource):
                resource_dict['type'] = getattr(
                    resource, 'type', resource.get('type', ''))
            if hasattr(resource, 'status') or (isinstance(resource, dict) and 'status' in resource):
                resource_dict['status'] = getattr(
                    resource, 'status', resource.get('status', ''))
            if hasattr(resource, 'spec') or (isinstance(resource, dict) and 'spec' in resource):
                resource_dict['spec'] = getattr(
                    resource, 'spec', resource.get('spec', ''))
            if hasattr(resource, 'create_time') or (isinstance(resource, dict) and 'create_time' in resource):
                resource_dict['create_time'] = getattr(
                    resource, 'create_time', resource.get('create_time', ''))
                
            # Add processed resource
            processed_resources.append(resource_dict)
                
        return processed_resources

    def augment(self, resources):
        """Enhance resource information"""
        # Ensure all resources can be properly serialized
        return self.process_resources(resources)


# API Resource Management
@resources.register('rest-api')
class ApiResource(QueryResourceManager):
    """Huawei Cloud API Gateway API Resource Management

    :example:

    .. code-block:: yaml

        policies:
          - name: apig-api-list
            resource: huaweicloud.rest-api
            filters:
              - type: value
                key: status
                value: 1
    """

    class resource_type(TypeInfo):
        service = 'rest-api'
        enum_spec = ('list_apis_v2', 'apis', 'offset')
        id = 'id'
        name = 'name'
        filter_name = 'name'
        filter_type = 'scalar'
        taggable = True
        tag_resource_type = 'apig'

    def get_instance_id(self):
        """Query and get API Gateway instance ID
        
        Get available instance ID by querying apig-instance API, prioritizing running instances
        If no available instance is found, return default instance ID
        """
        session = local_session(self.session_factory)
        
        # If instance_id is specified in the policy, use it directly
        if hasattr(self, 'data') and isinstance(self.data, dict) and 'instance_id' in self.data:
            instance_id = self.data['instance_id']
            log.info(f"Using instance_id from policy configuration: {instance_id}")
            return instance_id
            
        # Query APIG instance list
        try:
            # Use apig-instance service client
            client = session.client('apig-instance')
            instances_request = ListInstancesV2Request()
            response = client.list_instances_v2(instances_request)
            
            if hasattr(response, 'instances') and response.instances:
                # Use the first running instance
                for instance in response.instances:
                    if instance.status == 'Running':
                        instance_id = instance.id
                        log.info(f"Using first running instance ID: {instance_id}")
                        return instance_id
                
                # If no running instance is found, use the first instance
                if response.instances:
                    instance_id = response.instances[0].id
                    log.info(f"No running instance found, using first available instance ID: {instance_id}")
                    return instance_id
        except Exception as e:
            log.error(f"Failed to query APIG instance list: {str(e)}", exc_info=True)
        
        # If still no instance ID is obtained, use default instance ID
        instance_id = session.get_apig_instance_id()
        log.info(f"No available instance found, using default instance ID from configuration: {instance_id}")
        return instance_id

    def _fetch_resources(self, query):
        """Override resource retrieval method to ensure instance_id parameter is included in the request"""
        session = local_session(self.session_factory)
        client = session.client(self.resource_type.service)
        
        # Get instance ID
        instance_id = self.get_instance_id()
        
        # Ensure instance_id is properly set
        if not instance_id:
            log.error("Unable to get valid APIG instance ID, cannot continue querying API list")
            return []
        
        # Create new request object instead of modifying the incoming query
        request = ListApisV2Request()
        request.instance_id = str(instance_id)
        request.limit = 100
        
        # Call client method to process request
        try:
            response = client.list_apis_v2(request)
            resources = []
            
            if hasattr(response, 'apis'):
                for api in response.apis:
                    api_dict = {}
                    # Extract API attributes, only get basic data type attributes for serialization
                    for attr in dir(api):
                        if (not attr.startswith('_') and not callable(getattr(api, attr))
                            and attr not in ['auth_opt', 'vpc_status', 'auth_opt_status']):
                            value = getattr(api, attr)
                            # Ensure values are serializable basic types
                            if isinstance(value, (str, int, float, bool, type(None))) or (
                                isinstance(value, (list, dict)) and not any(
                                    hasattr(item, '__dict__') for item in value) if isinstance(value, list) else True
                            ):
                                api_dict[attr] = value
                    
                    # Add required fields
                    api_dict['id'] = api.id
                    api_dict['instance_id'] = instance_id
                    api_dict['tag_resource_type'] = self.resource_type.tag_resource_type
                    
                    resources.append(api_dict)
            
            return resources
        except exceptions.ClientRequestException as e:
            log.error(f"Failed to query API list: {str(e)}", exc_info=True)
            return []

    def augment(self, resources):
        """Enhance resource information"""
        # Return processed resources directly
        return resources

# API Resource Actions


@ApiResource.action_registry.register('delete')
class DeleteApiAction(HuaweiCloudBaseAction):
    """Delete API action

    :example:

    .. code-block:: yaml

        policies:
          - name: apig-api-delete
            resource: huaweicloud.rest-api
            filters:
              - type: value
                key: name
                value: test-api
            actions:
              - delete
    """
    schema = type_schema('delete')

    def perform_action(self, resource):
        client = self.manager.get_client()
        api_id = resource['id']
        instance_id = resource.get('instance_id')

        if not instance_id:
            # When instance_id is not in the resource, use manager to get it
            if hasattr(self.manager, 'get_instance_id'):
                instance_id = self.manager.get_instance_id()
            else:
                # If there's no get_instance_id method, use default instance ID
                session = local_session(self.manager.session_factory)
                instance_id = session.get_apig_instance_id()
                log.info(f"No available instance found, using default instance ID from configuration: {instance_id}")

        try:
            # Add more debug information
            self.log.debug(f"Deleting API {api_id} (Instance: {instance_id})")
            
            from huaweicloudsdkapig.v2 import DeleteApiV2Request
            
            # Ensure instance_id is string type
            request = DeleteApiV2Request(
                instance_id=str(instance_id),
                api_id=api_id
            )
            
            # Print request object
            self.log.debug(f"Request object: {request}")
            
            client.delete_api_v2(request)
            self.log.info(
                f"Successfully deleted API: {resource.get('name')} (ID: {api_id})")
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to delete API {resource.get('name')} (ID: {api_id}): {e}", exc_info=True)
            raise


@ApiResource.action_registry.register('update')
class UpdateApiAction(HuaweiCloudBaseAction):
    """Update API action

    This action allows updating various properties of an API in API Gateway, 
    including name, request protocol, request method, request URI, authentication type, etc.

    :example:

    .. code-block:: yaml

        policies:
            - name: apig-api-update
            resource: huaweicloud.rest-api
            filters:
                - type: value
                key: id
                value: 499e3bd193ba4db89a49f0ebdef19796
            actions:
                - type: update          
                name: updated-api-name
                api_type: 1
                req_protocol: HTTPS
                req_method: POST
                req_uri: "/test/update"
                auth_type: APP
                backend_type: HTTP
                group_id: "your_group_id"
    """

    schema = type_schema(
        'update',
        name={'type': 'string'},
        # Use api_type instead of type to avoid conflict with operation type
        api_type={'type': 'integer', 'enum': [1, 2]},
        req_protocol={'type': 'string', 'enum': [
            'HTTP', 'HTTPS', 'BOTH', 'GRPCS']},
        req_method={'type': 'string', 'enum': [
            'GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'PATCH', 'OPTIONS', 'ANY']},
        req_uri={'type': 'string'},
        auth_type={'type': 'string', 'enum': [
            'NONE', 'APP', 'IAM', 'AUTHORIZER']},
        backend_type={'type': 'string', 'enum': ['HTTP', 'FUNCTION', 'MOCK']},
        group_id={'type': 'string'},
    )

    def _build_update_body(self, resource):
        """Build API update request body

        Construct API update request body based on policy parameters while preserving necessary fields from the original API

        :param resource: API resource dictionary
        :return: Update request body object
        """
        from huaweicloudsdkapig.v2.model.api_create import ApiCreate

        # Extract necessary fields from the original API to ensure critical information is preserved
        update_info = {}

        # Required fields from original resource
        required_fields = ['name', 'type', 'req_protocol',
                           'req_method', 'req_uri', 'auth_type']
        for field in required_fields:
            if field in resource:
                update_info[field] = resource[field]

        # Update with new values from policy parameters
        field_mappings = {
            'name': 'name',
            'api_type': 'type',  # Map api_type to type
            'req_protocol': 'req_protocol',
            'req_method': 'req_method',
            'req_uri': 'req_uri',
            'auth_type': 'auth_type',
            'backend_type': 'backend_type',
            'group_id': 'group_id'
        }

        for policy_field, api_field in field_mappings.items():
            if policy_field in self.data:
                update_info[api_field] = self.data[policy_field]

        # Handle backend_api information (if exists)
        if 'backend_api' in resource:
            update_info['backend_api'] = resource['backend_api']

        # Handle backend_params information (if exists)
        if 'backend_params' in resource:
            update_info['backend_params'] = resource['backend_params']

        # Construct API create request body
        if update_info:
            return ApiCreate(**update_info)

        return None

    def perform_action(self, resource):
        client = self.manager.get_client()
        api_id = resource['id']
        instance_id = resource.get('instance_id')

        if not instance_id:
            # When instance_id is not in the resource, use manager to get it
            if hasattr(self.manager, 'get_instance_id'):
                instance_id = self.manager.get_instance_id()
            else:
                # If there's no get_instance_id method, use default instance ID
                session = local_session(self.manager.session_factory)
                instance_id = session.get_apig_instance_id()
                log.info(f"No available instance found, using default instance ID from configuration: {instance_id}")

        try:
            # Add more debug information
            self.log.debug(f"Updating API {api_id} (Instance: {instance_id})")
            
            from huaweicloudsdkapig.v2 import UpdateApiV2Request
            
            # First build the parameters to update
            update_body = self._build_update_body(resource)

            if not update_body:
                self.log.warning(
                    f"No update parameters provided, skipping API update {resource.get('name')} (ID: {api_id})")
                return

            # Create update request, ensure instance_id is string type
            request = UpdateApiV2Request(
                instance_id=str(instance_id),
                api_id=api_id,
                body=update_body
            )
            
            # Print request object
            self.log.debug(f"Request object: {request}")

            # Send request
            response = client.update_api_v2(request)
            self.log.info(
                f"Successfully updated API: {resource.get('name')} (ID: {api_id})")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to update API {resource.get('name')} (ID: {api_id}): {e}", exc_info=True)
            raise

# Environment Resource Management


@resources.register('rest-stage')
class StageResource(QueryResourceManager):
    """Huawei Cloud API Gateway Environment Resource Management

    :example:

    .. code-block:: yaml

        policies:
          - name: apig-stage-list
            resource: huaweicloud.rest-stage
            filters:
              - type: value
                key: name
                value: TEST
    """

    class resource_type(TypeInfo):
        service = 'rest-stage'
        enum_spec = ('list_environments_v2', 'envs', 'offset')
        id = 'id'
        name = 'name'
        filter_name = 'name'
        filter_type = 'scalar'
        taggable = True
        tag_resource_type = 'apig'

    def get_instance_id(self):
        """Query and get API Gateway instance ID
        
        Get available instance ID by querying apig-instance API, prioritizing running instances
        If no available instance is found, return default instance ID
        """
        session = local_session(self.session_factory)
        
        # If instance_id is specified in the policy, use it directly
        if hasattr(self, 'data') and isinstance(self.data, dict) and 'instance_id' in self.data:
            instance_id = self.data['instance_id']
            log.info(f"Using instance_id from policy configuration: {instance_id}")
            return instance_id
            
        # Query APIG instance list
        try:
            # Use apig-instance service client
            client = session.client('apig-instance')
            instances_request = ListInstancesV2Request()
            response = client.list_instances_v2(instances_request)
            
            if hasattr(response, 'instances') and response.instances:
                # Use the first running instance
                for instance in response.instances:
                    if instance.status == 'Running':
                        instance_id = instance.id
                        log.info(f"Using first running instance ID: {instance_id}")
                        return instance_id
                
                # If no running instance is found, use the first instance
                if response.instances:
                    instance_id = response.instances[0].id
                    log.info(f"No running instance found, using first available instance ID: {instance_id}")
                    return instance_id
        except Exception as e:
            log.error(f"Failed to query APIG instance list: {str(e)}", exc_info=True)
        
        # If still no instance ID is obtained, use default instance ID
        instance_id = session.get_apig_instance_id()
        log.info(f"No available instance found, using default instance ID from configuration: {instance_id}")
        return instance_id

    def _fetch_resources(self, query):
        """Override resource retrieval method to ensure instance_id parameter is included in the request"""
        session = local_session(self.session_factory)
        client = session.client(self.resource_type.service)
        
        # Get instance ID
        instance_id = self.get_instance_id()
        
        # Ensure instance_id is properly set
        if not instance_id:
            log.error("Unable to get valid APIG instance ID, cannot continue querying environment list")
            return []
        
        # Create new request object instead of modifying the incoming query
        request = ListEnvironmentsV2Request()
        request.instance_id = str(instance_id)
        request.limit = 100
        
        # Call client method to process request
        try:
            response = client.list_environments_v2(request)
            resources = []
            
            if hasattr(response, 'envs'):
                for env in response.envs:
                    env_dict = {}
                    # Extract environment attributes, only get basic data type attributes
                    for attr in dir(env):
                        if not attr.startswith('_') and not callable(getattr(env, attr)):
                            value = getattr(env, attr)
                            # Ensure values are serializable basic types
                            if isinstance(value, (str, int, float, bool, type(None))) or (
                                isinstance(value, (list, dict)) and not any(
                                    hasattr(item, '__dict__') for item in value) if isinstance(value, list) else True
                            ):
                                env_dict[attr] = value
                    
                    # Add required fields
                    env_dict['id'] = env.id
                    env_dict['instance_id'] = instance_id
                    env_dict['tag_resource_type'] = self.resource_type.tag_resource_type
                    
                    resources.append(env_dict)
                
            return resources
        except exceptions.ClientRequestException as e:
            log.error(f"Failed to query environment list: {str(e)}", exc_info=True)
            return []

    def augment(self, resources):
        """Enhance resource information"""
        # Return processed resources directly
        return resources

# Update Environment Resource


@StageResource.action_registry.register('update')
class UpdateStageAction(HuaweiCloudBaseAction):
    """Update environment action

    :example:

    .. code-block:: yaml

        policies:
          - name: apig-stage-update
            resource: huaweicloud.rest-stage
            filters:
              - type: value
                key: name
                value: TEST
            actions:
              - type: update
                name: updated-stage-name
                remark: updated description
    """

    schema = type_schema(
        'update',
        name={'type': 'string'},
        remark={'type': 'string'},
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        env_id = resource['id']
        instance_id = resource.get('instance_id')

        if not instance_id:
            # When instance_id is not in the resource, use manager to get it
            if hasattr(self.manager, 'get_instance_id'):
                instance_id = self.manager.get_instance_id()
            else:
                # If there's no get_instance_id method, use default instance ID
                session = local_session(self.manager.session_factory)
                instance_id = session.get_apig_instance_id()
                log.info(f"No available instance found, using default instance ID from configuration: {instance_id}")

        try:
            # Add more debug information
            self.log.debug(f"Updating environment {env_id} (Instance: {instance_id})")
            
            # Prepare update parameters
            update_info = {}
            
            if 'name' in self.data:
                update_info['name'] = self.data['name']
            if 'description' in self.data:
                update_info['remark'] = self.data['description']
            
            # Add other possible parameters
            if 'enable_metrics' in self.data:
                update_info['enable_metrics'] = self.data['enable_metrics']
            if 'is_waf_enabled' in self.data:
                update_info['is_waf_enabled'] = self.data['is_waf_enabled']
            if 'is_client_certificate_required' in self.data:
                update_info['is_client_certificate_required'] = self.data['is_client_certificate_required']

            if not update_info:
                self.log.warning(
                    f"No update parameters provided, skipping environment update {resource.get('name')} (ID: {env_id})")
                return

            # Create update request, ensure instance_id is string type
            request = UpdateEnvironmentV2Request(
                instance_id=str(instance_id),
                env_id=env_id,
                body=update_info
            )
            
            # Print request object
            self.log.debug(f"Request object: {request}")

            # Send request
            response = client.update_environment_v2(request)
            self.log.info(
                f"Successfully updated environment: {resource.get('name')} (ID: {env_id})")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to update environment {resource.get('name')} (ID: {env_id}): {e}", exc_info=True)
            raise


@StageResource.action_registry.register('delete')
class DeleteStageAction(HuaweiCloudBaseAction):
    """Delete environment action

    :example:

    .. code-block:: yaml

        policies:
          - name: apig-stage-delete
            resource: huaweicloud.rest-stage
            filters:
              - type: value
                key: name
                value: TEST
            actions:
              - delete
    """

    schema = type_schema('delete')

    def perform_action(self, resource):
        client = self.manager.get_client()
        env_id = resource['id']
        instance_id = resource.get('instance_id')

        if not instance_id:
            # When instance_id is not in the resource, use manager to get it
            if hasattr(self.manager, 'get_instance_id'):
                instance_id = self.manager.get_instance_id()
            else:
                # If there's no get_instance_id method, use default instance ID
                session = local_session(self.manager.session_factory)
                instance_id = session.get_apig_instance_id()
                log.info(f"No available instance found, using default instance ID from configuration: {instance_id}")

        try:
            # Add more debug information
            self.log.debug(f"Deleting environment {env_id} (Instance: {instance_id})")
            
            # Ensure instance_id is string type
            request = DeleteEnvironmentV2Request(
                instance_id=str(instance_id),
                env_id=env_id
            )
            
            # Print request object
            self.log.debug(f"Request object: {request}")
            
            client.delete_environment_v2(request)
            self.log.info(
                f"Successfully deleted environment: {resource.get('name')} (ID: {env_id})")
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to delete environment {resource.get('name')} (ID: {env_id}): {e}", exc_info=True)
            raise

# API Group Resource Management


@resources.register('api-groups')
class ApiGroupResource(QueryResourceManager):
    """Huawei Cloud API Gateway Group Resource Management

    :example:

    .. code-block:: yaml

        policies:
          - name: apig-group-list
            resource: huaweicloud.api-groups
            filters:
              - type: value
                key: status
                value: 1
    """

    class resource_type(TypeInfo):
        service = 'api-groups'
        enum_spec = ('list_api_groups_v2', 'groups', 'offset')
        id = 'id'
        name = 'name'
        filter_name = 'name'
        filter_type = 'scalar'
        taggable = True
        tag_resource_type = 'apig'

    def get_instance_id(self):
        """Query and get API Gateway instance ID
        
        Get available instance ID by querying apig-instance API, prioritizing running instances
        If no available instance is found, return default instance ID
        """
        session = local_session(self.session_factory)
        
        # If instance_id is specified in the policy, use it directly
        if hasattr(self, 'data') and isinstance(self.data, dict) and 'instance_id' in self.data:
            instance_id = self.data['instance_id']
            log.info(f"Using instance_id from policy configuration: {instance_id}")
            return instance_id
            
        # Query APIG instance list
        try:
            # Use apig-instance service client
            client = session.client('apig-instance')
            instances_request = ListInstancesV2Request()
            response = client.list_instances_v2(instances_request)
            
            if hasattr(response, 'instances') and response.instances:
                # Use the first running instance
                for instance in response.instances:
                    if instance.status == 'Running':
                        instance_id = instance.id
                        log.info(f"Using first running instance ID: {instance_id}")
                        return instance_id
                
                # If no running instance is found, use the first instance
                if response.instances:
                    instance_id = response.instances[0].id
                    log.info(f"No running instance found, using first available instance ID: {instance_id}")
                    return instance_id
        except Exception as e:
            log.error(f"Failed to query APIG instance list: {str(e)}", exc_info=True)
        
        # If still no instance ID is obtained, use default instance ID
        instance_id = session.get_apig_instance_id()
        log.info(f"No available instance found, using default instance ID from configuration: {instance_id}")
        return instance_id

    def _fetch_resources(self, query):
        """Override resource retrieval method to ensure instance_id parameter is included in the request"""
        session = local_session(self.session_factory)
        client = session.client(self.resource_type.service)
        
        # Get instance ID
        instance_id = self.get_instance_id()
        
        # Ensure instance_id is properly set
        if not instance_id:
            log.error("Unable to get valid APIG instance ID, cannot continue querying API group list")
            return []
        
        # Create new request object instead of modifying the incoming query
        request = ListApiGroupsV2Request()
        request.instance_id = str(instance_id)
        request.limit = 100
        
        # Call client method to process request
        try:
            response = client.list_api_groups_v2(request)
            resources = []
            
            if hasattr(response, 'groups'):
                for group in response.groups:
                    group_dict = {}
                    
                    # Special handling for url_domains attribute, extract as separate list
                    url_domains = []
                    if hasattr(group, 'url_domains') and group.url_domains is not None:
                        for domain in group.url_domains:
                            domain_dict = {}
                            # Process each domain object's various attributes
                            if hasattr(domain, 'id'):
                                domain_dict['id'] = domain.id
                            if hasattr(domain, 'domain'):
                                domain_dict['domain'] = domain.domain
                            if hasattr(domain, 'cname_status'):
                                domain_dict['cname_status'] = domain.cname_status
                            if hasattr(domain, 'ssl_id'):
                                domain_dict['ssl_id'] = domain.ssl_id
                            if hasattr(domain, 'ssl_name'):
                                domain_dict['ssl_name'] = domain.ssl_name
                            if hasattr(domain, 'min_ssl_version'):
                                domain_dict['min_ssl_version'] = domain.min_ssl_version
                                
                            # Add other possible attributes
                            for attr_name in ['verified_client_certificate_enabled', 
                                             'is_has_trusted_root_ca', 
                                             'ingress_http_port', 
                                             'ingress_https_port']:
                                if hasattr(domain, attr_name):
                                    domain_dict[attr_name] = getattr(
                                        domain, attr_name)
                                    
                            # Process possible ssl_infos nested list
                            if hasattr(domain, 'ssl_infos') and domain.ssl_infos is not None:
                                ssl_infos_list = []
                                for ssl_info in domain.ssl_infos:
                                    if hasattr(ssl_info, '__dict__'):
                                        ssl_info_dict = {}
                                        for ssl_attr in dir(ssl_info):
                                            if not ssl_attr.startswith('_') and not callable(getattr(ssl_info, ssl_attr)):
                                                ssl_info_dict[ssl_attr] = getattr(
                                                    ssl_info, ssl_attr)
                                        ssl_infos_list.append(ssl_info_dict)
                                domain_dict['ssl_infos'] = ssl_infos_list
                            else:
                                domain_dict['ssl_infos'] = []
                                
                            url_domains.append(domain_dict)
                    
                    # Extract other API group attributes
                    for attr in dir(group):
                        if (not attr.startswith('_') and not callable(getattr(group, attr)) 
                            and attr != 'url_domains'):  # Skip url_domains as we've already processed it
                            value = getattr(group, attr)
                            # Ensure values are serializable basic types
                            if isinstance(value, (str, int, float, bool, type(None))) or (
                                isinstance(value, (list, dict)) and not any(
                                    hasattr(item, '__dict__') for item in value) if isinstance(value, list) else True
                            ):
                                group_dict[attr] = value
                    
                    # Add processed url_domains
                    group_dict['url_domains'] = url_domains
                    
                    # Add required fields
                    group_dict['id'] = getattr(group, 'id', '')
                    group_dict['instance_id'] = instance_id
                    group_dict['tag_resource_type'] = self.resource_type.tag_resource_type
                    
                    resources.append(group_dict)
            
            return resources
        except exceptions.ClientRequestException as e:
            log.error(f"Failed to query API group list: {str(e)}", exc_info=True)
            return []

    def augment(self, resources):
        """Enhance resource information"""
        # Return processed resources directly
        return resources

# Update Security


@ApiGroupResource.action_registry.register('update-security')
class UpdateDomainSecurityAction(HuaweiCloudBaseAction):
    """Update domain security policy action

    :example:

    .. code-block:: yaml

        policies:
          - name: apig-domain-update-security
            resource: huaweicloud.api-groups
            filters:
              - type: value
                key: id
                value: c77f5e81d9cb4424bf704ef2b0ac7600
            actions:
              - type: update-security
                min_ssl_version: TLSv1.2
    """

    schema = type_schema(
        'update-security',
        min_ssl_version={'type': 'string', 'enum': ['TLSv1.1', 'TLSv1.2']},
        is_http_redirect_to_https={'type': 'boolean'},
        verified_client_certificate_enabled={'type': 'boolean'},
        ingress_http_port={'type': 'integer', 'minimum': -1, 'maximum': 49151},
        ingress_https_port={'type': 'integer', 'minimum': -1, 'maximum': 49151}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        group_id = resource['id']
        instance_id = resource.get('instance_id')
        
        # Get domain_id from policy data
        domain_id = self.data.get('domain_id')
        
        # If domain_id is not specified in the policy, try to get it from the resource's url_domains list
        if not domain_id and 'url_domains' in resource and resource['url_domains']:
            # Check if url_domains is a list and not empty
            if isinstance(resource['url_domains'], list) and len(resource['url_domains']) > 0:
                # Try to get the ID of the first domain
                domain_item = resource['url_domains'][0]
                if isinstance(domain_item, dict) and 'id' in domain_item:
                    domain_id = domain_item['id']
                    self.log.info(f"Using first domain ID from resource: {domain_id}")

        if not domain_id:
            self.log.error(
                f"No domain_id specified, cannot perform domain security policy update, API group ID: {group_id}")
            return

        if not instance_id:
            # When instance_id is not in the resource, use manager to get it
            if hasattr(self.manager, 'get_instance_id'):
                instance_id = self.manager.get_instance_id()
            else:
                # If there's no get_instance_id method, use default instance ID
                session = local_session(self.manager.session_factory)
                instance_id = session.get_apig_instance_id()
                log.info(f"No available instance found, using default instance ID from configuration: {instance_id}")

        try:
            # Add more debug information
            self.log.debug(
                f"Updating domain security policy Domain ID: {domain_id}, API group ID: {group_id} (Instance: {instance_id})")
            
            # Prepare update parameters
            update_info = {}
            
            if 'min_ssl_version' in self.data:
                update_info['min_ssl_version'] = self.data['min_ssl_version']
            
            if 'is_http_redirect_to_https' in self.data:
                update_info['is_http_redirect_to_https'] = self.data['is_http_redirect_to_https']
                
            if 'verified_client_certificate_enabled' in self.data:
                update_info['verified_client_certificate_enabled'] = self.data['verified_client_certificate_enabled']
                
            if 'ingress_http_port' in self.data:
                update_info['ingress_http_port'] = self.data['ingress_http_port']
                
            if 'ingress_https_port' in self.data:
                update_info['ingress_https_port'] = self.data['ingress_https_port']
            
            if 'ssl_id' in self.data:
                update_info['ssl_id'] = self.data['ssl_id']
                update_info['ssl_name'] = 'Certificate bound to this domain'
                
            if not update_info:
                self.log.warning(
                    f"No update parameters provided, skipping domain security policy update, Domain ID: {domain_id}, API group ID: {group_id}")
                return

            # Create update request, ensure instance_id is string type
            request = UpdateDomainV2Request(
                instance_id=str(instance_id),
                domain_id=domain_id,
                body=update_info
            )
            
            # Print request object
            self.log.debug(f"Request object: {request}")

            # Send request
            response = client.update_domain_v2(request)
            self.log.info(
                f"Successfully updated domain security policy: API group {resource.get('name')} (ID: {group_id}), Domain ID: {domain_id}")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to update domain security policy: API group {resource.get('name')} (ID: {group_id}), Domain ID: {domain_id}: {e}", exc_info=True)
            raise
