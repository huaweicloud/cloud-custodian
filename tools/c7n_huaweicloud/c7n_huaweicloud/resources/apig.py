# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkapig.v2 import (
    # API interface related
    DeleteApiV2Request,
    UpdateApiV2Request,
    ListApisV2Request,

    # Environment related
    UpdateEnvironmentV2Request,
    DeleteEnvironmentV2Request,
    ListEnvironmentsV2Request,

    # Domain related
    UpdateDomainV2Request,

    # Group related
    ListApiGroupsV2Request,

    # Instance related
    ListInstancesV2Request,
)

from c7n.utils import type_schema, local_session
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction

log = logging.getLogger('custodian.huaweicloud.apig')

# API Resource Management


@resources.register('apig-api')
class ApiResource(QueryResourceManager):
    """
    Huawei Cloud API Gateway API Resource Management
    """

    class resource_type(TypeInfo):
        service = 'apig-api'
        enum_spec = ('list_apis_v2', 'apis', 'offset')
        id = 'id'
        name = 'name'
        filter_name = 'name'
        filter_type = 'scalar'
        taggable = False

    def get_instance_id(self):
        """
        Query and get API Gateway instance ID
        """
        session = local_session(self.session_factory)

        # If instance_id is specified in the policy, use it directly
        if hasattr(self, 'data') and isinstance(self.data, dict) and 'instance_id' in self.data:
            instance_id = self.data['instance_id']
            log.info(
                f"Using instance_id from policy configuration: {instance_id}")
            return [instance_id]

        # Query APIG instance list
        try:
            # Use apig-instance service client
            client = session.client('apig-instance')
            instances_request = ListInstancesV2Request(limit=500)
            response = client.list_instances_v2(instances_request)

            if hasattr(response, 'instances') and response.instances:
                instance_ids = []
                for instance in response.instances:
                    instance_ids.append(instance.id)
                return instance_ids
        except Exception as e:
            log.error(
                f"Failed to query APIG instance list: {str(e)}", exc_info=True)

        return []

    def get_resources(self, query):
        return self.get_api_resources(query)

    def _fetch_resources(self, query):
        return self.get_api_resources(query)

    def get_api_resources(self, query):
        session = local_session(self.session_factory)
        client = session.client(self.resource_type.service)

        # Get instance ID
        instance_ids = self.get_instance_id()

        # Ensure instance_id is properly set
        if not instance_ids:
            log.error(
                "Unable to get valid APIG instance ID, "
                "cannot continue querying API list")
            return []

        resources = []
        for instance_id in instance_ids:
            offset, limit = 0, 500
            while True:
                # Create new request object instead of modifying the incoming query
                request = ListApisV2Request(offset=offset, limit=limit)
                request.instance_id = instance_id

                # Call client method to process request
                try:
                    response = client.list_apis_v2(request)
                    resource = eval(
                        str(response.apis)
                        .replace("null", "None")
                        .replace("false", "False")
                        .replace("true", "True")
                    )
                    for item in resource:
                        item["instance_id"] = instance_id
                    resources = resources + resource
                except exceptions.ClientRequestException as e:
                    log.error(
                        f"Failed to query API list: {str(e)}", exc_info=True)
                    break

                offset += limit
                if not response.total or offset >= response.total:
                    break

        return resources


# API Resource Actions
@ApiResource.action_registry.register('delete')
class DeleteApiAction(HuaweiCloudBaseAction):
    """Delete API action

    :example:
    Define a policy to delete API Gateway APIs with name 'test-api':

    .. code-block:: yaml

        policies:
          - name: apig-api-delete
            resource: huaweicloud.apig-api
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
            self.log.error(
                f"No available instance found, using default instance ID from configuration: "
                f"{instance_id}")
            return

        try:
            # Add more debug information
            self.log.debug(f"Deleting API {api_id} (Instance: {instance_id})")

            # Ensure instance_id is string type
            request = DeleteApiV2Request(
                instance_id=instance_id,
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
    Define a policy to update an API Gateway API with comprehensive configuration options:

    .. code-block:: yaml

        policies:
            - name: apig-api-update-full-example
              resource: huaweicloud.apig-api
              filters:
                - type: value
                  key: id
                  value: 499e3bd193ba4db89a49f0ebdef19796
              actions:
                - type: update
                  # Basic API properties
                  name: updated-api-name
                  api_type: 1  # 1 for public API, 2 for private API
                  version: "v1.0.1"
                  req_protocol: HTTPS
                  req_method: POST
                  req_uri: "/v1/test/update"
                  auth_type: APP  # Options: NONE, APP, IAM, AUTHORIZER
                  group_id: "c77f5e81d9cb4424bf704ef2b0ac7600"
                  match_mode: "NORMAL"  # NORMAL or SWA
                  cors: false
                  remark: "Updated API with complete parameters"

                  # Response examples
                  result_normal_sample: '{"result": "success", "data": {"id": 1}}'

                  # Tracing configuration
                  trace_enabled: true
                  sampling_strategy: "RATE"
                  sampling_param: "10"

                  # Tags
                  tags:
                    - "production"
                    - "api-gateway"

                  # Backend API configuration
                  backend_type: "HTTP"  # HTTP, FUNCTION, or MOCK
                  backend_api:
                    req_protocol: "HTTPS"
                    req_method: "POST"
                    req_uri: "/backend/service"
                    timeout: 5000
                    retry_count: "3"
                    url_domain: "api.example.com"
                    host: "api.backend-service.com"

                  # Backend parameters
                  backend_params:
                    - name: "X-User-Id"
                      value: "$context.authorizer.userId"
                      location: "HEADER"
                      origin: "SYSTEM"
                      remark: "User ID from the authorizer"
                    - name: "api-version"
                      value: "v1"
                      location: "HEADER"
                      origin: "CONSTANT"
                      remark: "API version as a constant"

                  # Authentication options
                  auth_opt:
                    app_code_auth_type: "HEADER"
                    app_code_headers:
                      - "X-Api-Auth"

                  # SSL verification
                  disables_ssl_verification: false

                  # Mock response (when backend_type is MOCK)
                  mock_info:
                    status_code: 200
                    example: '{"data": "mock response"}'
                    contentType: "application/json"
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
        version={'type': 'string'},
        cors={'type': 'boolean'},
        remark={'type': 'string'},
        authorizer_id={'type': 'string'},
        match_mode={'type': 'string', 'enum': ['NORMAL', 'SWA']},
        result_normal_sample={'type': 'string'},
        result_failure_sample={'type': 'string'},
        trace_enabled={'type': 'boolean'},
        sampling_strategy={'type': 'string'},
        sampling_param={'type': 'string'},
        tags={'type': 'array', 'items': {'type': 'string'}},
        backend_api={'type': 'object', 'properties': {
            'req_protocol': {'type': 'string', 'enum': ['HTTP', 'HTTPS']},
            'req_method': {'type': 'string', 'enum': [
                'GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'PATCH', 'OPTIONS', 'ANY']},
            'req_uri': {'type': 'string'},
            'timeout': {'type': 'integer'},
            'retry_count': {'type': 'string'},
            'url_domain': {'type': 'string'},
            'host': {'type': 'string'},
            'vpc_channel_info': {'type': 'object'}
        }},
        backend_params={'type': 'array', 'items': {'type': 'object', 'properties': {
            'name': {'type': 'string'},
            'value': {'type': 'string'},
            'location': {'type': 'string', 'enum': [
                'PATH', 'QUERY', 'HEADER']},
            'origin': {'type': 'string', 'enum': [
                'REQUEST', 'CONSTANT', 'SYSTEM']},
            'remark': {'type': 'string'}
        }}},
        auth_opt={'type': 'object', 'properties': {
            'app_code_auth_type': {'type': 'string', 'enum': [
                'DISABLE', 'HEADER', 'APP_CODE', 'HEADER_OR_APP_CODE']},
            'app_code_headers': {'type': 'array', 'items': {'type': 'string'}}
        }},
        disables_ssl_verification={'type': 'boolean'},
        mock_info={'type': 'object', 'properties': {
            'status_code': {'type': 'integer'},
            'example': {'type': 'string'},
            'contentType': {'type': 'string'}
        }}
    )

    def _build_update_body(self, resource):
        """Build API update request body

        Construct API update request body based on policy parameters while preserving
        necessary fields from the original API

        :param resource: API resource dictionary
        :return: Update request body object
        """
        from huaweicloudsdkapig.v2.model.api_create import ApiCreate

        # Extract necessary fields from the original API to ensure critical information is preserved
        update_info = {}

        for field in self.data:
            if field == "api_type":
                update_info["type"] = self.data[field]
            else:
                update_info[field] = self.data[field]

        # Construct API create request body
        return ApiCreate(**update_info)

    def perform_action(self, resource):
        client = self.manager.get_client()
        api_id = resource['id']
        instance_id = resource.get('instance_id')

        if not instance_id:
            self.log.error(
                f"No available instance found, using default instance ID from configuration: "
                f"{instance_id}")
            return

        try:
            # Add more debug information
            self.log.debug(f"Updating API {api_id} (Instance: {instance_id})")

            # First build the parameters to update
            update_body = self._build_update_body(resource)

            if not update_body:
                self.log.error(
                    f"No update parameters provided, skipping API update "
                    f"{resource.get('name')} (ID: {api_id})")
                return

            # Create update request, ensure instance_id is string type
            request = UpdateApiV2Request(
                instance_id=instance_id,
                api_id=api_id,
                body=update_body
            )

            # Print request object
            self.log.debug(f"Request object: {request}")

            # Send request
            response = client.update_api_v2(request)
            api_name = resource.get('name')
            self.log.info(
                f"Successfully updated API: {api_name} (ID: {api_id})")
            return response
        except exceptions.ClientRequestException as e:
            api_name = resource.get('name')
            self.log.error(
                f"Failed to update API {api_name} (ID: {api_id}): {e}",
                exc_info=True)
            raise

# Environment Resource Management


@resources.register('apig-stage')
class StageResource(QueryResourceManager):
    """
    Huawei Cloud API Gateway Environment Resource Management
    """

    class resource_type(TypeInfo):
        service = 'apig-stage'
        enum_spec = ('list_environments_v2', 'envs', 'offset')
        id = 'id'
        name = 'name'
        filter_name = 'name'
        filter_type = 'scalar'
        taggable = False

    def get_instance_id(self):
        """
        Query and get API Gateway instance ID
        """
        session = local_session(self.session_factory)

        # If instance_id is specified in the policy, use it directly
        if hasattr(self, 'data') and isinstance(self.data, dict) and 'instance_id' in self.data:
            instance_id = self.data['instance_id']
            log.info(
                f"Using instance_id from policy configuration: {instance_id}")
            return [instance_id]

        # Query APIG instance list
        try:
            # Use apig-instance service client
            client = session.client('apig-instance')
            instances_request = ListInstancesV2Request(limit=500)
            response = client.list_instances_v2(instances_request)

            if hasattr(response, 'instances') and response.instances:
                instance_ids = []
                for instance in response.instances:
                    instance_ids.append(instance.id)
                return instance_ids
        except Exception as e:
            log.error(
                f"Failed to query APIG instance list: {str(e)}", exc_info=True)

        return []

    def get_resources(self, query):
        return self.get_stage_resources(query)

    def _fetch_resources(self, query):
        return self.get_stage_resources(query)

    def get_stage_resources(self, query):
        """Override resource retrieval method to ensure
           instance_id parameter is included in the request"""
        session = local_session(self.session_factory)
        client = session.client(self.resource_type.service)

        # Get instance ID
        instance_ids = self.get_instance_id()

        # Ensure instance_id is properly set
        if not instance_ids:
            log.error(
                "Unable to get valid APIG instance ID, cannot continue querying API list")
            return []

        resources = []
        for instance_id in instance_ids:
            # Create new request object instead of modifying the incoming query
            request = ListEnvironmentsV2Request(limit=500)
            request.instance_id = instance_id

            # Call client method to process request
            try:
                response = client.list_environments_v2(request)
                resource = eval(
                    str(response.envs)
                    .replace("null", "None")
                    .replace("false", "False")
                    .replace("true", "True")
                )
                for item in resource:
                    item["instance_id"] = instance_id
                resources = resources + resource

                return resources
            except exceptions.ClientRequestException as e:
                log.error(
                    f"Failed to query environment list: {str(e)}", exc_info=True)
                return []
        return resources


# Update Environment Resource


@StageResource.action_registry.register('update')
class UpdateStageAction(HuaweiCloudBaseAction):
    """Update environment action

    :example:
    Define a policy to update an API Gateway environment's name and description:

    .. code-block:: yaml

        policies:
          - name: apig-stage-update
            resource: huaweicloud.apig-stage
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
            self.log.error(
                f"No available instance found, using default instance ID from configuration: "
                f"{instance_id}")
            return

        try:
            # Add more debug information
            self.log.debug(
                f"Updating environment {env_id} (Instance: {instance_id})")

            # Prepare update parameters
            update_info = {}

            if 'name' in self.data:
                update_info['name'] = self.data['name']
            if 'remark' in self.data:
                update_info['remark'] = self.data['remark']

            # Create update request, ensure instance_id is string type
            request = UpdateEnvironmentV2Request(
                instance_id=instance_id,
                env_id=env_id,
                body=update_info
            )

            # Print request object
            self.log.debug(f"Request object: {request}")

            # Send request
            response = client.update_environment_v2(request)
            env_name = resource.get('name')
            self.log.info(
                f"Successfully updated environment: {env_name} (ID: {env_id})")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to update environment {resource.get('name')} (ID: {env_id}): {e}",
                exc_info=True)
            raise


@StageResource.action_registry.register('delete')
class DeleteStageAction(HuaweiCloudBaseAction):
    """Delete environment action

    :example:
    Define a policy to delete API Gateway environments with name 'TEST':

    .. code-block:: yaml

        policies:
          - name: apig-stage-delete
            resource: huaweicloud.apig-stage
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
            self.log.error(
                f"No available instance found, using default instance ID from configuration: "
                f"{instance_id}")
            return

        try:
            # Add more debug information
            self.log.debug(
                f"Deleting environment {env_id} (Instance: {instance_id})")

            # Ensure instance_id is string type
            request = DeleteEnvironmentV2Request(
                instance_id=instance_id,
                env_id=env_id
            )

            # Print request object
            self.log.debug(f"Request object: {request}")

            client.delete_environment_v2(request)
            env_name = resource.get('name')
            self.log.info(
                f"Successfully deleted environment: {env_name} (ID: {env_id})")
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to delete environment {resource.get('name')} (ID: {env_id}): {e}",
                exc_info=True)
            raise

# API Group Resource Management


@resources.register('apig-api-groups')
class ApiGroupResource(QueryResourceManager):
    """
    Huawei Cloud API Gateway Group Resource Management
    """

    class resource_type(TypeInfo):
        service = 'apig-api-groups'
        enum_spec = ('list_api_groups_v2', 'groups', 'offset')
        id = 'id'
        name = 'name'
        filter_name = 'name'
        filter_type = 'scalar'
        taggable = False

    def get_instance_id(self):
        """
        Query and get API Gateway instance ID
        """
        session = local_session(self.session_factory)

        # If instance_id is specified in the policy, use it directly
        if hasattr(self, 'data') and isinstance(self.data, dict) and 'instance_id' in self.data:
            instance_id = self.data['instance_id']
            log.info(
                f"Using instance_id from policy configuration: {instance_id}")
            return [instance_id]

        # Query APIG instance list
        try:
            # Use apig-instance service client
            client = session.client('apig-instance')
            instances_request = ListInstancesV2Request(limit=500)
            response = client.list_instances_v2(instances_request)

            if hasattr(response, 'instances') and response.instances:
                instance_ids = []
                for instance in response.instances:
                    instance_ids.append(instance.id)
                return instance_ids
        except Exception as e:
            log.error(
                f"Failed to query APIG instance list: {str(e)}", exc_info=True)

        return []

    def get_resources(self, query):
        return self.get_api_groups_resources(query)

    def _fetch_resources(self, query):
        return self.get_api_groups_resources(query)

    def get_api_groups_resources(self, query):
        """Override resource retrieval method to ensure
           instance_id parameter is included in the request"""
        session = local_session(self.session_factory)
        client = session.client(self.resource_type.service)

        # Get instance ID
        instance_ids = self.get_instance_id()

        # Ensure instance_id is properly set
        if not instance_ids:
            log.error(
                "Unable to get valid APIG instance ID, "
                "cannot continue querying API group list")
            return []

        resources = []
        for instance_id in instance_ids:
            offset, limit = 0, 500
            while True:
                # Create new request object instead of modifying the incoming query
                request = ListApiGroupsV2Request(offset=offset, limit=limit)
                request.instance_id = instance_id

                # Call client method to process request
                try:
                    response = client.list_api_groups_v2(request)
                    resource = eval(
                        str(response.groups)
                        .replace("null", "None")
                        .replace("false", "False")
                        .replace("true", "True")
                    )
                    for item in resource:
                        item["instance_id"] = instance_id
                    resources = resources + resource
                except exceptions.ClientRequestException as e:
                    log.error(
                        f"Failed to query API Group list: {str(e)}", exc_info=True)
                    break

                offset += limit
                if not response.total or offset >= response.total:
                    break

        return resources


# Update Security


@ApiGroupResource.action_registry.register('update-domain')
class UpdateDomainSecurityAction(HuaweiCloudBaseAction):
    """Update domain security policy action

    :example:
    Define a policy to update security settings for an API Gateway domain:

    .. code-block:: yaml

        policies:
          - name: apig-domain-update-domain
            resource: huaweicloud.apig-api-groups
            filters:
              - type: value
                key: id
                value: c77f5e81d9cb4424bf704ef2b0ac7600
            actions:
              - type: update-domain
                domain_id: test_domain_id
                min_ssl_version: TLSv1.2
    """

    schema = type_schema(
        'update-domain',
        min_ssl_version={'type': 'string', 'enum': ['TLSv1.1', 'TLSv1.2']},
        is_http_redirect_to_https={'type': 'boolean'},
        verified_client_certificate_enabled={'type': 'boolean'},
        ingress_http_port={'type': 'integer', 'minimum': -1, 'maximum': 49151},
        ingress_https_port={'type': 'integer',
                            'minimum': -1, 'maximum': 49151},
        domain_id={'type': 'string'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        group_id = resource['id']
        instance_id = resource.get('instance_id')

        # Get domain_id from policy data
        domain_id = self.data.get('domain_id')

        if not domain_id:
            self.log.error(
                f"No domain_id specified, cannot perform domain security policy update, "
                f"API group ID: {group_id}")
            return

        try:
            # Add more debug information
            self.log.debug(
                f"Updating domain security policy Domain ID: {domain_id}, "
                f"API group ID: {group_id} (Instance: {instance_id})")

            from huaweicloudsdkapig.v2.model.url_domain_modify import UrlDomainModify

            update_info = {}

            # Required fields from original resource
            for field in self.data:
                if field != "domain_id" and field != "type":
                    update_info[field] = self.data[field]

            # Create update request, ensure instance_id is string type
            request = UpdateDomainV2Request(
                instance_id=instance_id,
                domain_id=domain_id,
                body=UrlDomainModify(**update_info)
            )

            # Print request object
            self.log.debug(f"Request object: {request}")

            # Send request
            response = client.update_domain_v2(request)
            group_name = resource.get('name')
            self.log.info(
                f"Successfully updated domain security policy: API group {group_name} "
                f"(ID: {group_id}), Domain ID: {domain_id}")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to update domain security policy: API group {resource.get('name')} "
                f"(ID: {group_id}), Domain ID: {domain_id}: {e}",
                exc_info=True)
            raise
