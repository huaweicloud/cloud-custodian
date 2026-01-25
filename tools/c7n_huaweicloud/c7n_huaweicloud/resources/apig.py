# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkapig.v2 import (
    # Instance related
    ListInstancesV2Request,
    CreateFeatureV2Request,
    FeatureToggle,

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
    UpdateSlDomainSettingV2Request,
    SlDomainAccessSetting,

    # Group related
    ListApiGroupsV2Request,

    # VPC Endpoint related
    ListEndpointConnectionsRequest,
    AcceptOrRejectEndpointConnectionsRequest,
    ConnectionActionReq,

    # Plugin related
    ListPluginsRequest,
    CreatePluginRequest,
    PluginCreate,
    AttachApiToPluginRequest,
    PluginOperApiInfo,

    # Signature Key related
    ListSignatureKeysV2Request,
    CreateSignatureKeyV2Request,
    AssociateSignatureKeyV2Request,
    BaseSignature,
    SignApiBinding,

    # Custom Authorizer related
    CreateCustomAuthorizerV2Request,
    AuthorizerCreate,
    Identity,
)

from c7n.utils import type_schema, local_session
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.utils.json_parse import safe_json_parse

log = logging.getLogger('custodian.huaweicloud.apig')


# Instance Resource Management
@resources.register('apig-instance')
class ApigInstanceResource(QueryResourceManager):
    """
    Huawei Cloud API Gateway Instance Resource Management
    """

    class resource_type(TypeInfo):
        service = 'apig-instance'
        enum_spec = ('list_instances_v2', 'instances', 'offset')
        id = 'id'
        name = 'instance_name'
        filter_name = 'instance_name'
        filter_type = 'scalar'
        taggable = False

    def get_resources(self, query):
        return self.get_instance_resources(query)

    def _fetch_resources(self, query):
        return self.get_instance_resources(query)

    def get_instance_resources(self, query):
        """Override resource retrieval method to query APIG instances"""
        session = local_session(self.session_factory)
        client = session.client(self.resource_type.service)

        # Create new request object with pagination parameters
        request = ListInstancesV2Request(limit=500)
        # Call client method to process request
        try:
            response = client.list_instances_v2(request)
            resource = safe_json_parse(response.instances)
            return resource
        except Exception as e:
            log.error(
                "[filters]-{get-instance-resources} The resource:[apig-instance] "
                "query instance list is failed, cause: %s", str(e), exc_info=True)
            return []


# Instance Feature Actions
@ApigInstanceResource.action_registry.register('create-feature')
class CreateFeatureAction(HuaweiCloudBaseAction):
    """Create feature configuration action for API Gateway instances

    This action configures features for API Gateway instances, allowing users to enable
    or disable specific capabilities as needed.

    :example:
    Define a policy to configure a feature for an API Gateway instance:

    .. code-block:: yaml

        policies:
          - name: apig-instance-create-feature
            resource: huaweicloud.apig-instance
            filters:
              - type: value
                key: id
                value: 499e3bd193ba4db89a49f0ebdef19796
            actions:
              - type: create-feature
                name: ratelimit
                enable: true
                config: "{\"api_limits\":8000}"
    """

    schema = type_schema(
        'create-feature',
        name={'type': 'string'},
        enable={'type': 'boolean'},
        config={'type': 'string'},
        required=['name', 'enable']
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']

        if not instance_id:
            instance_name = resource.get('instance_name', 'unknown')
            log.error(
                "[actions]-{create-feature} The resource:[apig-instance] "
                "with id:[%s] name:[%s] create feature is failed, "
                "cause: No available instance found", instance_id, instance_name)
            return

        try:
            # Build feature toggle object from policy data
            feature_toggle = FeatureToggle(
                name=self.data['name'],
                enable=self.data['enable']
            )

            # Add config parameter if provided
            if 'config' in self.data:
                feature_toggle.config = self.data['config']

            # Create request
            request = CreateFeatureV2Request(
                instance_id=instance_id,
                body=feature_toggle
            )

            # Send request
            response = client.create_feature_v2(request)

            feature_name = self.data['name']
            instance_name = resource.get('instance_name')
            log.info(
                "[actions]-{create-feature} The resource:[apig-instance] "
                "with id:[%s] name:[%s] create feature '%s' is success.",
                instance_id, instance_name, feature_name)

            return response
        except exceptions.ClientRequestException as e:
            feature_name = self.data.get('name', 'unknown')
            instance_name = resource.get('instance_name')
            log.error(
                "[actions]-{create-feature} The resource:[apig-instance] "
                "with id:[%s] name:[%s] create feature '%s' is failed, cause: "
                "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                instance_id, instance_name, feature_name,
                e.status_code, e.request_id, e.error_code, e.error_msg)
            raise


@ApigInstanceResource.action_registry.register('create-plugin')
class CreatePluginAction(HuaweiCloudBaseAction):
    """Create plugin action for API Gateway instances

    This action creates a plugin for API Gateway instances to enhance API functionality
    by adding various capabilities such as rate limiting, CORS, authentication, etc.

    :example:
    Define a policy to create a rate limiting plugin for an API Gateway instance:

    .. code-block:: yaml

        policies:
          - name: apig-instance-create-plugin
            resource: huaweicloud.apig-instance
            filters:
              - type: value
                key: id
                value: 499e3bd193ba4db89a49f0ebdef19796
            actions:
              - type: create-plugin
                plugin_name: "rate_limit_plugin"
                plugin_type: "rate_limit"
                plugin_scope: "global"
                plugin_content: "{\"scope\":\"basic\",\"default_interval\":1,\"default_time_unit\":\"minute\",\"api_limit\":1000,\"algorithm\":\"counter\"}"
                remark: "Rate limiting plugin for API protection"
    """

    schema = type_schema(
        'create-plugin',
        plugin_name={'type': 'string'},
        plugin_type={'type': 'string', 'enum': [
            'cors', 'set_resp_headers', 'kafka_log', 'breaker', 'rate_limit',
            'third_auth', 'proxy_cache', 'proxy_mirror', 'oidc_auth', 'jwt_auth']},
        plugin_scope={'type': 'string', 'enum': ['global'], 'default': 'global'},
        plugin_content={'type': 'string'},
        remark={'type': 'string'},
        required=['plugin_name', 'plugin_type', 'plugin_content']
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']

        if not instance_id:
            instance_name = resource.get('instance_name', 'unknown')
            log.error(
                "[actions]-{create-plugin} The resource:[apig-instance] "
                "with id:[%s] name:[%s] create plugin is failed, "
                "cause: No available instance found", instance_id, instance_name)
            return

        try:
            # Build plugin create object from policy data
            plugin_create = PluginCreate(
                plugin_name=self.data['plugin_name'],
                plugin_type=self.data['plugin_type'],
                plugin_scope=self.data['plugin_scope'],
                plugin_content=self.data['plugin_content']
            )

            # Add remark if provided
            if 'remark' in self.data:
                plugin_create.remark = self.data['remark']

            # Create request
            request = CreatePluginRequest(
                instance_id=instance_id,
                body=plugin_create
            )

            # Send request
            response = client.create_plugin(request)

            plugin_name = self.data['plugin_name']
            plugin_type = self.data['plugin_type']
            instance_name = resource.get('instance_name')
            log.info(
                "[actions]-{create-plugin} The resource:[apig-instance] "
                "with id:[%s] name:[%s] create plugin '%s' (type: %s) is success.",
                instance_id, instance_name, plugin_name, plugin_type)

            return response
        except exceptions.ClientRequestException as e:
            plugin_name = self.data.get('plugin_name', 'unknown')
            plugin_type = self.data.get('plugin_type', 'unknown')
            instance_name = resource.get('instance_name')
            log.error(
                "[actions]-{create-plugin} The resource:[apig-instance] "
                "with id:[%s] name:[%s] create plugin '%s' (type: %s) is failed, cause: "
                "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                instance_id, instance_name, plugin_name, plugin_type,
                e.status_code, e.request_id, e.error_code, e.error_msg)
            raise


@ApigInstanceResource.action_registry.register('create-signature-key')
class CreateSignatureKeyAction(HuaweiCloudBaseAction):
    """Create signature key action for API Gateway instances

    This action creates a signature key for API Gateway instances to enhance API security
    by providing a mechanism to authenticate requests and prevent unauthorized access.

    :example:
    Define a policy to create a signature key for an API Gateway instance:

    .. code-block:: yaml

        policies:
          - name: apig-instance-create-signature-key
            resource: huaweicloud.apig-instance
            filters:
              - type: value
                key: id
                value: 499e3bd193ba4db89a49f0ebdef19796
            actions:
              - type: create
                name: "test-signature-key"
                sign_type: "hmac"
                sign_key: "fe6c10833b5e4c5f8944e76919d7fb30"
                sign_secret: "8f0b39c42a1445ccb4678f67f327d192"
    """

    schema = type_schema(
        'create-signature-key',
        name={'type': 'string'},
        sign_type={'type': 'string', 'enum': ['hmac', 'basic', 'public_key', 'aes']},
        sign_key={'type': 'string'},
        sign_secret={'type': 'string'},
        sign_algorithm={'type': 'string'},
        required=['name']
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']

        if not instance_id:
            instance_name = resource.get('instance_name', 'unknown')
            log.error(
                "[actions]-{create-signature-key} The resource:[apig-instance] "
                "with id:[%s] name:[%s] create signature key is failed, "
                "cause: No available instance found", instance_id, instance_name)
            return

        try:
            # Build signature key create object from policy data
            signature_key = BaseSignature(
                name=self.data['name']
            )

            # Add optional fields if provided
            if 'sign_type' in self.data:
                signature_key.sign_type = self.data['sign_type']
            if 'sign_key' in self.data:
                signature_key.sign_key = self.data['sign_key']
            if 'sign_secret' in self.data:
                signature_key.sign_secret = self.data['sign_secret']
            if 'sign_algorithm' in self.data:
                signature_key.sign_algorithm = self.data['sign_algorithm']

            # Create request
            request = CreateSignatureKeyV2Request(
                instance_id=instance_id,
                body=signature_key
            )

            # Send request
            response = client.create_signature_key_v2(request)

            signature_name = self.data['name']
            instance_name = resource.get('instance_name')
            log.info(
                "[actions]-{create-signature-key} The resource:[apig-instance] "
                "with id:[%s] name:[%s] create signature key '%s' is success.",
                instance_id, instance_name, signature_name)

            return response
        except exceptions.ClientRequestException as e:
            signature_name = self.data.get('name', 'unknown')
            instance_name = resource.get('instance_name')
            log.error(
                "[actions]-{create-signature-key} The resource:[apig-instance] "
                "with id:[%s] name:[%s] create signature key '%s' is failed, cause: "
                "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                instance_id, instance_name, signature_name,
                e.status_code, e.request_id, e.error_code, e.error_msg)
            raise


@ApigInstanceResource.action_registry.register('create-custom-authorizer')
class CreateCustomAuthorizerAction(HuaweiCloudBaseAction):
    """Create custom authorizer action for API Gateway instances

    This action creates a custom authorizer for API Gateway instances to enhance API security
    by providing custom authentication logic through serverless functions.

    :example:
    Define a policy to create a custom authorizer for an API Gateway instance:

    .. code-block:: yaml

        policies:
          - name: apig-instance-create-custom-authorizer
            resource: huaweicloud.apig-instance
            filters:
              - type: value
                key: id
                value: 499e3bd193ba4db89a49f0ebdef19796
            actions:
              - type: create-custom-authorizer
                name: "test_authorizer"
                custom_authorizer_type: "BACKEND"
                authorizer_type: "FUNC"
                authorizer_uri: "urn:fss:xx-xxx-1:08e31c7f5e00f4732ffdc009030ab25d:function:default:test"
                network_type: "V1"
                authorizer_version: "latest"
                authorizer_alias_uri: "urn:fss:xx-xxx-4:106506b9a92342df9a5025fc12351cfc:function:defau:apigDemo"
                ttl: 300
                user_data: "Custom authorizer for frontend authentication"
    """

    schema = type_schema(
        'create-custom-authorizer',
        name={'type': 'string'},
        custom_authorizer_type={'type': 'string', 'enum': ['FRONTEND', 'BACKEND']},
        authorizer_type={'type': 'string', 'enum': ['FUNC'], 'default': 'FUNC'},
        authorizer_uri={'type': 'string'},
        network_type={'type': 'string', 'enum': ['V1', 'V2'], 'default': 'V1'},
        authorizer_version={'type': 'string'},
        authorizer_alias_uri={'type': 'string'},
        identities={'type': 'array', 'items': {'type': 'object', 'properties': {
            'name': {'type': 'string'},
            'location': {'type': 'string'},
            'validation': {'type': 'string'}
        }}},
        ttl={'type': 'integer'},
        user_data={'type': 'string'},
        required=['name', 'type', 'authorizer_uri']
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']

        if not instance_id:
            instance_name = resource.get('instance_name', 'unknown')
            log.error(
                "[actions]-{create-custom-authorizer} The resource:[apig-instance] "
                "with id:[%s] name:[%s] create custom authorizer is failed, "
                "cause: No available instance found", instance_id, instance_name)
            return

        try:
            # Build authorizer create object from policy data
            authorizer_create = AuthorizerCreate(
                name=self.data['name'],
                type=self.data['custom_authorizer_type'],
                authorizer_type=self.data.get('authorizer_type', 'FUNC'),
                authorizer_uri=self.data['authorizer_uri']
            )

            # Add optional fields if provided
            if 'network_type' in self.data:
                authorizer_create.network_type = self.data['network_type']
            if 'authorizer_version' in self.data:
                authorizer_create.authorizer_version = self.data['authorizer_version']
            if 'authorizer_alias_uri' in self.data:
                authorizer_create.authorizer_alias_uri = self.data['authorizer_alias_uri']
            if 'identities' in self.data:
                identities = []
                for identity_data in self.data['identities']:
                    identity = Identity(
                        name=identity_data['name'],
                        location=identity_data['location']
                    )
                    if 'validation' in identity_data:
                        identity.validation = identity_data['validation']
                    identities.append(identity)
                authorizer_create.identities = identities
            if 'ttl' in self.data:
                authorizer_create.ttl = self.data['ttl']
            if 'user_data' in self.data:
                authorizer_create.user_data = self.data['user_data']

            # Create request
            request = CreateCustomAuthorizerV2Request(
                instance_id=instance_id,
                body=authorizer_create
            )

            # Send request
            response = client.create_custom_authorizer_v2(request)

            authorizer_name = self.data['name']
            instance_name = resource.get('instance_name')
            log.info(
                "[actions]-{create-custom-authorizer} The resource:[apig-instance] "
                "with id:[%s] name:[%s] create custom authorizer '%s' is success.",
                instance_id, instance_name, authorizer_name)

            return response
        except exceptions.ClientRequestException as e:
            authorizer_name = self.data.get('name', 'unknown')
            instance_name = resource.get('instance_name')
            log.error(
                "[actions]-{create-custom-authorizer} The resource:[apig-instance] "
                "with id:[%s] name:[%s] create custom authorizer '%s' is failed, cause: "
                "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                instance_id, instance_name, authorizer_name,
                e.status_code, e.request_id, e.error_code, e.error_msg)
            raise


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
                "[filters]-{get-api-resources} The resource:[apig-api] "
                "query API list is failed, cause: Unable to get valid APIG instance ID")
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
                    resource = safe_json_parse(response.apis)
                    for item in resource:
                        item["instance_id"] = instance_id
                    resources = resources + resource
                except exceptions.ClientRequestException as e:
                    log.error(
                        "[filters]-{get-api-resources} The resource:[apig-api] "
                        "query API list is failed, cause: "
                        "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                        e.status_code, e.request_id, e.error_code, e.error_msg, exc_info=True)
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
            api_name = resource.get('name', 'unknown')
            log.error(
                "[actions]-{delete} The resource:[apig-api] "
                "with id:[%s] name:[%s] delete API is failed, "
                "cause: No available instance found", api_id, api_name)
            return

        try:
            # Ensure instance_id is string type
            request = DeleteApiV2Request(
                instance_id=instance_id,
                api_id=api_id
            )

            client.delete_api_v2(request)
            api_name = resource.get('name')
            log.info(
                "[actions]-{delete} The resource:[apig-api] "
                "with id:[%s] name:[%s] delete API is success.",
                api_id, api_name)
        except exceptions.ClientRequestException as e:
            api_name = resource.get('name')
            log.error(
                "[actions]-{delete} The resource:[apig-api] "
                "with id:[%s] name:[%s] delete API is failed, cause: "
                "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                api_id, api_name, e.status_code, e.request_id, e.error_code, e.error_msg)
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
            api_name = resource.get('name', 'unknown')
            log.error(
                "[actions]-{update} The resource:[apig-api] "
                "with id:[%s] name:[%s] update API is failed, "
                "cause: No available instance found", api_id, api_name)
            return

        try:
            # First build the parameters to update
            update_body = self._build_update_body(resource)

            if not update_body:
                api_name = resource.get('name')
                log.error(
                    "[actions]-{update} The resource:[apig-api] "
                    "with id:[%s] name:[%s] update API is failed, "
                    "cause: No update parameters provided", api_id, api_name)
                return

            # Create update request, ensure instance_id is string type
            request = UpdateApiV2Request(
                instance_id=instance_id,
                api_id=api_id,
                body=update_body
            )

            # Send request
            response = client.update_api_v2(request)
            api_name = resource.get('name')
            log.info(
                "[actions]-{update} The resource:[apig-api] "
                "with id:[%s] name:[%s] update API is success.",
                api_id, api_name)
            return response
        except exceptions.ClientRequestException as e:
            api_name = resource.get('name')
            log.error(
                "[actions]-{update} The resource:[apig-api] "
                "with id:[%s] name:[%s] update API is failed, cause: "
                "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                api_id, api_name, e.status_code, e.request_id, e.error_code, e.error_msg)
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
                "[filters]-{get-stage-resources} The resource:[apig-stage] "
                "query environment list is failed, cause: Unable to get valid APIG instance ID")
            return []

        resources = []
        for instance_id in instance_ids:
            # Create new request object instead of modifying the incoming query
            request = ListEnvironmentsV2Request(limit=500)
            request.instance_id = instance_id

            # Call client method to process request
            try:
                response = client.list_environments_v2(request)
                resource = safe_json_parse(response.envs)
                for item in resource:
                    item["instance_id"] = instance_id
                resources = resources + resource

                return resources
            except exceptions.ClientRequestException as e:
                log.error(
                    "[filters]-{get-stage-resources} The resource:[apig-stage] "
                    "query environment list is failed, cause: "
                    "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                    e.status_code, e.request_id, e.error_code, e.error_msg, exc_info=True)
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
            env_name = resource.get('name', 'unknown')
            log.error(
                "[actions]-{update} The resource:[apig-stage] "
                "with id:[%s] name:[%s] update environment is failed, "
                "cause: No available instance found", env_id, env_name)
            return

        try:
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

            # Send request
            response = client.update_environment_v2(request)
            env_name = resource.get('name')
            log.info(
                "[actions]-{update} The resource:[apig-stage] "
                "with id:[%s] name:[%s] update environment is success.",
                env_id, env_name)
            return response
        except exceptions.ClientRequestException as e:
            env_name = resource.get('name')
            log.error(
                "[actions]-{update} The resource:[apig-stage] "
                "with id:[%s] name:[%s] update environment is failed, cause: "
                "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                env_id, env_name, e.status_code, e.request_id, e.error_code, e.error_msg)
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
            env_name = resource.get('name', 'unknown')
            log.error(
                "[actions]-{delete} The resource:[apig-stage] "
                "with id:[%s] name:[%s] delete environment is failed, "
                "cause: No available instance found", env_id, env_name)
            return

        try:
            # Ensure instance_id is string type
            request = DeleteEnvironmentV2Request(
                instance_id=instance_id,
                env_id=env_id
            )

            client.delete_environment_v2(request)
            env_name = resource.get('name')
            log.info(
                "[actions]-{delete} The resource:[apig-stage] "
                "with id:[%s] name:[%s] delete environment is success.",
                env_id, env_name)
        except exceptions.ClientRequestException as e:
            env_name = resource.get('name')
            log.error(
                "[actions]-{delete} The resource:[apig-stage] "
                "with id:[%s] name:[%s] delete environment is failed, cause: "
                "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                env_id, env_name, e.status_code, e.request_id, e.error_code, e.error_msg)
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
                "[filters]-{get-instance-id} The resource:[apig-api-groups] "
                "using instance_id from policy configuration: %s", instance_id)
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
                "[filters]-{get-instance-id} The resource:[apig-api-groups] "
                "query APIG instance list is failed, cause: %s", str(e), exc_info=True)

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
                "[filters]-{get-api-groups-resources} The resource:[apig-api-groups] "
                "query API group list is failed, cause: Unable to get valid APIG instance ID")
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
                    resource = safe_json_parse(response.groups)
                    for item in resource:
                        item["instance_id"] = instance_id
                    resources = resources + resource
                except exceptions.ClientRequestException as e:
                    log.error(
                        "[filters]-{get-api-groups-resources} The resource:[apig-api-groups] "
                        "query API group list is failed, cause: "
                        "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                        e.status_code, e.request_id, e.error_code, e.error_msg, exc_info=True)
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
            group_name = resource.get('name', 'unknown')
            log.error(
                "[actions]-{update-domain} The resource:[apig-api-groups] "
                "with id:[%s] name:[%s] update domain security policy is failed, "
                "cause: No domain_id specified", group_id, group_name)
            return

        try:
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

            # Send request
            response = client.update_domain_v2(request)
            group_name = resource.get('name')
            log.info(
                "[actions]-{update-domain} The resource:[apig-api-groups] "
                "with id:[%s] name:[%s] update domain security policy (domain_id: %s) is success.",
                group_id, group_name, domain_id)
            return response
        except exceptions.ClientRequestException as e:
            group_name = resource.get('name')
            log.error(
                "[actions]-{update-domain} The resource:[apig-api-groups] "
                "with id:[%s] name:[%s] update domain security policy (domain_id: %s) is failed, cause: "
                "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                group_id, group_name, domain_id,
                e.status_code, e.request_id, e.error_code, e.error_msg)
            raise


# Update SLDomain Setting
@ApiGroupResource.action_registry.register('update-sl-domain-setting')
class UpdateSLDomainSettingAction(HuaweiCloudBaseAction):
    """Update SLDomain setting action for API Gateway groups

    This action allows updating the debug domain access settings for API Gateway groups,
    controlling whether debug domains can be accessed.

    :example:
    Define a policy to update SLDomain settings for an API Gateway group:

    .. code-block:: yaml

        policies:
          - name: apig-group-update-sl-domain-setting
            resource: huaweicloud.apig-api-groups
            filters:
              - type: value
                key: id
                value: c77f5e81d9cb4424bf704ef2b0ac7600
            actions:
              - type: update-sl-domain-setting
                sl_domain_access_enabled: true
    """

    schema = type_schema(
        'update-sl-domain-setting',
        sl_domain_access_enabled={'type': 'boolean', 'required': True}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        group_id = resource['id']
        instance_id = resource.get('instance_id')

        if not instance_id:
            group_name = resource.get('name', 'unknown')
            log.error(
                "[actions]-{update-sl-domain-setting} The resource:[apig-api-groups] "
                "with id:[%s] name:[%s] update SL domain setting is failed, "
                "cause: No available instance found", group_id, group_name)
            return

        try:
            # Build domain access setting object from policy data
            domain_setting = SlDomainAccessSetting(
                sl_domain_access_enabled=self.data['sl_domain_access_enabled']
            )

            # Create update request
            request = UpdateSlDomainSettingV2Request(
                instance_id=instance_id,
                group_id=group_id,
                body=domain_setting
            )

            # Send request
            response = client.update_sl_domain_setting_v2(request)
            group_name = resource.get('name')
            access_status = "enabled" if self.data['sl_domain_access_enabled'] else "disabled"
            log.info(
                "[actions]-{update-sl-domain-setting} The resource:[apig-api-groups] "
                "with id:[%s] name:[%s] update SL domain setting (debug domain access %s) is success.",
                group_id, group_name, access_status)
            return response
        except exceptions.ClientRequestException as e:
            group_name = resource.get('name')
            access_status = "enable" if self.data.get('sl_domain_access_enabled', False) else "disable"
            log.error(
                "[actions]-{update-sl-domain-setting} The resource:[apig-api-groups] "
                "with id:[%s] name:[%s] %s debug domain access is failed, cause: "
                "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                group_id, group_name, access_status,
                e.status_code, e.request_id, e.error_code, e.error_msg)
            raise


# VPC Endpoint Resource Management
@resources.register('apig-vpc-endpoint')
class ApigVpcEndpointResource(QueryResourceManager):
    """
    Huawei Cloud API Gateway VPC Endpoint Resource Management
    """

    class resource_type(TypeInfo):
        service = 'apig-vpc-endpoint'
        enum_spec = ('list_endpoint_connections', 'connections', 'offset')
        id = 'id'
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
                "[filters]-{get-instance-id} The resource:[apig-vpc-endpoint] "
                "using instance_id from policy configuration: %s", instance_id)
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
                "[filters]-{get-instance-id} The resource:[apig-vpc-endpoint] "
                "query APIG instance list is failed, cause: %s", str(e), exc_info=True)

        return []

    def get_resources(self, query):
        return self.get_vpc_endpoint_resources(query)

    def _fetch_resources(self, query):
        return self.get_vpc_endpoint_resources(query)

    def get_vpc_endpoint_resources(self, query):
        """Override resource retrieval method to query VPC endpoint connections"""
        session = local_session(self.session_factory)
        client = session.client(self.resource_type.service)

        # Get instance ID
        instance_ids = self.get_instance_id()

        # Ensure instance_id is properly set
        if not instance_ids:
            log.error(
                "[filters]-{get-vpc-endpoint-resources} The resource:[apig-vpc-endpoint] "
                "query VPC endpoint connections is failed, cause: Unable to get valid APIG instance ID")
            return []

        resources = []
        for instance_id in instance_ids:
            offset, limit = 0, 500
            while True:
                # Create new request object
                request = ListEndpointConnectionsRequest(
                    instance_id=instance_id,
                    offset=offset,
                    limit=limit
                )

                # Call client method to process request
                try:
                    response = client.list_endpoint_connections(request)
                    resource = safe_json_parse(response.connections)
                    for item in resource:
                        item["instance_id"] = instance_id
                    resources = resources + resource
                except exceptions.ClientRequestException as e:
                    log.error(
                        "[filters]-{get-vpc-endpoint-resources} The resource:[apig-vpc-endpoint] "
                        "query VPC endpoint connections is failed, cause: "
                        "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                        e.status_code, e.request_id, e.error_code, e.error_msg, exc_info=True)
                    break

                offset += limit
                if not response.total or offset >= response.total:
                    break

        return resources


# VPC Endpoint Resource Actions
@ApigVpcEndpointResource.action_registry.register('accept-or-reject-vpcep-connection')
class AcceptOrRejectVpcEndpointConnectionAction(HuaweiCloudBaseAction):
    """Accept or reject VPC endpoint connection action

    This action allows accepting or rejecting VPC endpoint connections in API Gateway.

    :example:
    Define a policy to accept VPC endpoint connections:

    .. code-block:: yaml

        policies:
          - name: apig-vpc-endpoint-accept
            resource: huaweicloud.apig-vpc-endpoint
            filters:
              - type: value
                key: instance_id
                value: 499e3bd193ba4db89a49f0ebdef19796
            actions:
              - type: accept-or-reject-vpcep-connection
                action: receive
                endpoints:
                  - "669b61c0-b826-4888-a411-3d3fb4a753b7"
    """

    schema = type_schema(
        'accept-or-reject-vpcep-connection',
        action={'type': 'string', 'enum': ['receive', 'reject']},
        endpoints={'type': 'array', 'items': {'type': 'string'}}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        endpoints = self.data['endpoints']
        instance_id = resource.get('instance_id')

        if not instance_id:
            log.error(
                "[actions]-{accept-or-reject-vpcep-connection} The resource:[apig-vpc-endpoint] "
                "accept or reject VPC endpoint connection is failed, "
                "cause: No available instance found")
            return

        try:
            # Build connection action request body
            connection_action = ConnectionActionReq(
                action=self.data['action'],
                endpoints=endpoints
            )

            # Create request
            request = AcceptOrRejectEndpointConnectionsRequest(
                instance_id=instance_id,
                body=connection_action
            )

            # Send request
            response = client.accept_or_reject_endpoint_connections(request)

            action_desc = "accepted" if self.data['action'] == 'receive' else "rejected"
            endpoints_str = ", ".join(endpoints)
            log.info(
                "[actions]-{accept-or-reject-vpcep-connection} The resource:[apig-vpc-endpoint] "
                "with instance_id:[%s] %s VPC endpoint connection (endpoints: %s) is success.",
                instance_id, action_desc, endpoints_str)

            return response
        except exceptions.ClientRequestException as e:
            action_desc = "accept" if self.data['action'] == 'receive' else "reject"
            endpoints_str = ", ".join(endpoints)
            log.error(
                "[actions]-{accept-or-reject-vpcep-connection} The resource:[apig-vpc-endpoint] "
                "with instance_id:[%s] %s VPC endpoint connection (endpoints: %s) is failed, cause: "
                "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                instance_id, action_desc, endpoints_str,
                e.status_code, e.request_id, e.error_code, e.error_msg)
            raise


# Plugin Resource Management
@resources.register('apig-plugin')
class ApigPluginResource(QueryResourceManager):
    """
    Huawei Cloud API Gateway Plugin Resource Management
    """

    class resource_type(TypeInfo):
        service = 'apig-plugin'
        enum_spec = ('list_plugins', 'plugins', 'offset')
        id = 'plugin_id'
        name = 'plugin_name'
        filter_name = 'plugin_name'
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
                "[filters]-{get-instance-id} The resource:[apig-plugin] "
                "using instance_id from policy configuration: %s", instance_id)
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
                "[filters]-{get-instance-id} The resource:[apig-plugin] "
                "query APIG instance list is failed, cause: %s", str(e), exc_info=True)

        return []

    def get_resources(self, query):
        return self.get_policy_resources(query)

    def _fetch_resources(self, query):
        return self.get_policy_resources(query)

    def get_policy_resources(self, query):
        """Override resource retrieval method to query APIG plugins"""
        session = local_session(self.session_factory)
        client = session.client(self.resource_type.service)

        # Get instance ID
        instance_ids = self.get_instance_id()

        # Ensure instance_id is properly set
        if not instance_ids:
            log.error(
                "[filters]-{get-policy-resources} The resource:[apig-plugin] "
                "query plugin list is failed, cause: Unable to get valid APIG instance ID")
            return []

        resources = []
        for instance_id in instance_ids:
            offset, limit = 0, 500
            while True:
                # Create new request object
                request = ListPluginsRequest(offset=offset, limit=limit)
                request.instance_id = instance_id

                # Call client method to process request
                try:
                    response = client.list_plugins(request)
                    resource = safe_json_parse(response.plugins)
                    for item in resource:
                        item["instance_id"] = instance_id
                    resources = resources + resource
                except exceptions.ClientRequestException as e:
                    log.error(
                        "[filters]-{get-policy-resources} The resource:[apig-plugin] "
                        "query plugin list is failed, cause: "
                        "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                        e.status_code, e.request_id, e.error_code, e.error_msg, exc_info=True)
                    break

                offset += limit
                if not response.total or offset >= response.total:
                    break

        return resources


# Plugin Resource Actions
@ApigPluginResource.action_registry.register('bind-api')
class BindApiPluginAction(HuaweiCloudBaseAction):
    """Bind API to plugin action

    This action binds specified APIs to a plugin in API Gateway.

    :example:
    Define a policy to bind APIs to a plugin:

    .. code-block:: yaml

        policies:
          - name: apig-plugin-bind-api
            resource: huaweicloud.apig-plugin
            filters:
              - type: value
                key: instance_id
                value: 499e3bd193ba4db89a49f0ebdef19796
              - type: value
                key: plugin_id
                value: c18dc6f7a0a84a58b01966069ba434ac
            actions:
              - type: bind-api
                env_id: "DEFAULT_ENVIRONMENT_RELEASE_ID"
                api_ids:
                  - "013cf5266c9049cd977a4bb22fc096cd"
                  - "8686f89d846d4a85be4c6d22263cf5e4"
    """

    schema = type_schema(
        'bind-api',
        env_id={'type': 'string'},
        api_ids={'type': 'array', 'items': {'type': 'string'}},
        required=['env_id', 'api_ids']
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        plugin_id = resource['plugin_id']
        instance_id = resource.get('instance_id')

        if not instance_id:
            plugin_name = resource.get('plugin_name', 'unknown')
            log.error(
                "[actions]-{bind-api} The resource:[apig-plugin] "
                "with id:[%s] name:[%s] bind API to plugin is failed, "
                "cause: No available instance found", plugin_id, plugin_name)
            return

        try:
            # Build plugin operation API info
            plugin_oper_api_info = PluginOperApiInfo(
                env_id=self.data['env_id'],
                api_ids=self.data['api_ids']
            )

            # Create request
            request = AttachApiToPluginRequest(
                instance_id=instance_id,
                plugin_id=plugin_id,
                body=plugin_oper_api_info
            )

            # Send request
            response = client.attach_api_to_plugin(request)

            plugin_name = resource.get('plugin_name')
            api_count = len(self.data['api_ids'])
            log.info(
                "[actions]-{bind-api} The resource:[apig-plugin] "
                "with id:[%s] name:[%s] bind %d APIs to plugin in environment %s is success.",
                plugin_id, plugin_name, api_count, self.data['env_id'])

            return response
        except exceptions.ClientRequestException as e:
            plugin_name = resource.get('plugin_name')
            log.error(
                "[actions]-{bind-api} The resource:[apig-plugin] "
                "with id:[%s] name:[%s] bind API to plugin is failed, cause: "
                "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                plugin_id, plugin_name, e.status_code, e.request_id, e.error_code, e.error_msg)
            raise


# Signature Key Resource Management
@resources.register('apig-signature-key')
class SignatureKeyResource(QueryResourceManager):
    """
    Huawei Cloud API Gateway Signature Key Resource Management
    """

    class resource_type(TypeInfo):
        service = 'apig-signature-key'
        enum_spec = ('list_signature_keys_v2', 'signatures', 'offset')
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
                "[filters]-{get-instance-id} The resource:[apig-signature-key] "
                "using instance_id from policy configuration: %s", instance_id)
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
                "[filters]-{get-instance-id} The resource:[apig-signature-key] "
                "query APIG instance list is failed, cause: %s", str(e), exc_info=True)

        return []

    def get_resources(self, query):
        return self.get_signature_keys_resources(query)

    def _fetch_resources(self, query):
        return self.get_signature_keys_resources(query)

    def get_signature_keys_resources(self, query):
        """Override resource retrieval method to query signature keys"""
        session = local_session(self.session_factory)
        client = session.client(self.resource_type.service)

        # Get instance ID
        instance_ids = self.get_instance_id()

        # Ensure instance_id is properly set
        if not instance_ids:
            log.error(
                "[filters]-{get-signature-keys-resources} The resource:[apig-signature-key] "
                "query signature key list is failed, cause: Unable to get valid APIG instance ID")
            return []

        resources = []
        for instance_id in instance_ids:
            offset, limit = 0, 500
            while True:
                # Create new request object
                request = ListSignatureKeysV2Request(offset=offset, limit=limit)
                request.instance_id = instance_id

                # Call client method to process request
                try:
                    response = client.list_signature_keys_v2(request)
                    resource = safe_json_parse(response.signs)
                    for item in resource:
                        item["instance_id"] = instance_id
                    resources = resources + resource
                except exceptions.ClientRequestException as e:
                    log.error(
                        "[filters]-{get-signature-keys-resources} The resource:[apig-signature-key] "
                        "query signature key list is failed, cause: "
                        "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                        e.status_code, e.request_id, e.error_code, e.error_msg, exc_info=True)
                    break

                offset += limit
                if not response.total or offset >= response.total:
                    break

        return resources


# Signature Key Resource Actions
@SignatureKeyResource.action_registry.register('associate')
class AssociateSignatureKeyAction(HuaweiCloudBaseAction):
    """Associate signature key to APIs action

    This action binds a signature key to specified APIs in API Gateway.

    :example:
    Define a policy to bind a signature key to APIs:

    .. code-block:: yaml

        policies:
          - name: apig-signature-key-associate
            resource: huaweicloud.apig-signature-key
            filters:
              - type: value
                key: instance_id
                value: 499e3bd193ba4db89a49f0ebdef19796
              - type: value
                key: id
                value: 0b0e8f456b8742218af75f945307173c
            actions:
              - type: associate
                publish_ids:
                  - "ed398470b8664d038802e8c5f6f29c36"
                  - "927a7009984e4102b7aa0188b82ca485"
    """

    schema = type_schema(
        'associate',
        publish_ids={'type': 'array', 'items': {'type': 'string'}},
        required=['publish_ids']
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        signature_key_id = resource['id']
        instance_id = resource.get('instance_id')

        if not instance_id:
            signature_name = resource.get('name', 'unknown')
            log.error(
                "[actions]-{associate} The resource:[apig-signature-key] "
                "with id:[%s] name:[%s] associate signature key to APIs is failed, "
                "cause: No available instance found", signature_key_id, signature_name)
            return

        try:
            # Build signature API binding object from policy data
            binding = SignApiBinding(
                sign_id=signature_key_id,
                publish_ids=self.data['publish_ids']
            )

            # Create request
            request = AssociateSignatureKeyV2Request(
                instance_id=instance_id,
                body=binding
            )

            # Send request
            response = client.associate_signature_key_v2(request)

            signature_name = resource.get('name')
            api_count = len(self.data['publish_ids'])
            log.info(
                "[actions]-{associate} The resource:[apig-signature-key] "
                "with id:[%s] name:[%s] associate signature key to %d APIs is success.",
                signature_key_id, signature_name, api_count)

            return response
        except exceptions.ClientRequestException as e:
            signature_name = resource.get('name')
            log.error(
                "[actions]-{associate} The resource:[apig-signature-key] "
                "with id:[%s] name:[%s] associate signature key to APIs is failed, cause: "
                "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                signature_key_id, signature_name,
                e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
