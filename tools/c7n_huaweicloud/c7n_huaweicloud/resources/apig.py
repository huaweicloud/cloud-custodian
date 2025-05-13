# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkapig.v2 import (
    # API interface related
    DeleteApiV2Request,
    UpdateApiV2Request,

    # Environment related
    UpdateEnvironmentV2Request,
    DeleteEnvironmentV2Request,

    # Domain related
    UpdateDomainV2Request,

)

from c7n.filters.core import AgeFilter
from c7n.utils import type_schema, local_session
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction

log = logging.getLogger('custodian.huaweicloud.apig')


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

    def _get_instance_id(self):
        """Get APIG instance ID"""
        session = local_session(self.session_factory)
        return session.get_apig_instance_id()


# API Resource Filters
@ApiResource.filter_registry.register('age')
class ApiAgeFilter(AgeFilter):
    """API creation time filter

    :example:

    .. code-block:: yaml

        policies:
          - name: apig-api-old
            resource: huaweicloud.rest-api
            filters:
              - type: age
                days: 90
                op: gt
    """

    schema = type_schema(
        'age',
        op={
            '$ref': '#/definitions/filters_common/comparison_operators'
        },
        days={'type': 'number'},
        hours={'type': 'number'},
        minutes={'type': 'number'}
    )
    date_attribute = "register_time"


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
            # When resource doesn't have instance ID, use default instance ID
            instance_id = 'cc371c55cc9141558ccd76b86903e78b'
            log.info(
                f"API {api_id} instance ID not found, using default instance ID: {instance_id}")

        try:
            request = DeleteApiV2Request(
                instance_id=instance_id,
                api_id=api_id
            )
            client.delete_api_v2(request)
            self.log.info(
                f"Successfully deleted API: {resource.get('name')} (ID: {api_id})")
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to delete API {resource.get('name')} (ID: {api_id}): {e}")
            raise

# API Update Action


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
                key: name
                value: test-api
            actions:
              - type: update
                name: updated-api-name
                req_protocol: HTTPS
                req_method: POST
                remark: "Updated by Cloud Custodian"
    """

    schema = type_schema(
        'update',
        name={'type': 'string'},
        # 1: public API, 2: private API
        type={'type': 'integer', 'enum': [1, 2]},
        version={'type': 'string'},
        req_protocol={'type': 'string', 'enum': [
            'HTTP', 'HTTPS', 'BOTH', 'GRPCS']},
        req_method={'type': 'string', 'enum': [
            'GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'PATCH', 'OPTIONS', 'ANY']},
        req_uri={'type': 'string'},
        auth_type={'type': 'string', 'enum': [
            'NONE', 'APP', 'IAM', 'AUTHORIZER']},
        cors={'type': 'boolean'},
        match_mode={'type': 'string', 'enum': ['NORMAL', 'SWA']},
        remark={'type': 'string'},
        backend_type={'type': 'string', 'enum': ['HTTP', 'FUNCTION', 'MOCK']},
        result_normal_sample={'type': 'string'},
        result_failure_sample={'type': 'string'},
        authorizer_id={'type': 'string'},
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        api_id = resource['id']
        instance_id = resource.get('instance_id')

        if not instance_id:
            # When resource doesn't have instance ID, use default instance ID
            instance_id = 'cc371c55cc9141558ccd76b86903e78b'
            log.info(
                f"API {api_id} instance ID not found, using default instance ID: {instance_id}")

        try:
            # 首先构建需要更新的参数
            update_body = self._build_update_body(resource)

            if not update_body:
                self.log.warning(
                    f"No update parameters provided for API {resource.get('name')} (ID: {api_id}), skipping update")
                return

            # 创建更新请求
            request = UpdateApiV2Request(
                instance_id=instance_id,
                api_id=api_id,
                body=update_body
            )

            # 发送请求
            response = client.update_api_v2(request)
            self.log.info(
                f"Successfully updated API: {resource.get('name')} (ID: {api_id})")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to update API {resource.get('name')} (ID: {api_id}): {e}")
            raise

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
            'type': 'type',
            'version': 'version',
            'req_protocol': 'req_protocol',
            'req_method': 'req_method',
            'req_uri': 'req_uri',
            'auth_type': 'auth_type',
            'cors': 'cors',
            'match_mode': 'match_mode',
            'remark': 'remark',
            'backend_type': 'backend_type',
            'result_normal_sample': 'result_normal_sample',
            'result_failure_sample': 'result_failure_sample',
            'authorizer_id': 'authorizer_id'
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

    def _get_instance_id(self):
        """Get APIG instance ID"""
        session = local_session(self.session_factory)
        return session.get_apig_instance_id()

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
                description: "Updated by Cloud Custodian"
                enable_metrics: true
    """

    schema = type_schema(
        'update',
        description={'type': 'string'},
        enable_metrics={'type': 'boolean'},
        is_waf_enabled={'type': 'boolean'},
        is_client_certificate_required={'type': 'boolean'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        env_id = resource['id']
        instance_id = resource.get('instance_id')

        if not instance_id:
            # When resource doesn't have instance ID, use default instance ID
            instance_id = 'cc371c55cc9141558ccd76b86903e78b'
            log.info(
                f"API {env_id} instance ID not found, using default instance ID: {instance_id}")

        try:
            # Prepare update parameters
            update_info = {}

            if 'name' in self.data:
                update_info['name'] = self.data['name']
            if 'description' in self.data:
                update_info['remark'] = self.data['description']

            request = UpdateEnvironmentV2Request(
                instance_id=instance_id,
                env_id=env_id,
                body=update_info
            )
            client.update_environment_v2(request)
            self.log.info(
                f"Successfully updated environment: {resource.get('name')} (ID: {env_id})")
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to update environment {resource.get('name')} (ID: {env_id}): {e}")
            raise

# Delete Environment Action


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
            # When resource doesn't have instance ID, use default instance ID
            instance_id = 'cc371c55cc9141558ccd76b86903e78b'
            log.info(
                f"API {env_id} instance ID not found, using default instance ID: {instance_id}")

        try:
            request = DeleteEnvironmentV2Request(
                instance_id=instance_id,
                env_id=env_id
            )
            client.delete_environment_v2(request)
            self.log.info(
                f"Successfully deleted environment: {resource.get('name')} (ID: {env_id})")
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to delete environment {resource.get('name')} (ID: {env_id}): {e}")
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

# Update Domain


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
                domain_id: 2c9eb1538a138432018a13ccccc00001
                min_ssl_version: TLSv1.2
    """

    schema = type_schema(
        'update-security',
        domain_id={'type': 'string'},
        min_ssl_version={'type': 'string', 'enum': ['TLSv1.1', 'TLSv1.2']}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        group_id = resource['id']
        instance_id = resource.get('instance_id')
        domain_id = self.data.get('domain_id')

        if not domain_id:
            self.log.error(
                f"Domain ID not specified, cannot execute operation, group ID: {group_id}")
            return

        if not instance_id:
            # When resource doesn't have instance ID, use default instance ID
            instance_id = 'cc371c55cc9141558ccd76b86903e78b'
            log.info(
                f"Group {group_id} instance ID not found, using default instance ID: {instance_id}")

        try:
            # Prepare update parameters
            update_info = {}

            if 'min_ssl_version' in self.data:
                update_info['min_ssl_version'] = self.data['min_ssl_version']

            # Check URL domain list, get domain information
            domain_info = None
            if 'url_domains' in resource:
                for domain in resource['url_domains']:
                    if domain['id'] == domain_id:
                        domain_info = domain
                        break

            request = UpdateDomainV2Request(
                instance_id=instance_id,
                group_id=group_id,
                domain_id=domain_id,
                body=update_info
            )
            client.update_domain_v2(request)
            self.log.info(
                f"Successfully updated domain security policy: Group {resource.get('name')} (ID: {group_id}), Domain ID: {domain_id}")
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to update domain security policy Group {resource.get('name')} (ID: {group_id}), Domain ID: {domain_id}: {e}")
            raise
