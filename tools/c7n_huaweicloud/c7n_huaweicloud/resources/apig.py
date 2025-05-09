# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from datetime import datetime
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkapig.v2 import (
    # API接口相关
    ListApisV2Request,
    DeleteApiV2Request,
    UpdateApiV2Request,

    # 环境相关
    ListEnvironmentsV2Request,
    UpdateEnvironmentV2Request,
    DeleteEnvironmentV2Request,

    # 域名相关
    UpdateDomainV2Request,

    # 分组相关
    ListApiGroupsV2Request,

    # 标签相关
    ListProjectInstanceTagsRequest,
    BatchCreateOrDeleteInstanceTagsRequest,
)

from c7n.filters import Filter, ValueFilter
from c7n.filters.core import AgeFilter, ListItemFilter
from c7n.utils import type_schema, local_session, jmespath_search
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction

log = logging.getLogger('custodian.huaweicloud.apig')


# API资源管理
@resources.register('rest-api')
class ApiResource(QueryResourceManager):
    """华为云API网关API资源管理

    :示例:

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
        """获取APIG实例ID"""
        session = local_session(self.session_factory)
        return session.get_apig_instance_id()


# API资源过滤器
@ApiResource.filter_registry.register('age')
class ApiAgeFilter(AgeFilter):
    """API创建时间过滤器

    :示例:

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


# API资源操作
@ApiResource.action_registry.register('delete')
class DeleteApiAction(HuaweiCloudBaseAction):
    """删除API操作

    :示例:

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
            # 当资源中没有实例ID时，使用默认实例ID
            instance_id = 'cc371c55cc9141558ccd76b86903e78b'
            log.info(f"API {api_id} 未找到实例ID，使用默认实例ID: {instance_id}")

        try:
            request = DeleteApiV2Request(
                instance_id=instance_id,
                api_id=api_id
            )
            client.delete_api_v2(request)
            self.log.info(f"成功删除API: {resource.get('name')} (ID: {api_id})")
        except exceptions.ClientRequestException as e:
            self.log.error(f"删除API失败 {resource.get('name')} (ID: {api_id}): {e}")
            raise

# 环境资源管理
@resources.register('rest-stage')
class StageResource(QueryResourceManager):
    """华为云API网关环境资源管理

    :示例:

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
        """获取APIG实例ID"""
        session = local_session(self.session_factory)
        return session.get_apig_instance_id()

# 更新环境资源
@StageResource.action_registry.register('update')
class UpdateStageAction(HuaweiCloudBaseAction):
    """更新环境操作

    :示例:

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
            # 当资源中没有实例ID时，使用默认实例ID
            instance_id = 'cc371c55cc9141558ccd76b86903e78b'
            log.info(f"API {env_id} 未找到实例ID，使用默认实例ID: {instance_id}")

        try:
            # 准备更新参数
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
            self.log.info(f"成功更新环境: {resource.get('name')} (ID: {env_id})")
        except exceptions.ClientRequestException as e:
            self.log.error(f"更新环境失败 {resource.get('name')} (ID: {env_id}): {e}")
            raise

# 删除环境操作
@StageResource.action_registry.register('delete')
class DeleteStageAction(HuaweiCloudBaseAction):
    """删除环境操作

    :示例:

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
            # 当资源中没有实例ID时，使用默认实例ID
            instance_id = 'cc371c55cc9141558ccd76b86903e78b'
            log.info(f"API {env_id} 未找到实例ID，使用默认实例ID: {instance_id}")

        try:
            request = DeleteEnvironmentV2Request(
                instance_id=instance_id,
                env_id=env_id
            )
            client.delete_environment_v2(request)
            self.log.info(f"成功删除环境: {resource.get('name')} (ID: {env_id})")
        except exceptions.ClientRequestException as e:
            self.log.error(f"删除环境失败 {resource.get('name')} (ID: {env_id}): {e}")
            raise

# API分组资源管理
@resources.register('api-groups')
class ApiGroupResource(QueryResourceManager):
    """华为云API网关分组资源管理

    :示例:

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

# 更新域名
@ApiGroupResource.action_registry.register('update-security')
class UpdateDomainSecurityAction(HuaweiCloudBaseAction):
    """更新域名安全策略操作

    :示例:

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
            self.log.error(f"未指定需要更新的域名ID，无法执行操作，分组ID: {group_id}")
            return

        if not instance_id:
            # 当资源中没有实例ID时，使用默认实例ID
            instance_id = 'cc371c55cc9141558ccd76b86903e78b'
            log.info(f"分组 {group_id} 未找到实例ID，使用默认实例ID: {instance_id}")

        try:
            # 准备更新参数
            update_info = {}
            
            if 'min_ssl_version' in self.data:
                update_info['min_ssl_version'] = self.data['min_ssl_version']
            
            # 检查URL域名列表，获取域名信息
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
            self.log.info(f"成功更新域名安全策略: 分组 {resource.get('name')} (ID: {group_id})，域名ID: {domain_id}")
        except exceptions.ClientRequestException as e:
            self.log.error(f"更新域名安全策略失败 分组 {resource.get('name')} (ID: {group_id})，域名ID: {domain_id}: {e}")
            raise
