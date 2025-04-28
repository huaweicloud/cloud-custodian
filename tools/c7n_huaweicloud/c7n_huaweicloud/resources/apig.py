# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
#
# 华为云API网关 (APIG) 资源、过滤器和操作的实现

import jmespath
import logging
from datetime import datetime

from c7n.filters.core import type_schema, ValueFilter, ListItemFilter, FilterRegistry
from c7n.filters import Filter, AgeFilter
from c7n.utils import local_session, type_schema

from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, QueryMeta

from huaweicloudsdkapig.v2 import ListApisV2Request, DeleteApiV2Request,ListProjectInstanceTagsRequest
from huaweicloudsdkapig.v2 import UpdateEnvironmentV2Request, DeleteEnvironmentV2Request
from huaweicloudsdkapig.v2 import UpdateDomainV2Request

log = logging.getLogger('custodian.huaweicloud.apig')


@resources.register('apig')
class APIG(QueryResourceManager):
    """华为云API网关（APIG）资源管理器

    :example:

    .. code-block:: yaml

        policies:
          - name: list-apig-apis
            resource: huaweicloud.apig
            filters:
              - type: value
                key: name
                value: test-api
    """

    class resource_type(object, metaclass=QueryMeta):
        """定义APIG资源类型信息"""
        service = 'apig'  # 指定对应的华为云服务名称
        # API操作、结果列表键和分页参数
        # 'list_apis_v2' 是API方法名
        # 'apis' 是包含API列表的响应字段名
        # 'marker' 表示使用marker分页方式
        enum_spec = ('list_apis_v2', 'apis', 'marker')
        id = 'id'  # 指定资源唯一标识符字段名
        name = 'name'  # 指定资源名称字段名
        taggable = True  # 指示此资源支持标签
        tag_resource_type = 'apig'  # 查询标签时使用的资源类型
        
    def augment(self, resources):
        """
        增强资源数据，添加标签信息

        :param resources: API资源列表
        :return: 增强后的资源列表
        """
        client = self.get_client()
        session = local_session(self.session_factory)
        
        for resource in resources:
            # 确保有tag_resource_type字段
            if not resource.get('tag_resource_type'):
                resource['tag_resource_type'] = self.resource_type.tag_resource_type
            
            # 获取API的标签
            try:
                request = ListProjectInstanceTagsRequest()
                request.resource_type = self.resource_type.tag_resource_type
                request.resource_id = resource['id']
                response = client.list_project_instance_tags(request)
                if hasattr(response, 'tags') and response.tags:
                    resource['Tags'] = [{
                        'Key': tag.key,
                        'Value': tag.value
                    } for tag in response.tags]
            except Exception as e:
                log.warning(f"获取API标签失败: {e}")
                
            # 转换注册时间和更新时间为标准格式
            if 'register_time' in resource:
                register_time = resource['register_time']
                try:
                    if isinstance(register_time, str):
                        resource['register_time'] = datetime.strptime(
                            register_time, '%Y-%m-%dT%H:%M:%SZ'
                        )
                except Exception as e:
                    log.warning(f"转换注册时间格式失败: {e}")
                    
            if 'update_time' in resource:
                update_time = resource['update_time']
                try:
                    if isinstance(update_time, str):
                        resource['update_time'] = datetime.strptime(
                            update_time, '%Y-%m-%dT%H:%M:%S.%fZ'
                        )
                except Exception as e:
                    log.warning(f"转换更新时间格式失败: {e}")
                
        return resources

@APIG.filter_registry.register('age')
class APIGAgeFilter(AgeFilter):
    """APIG API创建时间过滤器

    根据API的创建时间进行过滤。

    :example:

    .. code-block:: yaml

        policies:
          - name: old-apis
            resource: huaweicloud.apig
            filters:
              - type: age
                days: 90
                op: gt
    """

    schema = type_schema(
        'age',
        op={'$ref': '#/definitions/filters_common/comparison_operators'},
        days={'type': 'number'},
        hours={'type': 'number'},
        minutes={'type': 'number'}
    )
    date_attribute = "register_time"

    def get_resource_date(self, resource):
        """
        获取资源的创建日期

        :param resource: 资源对象
        :return: 创建日期
        """
        # 获取资源的注册时间
        date_str = resource.get(self.date_attribute)
        
        if not date_str:
            return None
            
        # 如果已经转换为datetime对象，直接返回
        if isinstance(date_str, datetime):
            return date_str
            
        # 否则尝试转换
        try:
            return datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%SZ')
        except Exception:
            log.warning(
                f"无法解析API {resource.get('id', 'unknown')} 的日期 {date_str}"
            )
            return None

@APIG.action_registry.register('delete')
class DeleteAPI(HuaweiCloudBaseAction):
    """删除API操作

    :example:

    .. code-block:: yaml

        policies:
          - name: delete-test-apis
            resource: huaweicloud.apig
            filters:
              - type: value
                key: name
                value: test-api
            actions:
              - delete
    """

    schema = type_schema('delete')

    def perform_action(self, resource):
        """
        执行删除API操作

        :param resource: 要删除的API资源
        """
        client = self.manager.get_client()
        api_id = resource['id']
        instance_id = resource.get('instance_id')
        
        if not instance_id:
            # 当资源中没有实例ID时，使用默认实例ID
            instance_id = 'cc371c55cc9141558ccd76b86903e78b'
            log.info(f"API {api_id} 未找到实例ID，使用默认实例ID: {instance_id}")
        
        try:
            # 创建删除API请求
            request = DeleteApiV2Request()
            request.api_id = api_id
            request.instance_id = instance_id
            
            # 执行删除操作
            client.delete_api_v2(request)
            log.info(f"成功删除API: {api_id}")
        except Exception as e:
            log.error(f"删除API {api_id} 失败: {e}")

@APIG.action_registry.register('update-environment')
class UpdateEnvironment(HuaweiCloudBaseAction):
    """修改环境信息

    :example:

    .. code-block:: yaml

        policies:
          - name: update-test-environment
            resource: huaweicloud.apig
            actions:
              - type: update-environment
                environment_id: 7a1ad0c350844ee69435ab297c1e6d18
                name: "updated-test-env"
                description: "Updated test environment"
    """

    schema = type_schema(
        'update-environment',
        environment_id={'type': 'string'},
        name={'type': 'string'},
        description={'type': 'string'},
        required=['environment_id']
    )
    permissions = ('apig:updateEnvironment',)

    def perform_action(self, resource):
        """
        执行更新环境操作

        :param resource: 资源对象
        """
        client = self.manager.get_client()
        environment_id = self.data.get('environment_id')
        instance_id = resource.get('instance_id')
            
        if not instance_id:
            # 当资源中没有实例ID时，使用默认实例ID
            instance_id = 'cc371c55cc9141558ccd76b86903e78b'
            log.info(f"环境 {environment_id} 未找到实例ID，使用默认实例ID: {instance_id}")
            
        try:
            # 创建更新环境请求
            request = UpdateEnvironmentV2Request()
            request.env_id = environment_id
            request.instance_id = instance_id
            
            # 设置请求体
            body = {}
            if 'name' in self.data:
                body['name'] = self.data['name']
            if 'description' in self.data:
                body['remark'] = self.data['description']
                
            request.body = body
            
            # 执行更新操作
            client.update_environment_v2(request)
            log.info(f"成功更新环境 {environment_id}")
        except Exception as e:
            log.error(f"更新环境 {environment_id} 失败: {e}")

@APIG.action_registry.register('delete-environment')
class DeleteEnvironment(HuaweiCloudBaseAction):
    """删除环境

    :example:

    .. code-block:: yaml

        policies:
          - name: delete-test-environment
            resource: huaweicloud.apig
            actions:
              - type: delete-environment
                environment_id: 7a1ad0c350844ee69435ab297c1e6d18
    """

    schema = type_schema(
        'delete-environment',
        environment_id={'type': 'string'},
        required=['environment_id']
    )
    permissions = ('apig:deleteEnvironment',)

    def perform_action(self, resource):
        """
        执行删除环境操作

        :param resource: 资源对象
        """
        client = self.manager.get_client()
        environment_id = self.data.get('environment_id')
        instance_id = resource.get('instance_id')
            
        if not instance_id:
            # 当资源中没有实例ID时，使用默认实例ID
            instance_id = 'cc371c55cc9141558ccd76b86903e78b'
            log.info(f"环境 {environment_id} 未找到实例ID，使用默认实例ID: {instance_id}")
            
        try:
            # 创建删除环境请求
            request = DeleteEnvironmentV2Request()
            request.env_id = environment_id
            request.instance_id = instance_id
            
            # 执行删除操作
            client.delete_environment_v2(request)
            log.info(f"成功删除环境 {environment_id}")
        except Exception as e:
            log.error(f"删除环境 {environment_id} 失败: {e}")

@APIG.action_registry.register('update-domain')
class UpdateDomain(HuaweiCloudBaseAction):
    """修改自定义域名信息

    :example:

    .. code-block:: yaml

        policies:
          - name: update-custom-domain
            resource: huaweicloud.apig
            actions:
              - type: update-domain
                domain_id: 7a1ad0c350844ee69435ab297c1e6d18
                min_ssl_version: TLSv1.2
    """

    schema = type_schema(
        'update-domain',
        domain_id={'type': 'string'},
        min_ssl_version={'type': 'string', 'enum': ['TLSv1.1', 'TLSv1.2']},
        required=['domain_id']
    )
    permissions = ('apig:updateDomain',)

    def perform_action(self, resource):
        """
        执行更新域名操作

        :param resource: 资源对象
        """
        client = self.manager.get_client()
        domain_id = self.data.get('domain_id')
        instance_id = resource.get('instance_id')
            
        if not instance_id:
            # 当资源中没有实例ID时，使用默认实例ID
            instance_id = 'cc371c55cc9141558ccd76b86903e78b'
            log.info(f"域名 {domain_id} 未找到实例ID，使用默认实例ID: {instance_id}")
            
        try:
            # 创建更新域名请求
            request = UpdateDomainV2Request()
            request.domain_id = domain_id
            request.instance_id = instance_id
            
            # 设置请求体
            body = {}
            if 'min_ssl_version' in self.data:
                body['min_ssl_version'] = self.data['min_ssl_version']
                
            request.body = body
            
            # 执行更新操作
            client.update_domain_v2(request)
            log.info(f"成功更新域名 {domain_id}")
        except Exception as e:
            log.error(f"更新域名 {domain_id} 失败: {e}")