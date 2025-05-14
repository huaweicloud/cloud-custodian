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
        """处理资源数据，确保project_id等字段存在"""
        processed_resources = []
        
        for resource in resources:
            resource_dict = {}
            
            # 优先从原始属性中提取数据
            if hasattr(resource, '__dict__') and hasattr(resource, '_field_names'):
                # 处理SDK对象模式
                for field in resource._field_names:
                    if hasattr(resource, field):
                        value = getattr(resource, field)
                        # 确保值是可序列化的基本类型
                        if isinstance(value, (str, int, float, bool, type(None))) or (
                            isinstance(value, (list, dict)) and not any(
                                hasattr(item, '__dict__') for item in value) if isinstance(value, list) else True
                        ):
                            resource_dict[field] = value
            else:
                # 处理字典模式
                for key, value in resource.items() if isinstance(resource, dict) else []:
                    # 确保值是可序列化的基本类型
                    if isinstance(value, (str, int, float, bool, type(None))) or (
                        isinstance(value, (list, dict)) and not any(
                            hasattr(item, '__dict__') for item in value) if isinstance(value, list) else True
                    ):
                        resource_dict[key] = value
            
            # 确保基本字段存在
            resource_dict['id'] = getattr(resource, 'id', resource.get('id', ''))
            resource_dict['instance_name'] = getattr(resource, 'instance_name', resource.get('instance_name', ''))
            
            # 添加其他重要字段
            if hasattr(resource, 'project_id') or (isinstance(resource, dict) and 'project_id' in resource):
                resource_dict['project_id'] = getattr(resource, 'project_id', resource.get('project_id', ''))
            if hasattr(resource, 'type') or (isinstance(resource, dict) and 'type' in resource):
                resource_dict['type'] = getattr(resource, 'type', resource.get('type', ''))
            if hasattr(resource, 'status') or (isinstance(resource, dict) and 'status' in resource):
                resource_dict['status'] = getattr(resource, 'status', resource.get('status', ''))
            if hasattr(resource, 'spec') or (isinstance(resource, dict) and 'spec' in resource):
                resource_dict['spec'] = getattr(resource, 'spec', resource.get('spec', ''))
            if hasattr(resource, 'create_time') or (isinstance(resource, dict) and 'create_time' in resource):
                resource_dict['create_time'] = getattr(resource, 'create_time', resource.get('create_time', ''))
                
            # 添加已处理的资源
            processed_resources.append(resource_dict)
                
        return processed_resources
        
    def augment(self, resources):
        """增强资源信息"""
        # 确保所有资源都可以被正确序列化
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
        """查询并获取API网关实例ID
        
        通过查询apig-instance接口获取可用的实例ID，优先使用运行中的实例
        如果未找到可用实例，则返回默认实例ID
        """
        session = local_session(self.session_factory)
        
        # 如果策略中已指定instance_id，则直接使用
        if hasattr(self, 'data') and isinstance(self.data, dict) and 'instance_id' in self.data:
            instance_id = self.data['instance_id']
            log.info(f"使用策略配置中的instance_id: {instance_id}")
            return instance_id
            
        # 查询APIG实例列表
        try:
            # 使用apig-instance服务客户端
            client = session.client('apig-instance')
            instances_request = ListInstancesV2Request()
            response = client.list_instances_v2(instances_request)
            
            if hasattr(response, 'instances') and response.instances:
                # 使用第一个运行中的实例
                for instance in response.instances:
                    if instance.status == 'Running':
                        instance_id = instance.id
                        log.info(f"使用查询到的第一个运行中实例ID: {instance_id}")
                        return instance_id
                
                # 如果没有找到运行中的实例，使用第一个实例
                if response.instances:
                    instance_id = response.instances[0].id
                    log.info(f"未找到运行中实例，使用第一个可用实例ID: {instance_id}")
                    return instance_id
        except Exception as e:
            log.error(f"查询APIG实例列表失败: {str(e)}", exc_info=True)
        
        # 如果仍然没有获取到，使用默认实例ID
        instance_id = session.get_apig_instance_id()
        log.info(f"未找到可用实例，使用配置的默认实例ID: {instance_id}")
        return instance_id
    
    def resources(self):
        """重写资源获取方法，确保正确设置instance_id"""
        session = local_session(self.session_factory)
        client = session.client('apig')
        
        # 获取实例ID
        instance_id = self.get_instance_id()
        
        # 修改：确保instance_id被正确设置
        if not instance_id:
            log.error("无法获取有效的APIG实例ID，无法继续查询API列表")
            return []
            
        log.debug(f"使用实例ID {instance_id} 查询API列表")
        
        # 创建请求对象
        try:
            request = ListApisV2Request()
            # 关键修复：设置instance_id
            request.instance_id = str(instance_id)
            request.limit = 100
            
            # 直接调用API
            response = client.list_apis_v2(request)
            
            # 处理响应
            resources = []
            if hasattr(response, 'apis'):
                for api in response.apis:
                    api_dict = {}
                    # 提取API属性，只获取基本数据类型的属性进行序列化
                    for attr in dir(api):
                        if (not attr.startswith('_') and not callable(getattr(api, attr))
                            and attr not in ['auth_opt', 'vpc_status', 'auth_opt_status']):
                            value = getattr(api, attr)
                            # 确保值是可序列化的基本类型
                            if isinstance(value, (str, int, float, bool, type(None))) or (
                                isinstance(value, (list, dict)) and not any(
                                    hasattr(item, '__dict__') for item in value) if isinstance(value, list) else True
                            ):
                                api_dict[attr] = value
                    
                    # 添加必要的字段
                    api_dict['id'] = api.id
                    api_dict['instance_id'] = instance_id
                    api_dict['tag_resource_type'] = self.resource_type.tag_resource_type
                    
                    resources.append(api_dict)
            
            log.info(f"成功从实例 {instance_id} 获取 {len(resources)} 个API资源")
            return resources
        except exceptions.ClientRequestException as e:
            log.error(f"查询API列表失败: {str(e)}", exc_info=True)
            return []
        
    def augment(self, resources):
        """增强资源信息，添加instance_id字段"""
        # 由于已经在resources方法中处理了资源增强，所以这里直接返回
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
            # 当资源中不含instance_id，使用manager获取
            if hasattr(self.manager, 'get_instance_id'):
                instance_id = self.manager.get_instance_id()
            else:
                # 如果没有get_instance_id方法，使用默认实例ID
                session = local_session(self.manager.session_factory)
                instance_id = session.get_apig_instance_id()
                log.info(f"未找到可用实例，使用配置的默认实例ID: {instance_id}")

        try:
            # 添加更多调试信息
            self.log.debug(f"删除API {api_id} (所属实例: {instance_id})")
            
            from huaweicloudsdkapig.v2 import DeleteApiV2Request
            
            # 确保instance_id是字符串类型
            request = DeleteApiV2Request(
                instance_id=str(instance_id),
                api_id=api_id
            )
            
            # 打印请求对象
            self.log.debug(f"请求对象: {request}")
            
            client.delete_api_v2(request)
            self.log.info(
                f"成功删除API: {resource.get('name')} (ID: {api_id})")
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"删除API失败 {resource.get('name')} (ID: {api_id}): {e}", exc_info=True)
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
    """

    schema = type_schema(
        'update',
        name={'type': 'string'},
        # 使用api_type替代type，避免与操作类型冲突
        api_type={'type': 'integer', 'enum': [1, 2]},
        req_protocol={'type': 'string', 'enum': [
            'HTTP', 'HTTPS', 'BOTH', 'GRPCS']},
        req_method={'type': 'string', 'enum': [
            'GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'PATCH', 'OPTIONS', 'ANY']},
        req_uri={'type': 'string'},
        auth_type={'type': 'string', 'enum': [
            'NONE', 'APP', 'IAM', 'AUTHORIZER']},
        backend_type={'type': 'string', 'enum': ['HTTP', 'FUNCTION', 'MOCK']},
        group_id={'type':'string'},
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
            'api_type': 'type',  # 使用api_type映射到type
            'req_protocol': 'req_protocol',
            'req_method': 'req_method',
            'req_uri': 'req_uri',
            'auth_type': 'auth_type',
            'backend_type': 'backend_type',
            'group_id':'group_id'
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
            # 当资源中不含instance_id，使用manager获取
            if hasattr(self.manager, 'get_instance_id'):
                instance_id = self.manager.get_instance_id()
            else:
                # 如果没有get_instance_id方法，使用默认实例ID
                session = local_session(self.manager.session_factory)
                instance_id = session.get_apig_instance_id()
                log.info(f"未找到可用实例，使用配置的默认实例ID: {instance_id}")

        try:
            # 添加更多调试信息
            self.log.debug(f"更新API {api_id} (所属实例: {instance_id})")
            
            from huaweicloudsdkapig.v2 import UpdateApiV2Request
            
            # 首先构建需要更新的参数
            update_body = self._build_update_body(resource)

            if not update_body:
                self.log.warning(
                    f"未提供更新参数，跳过API更新 {resource.get('name')} (ID: {api_id})")
                return

            # 创建更新请求，确保instance_id是字符串类型
            request = UpdateApiV2Request(
                instance_id=str(instance_id),
                api_id=api_id,
                body=update_body
            )
            
            # 打印请求对象
            self.log.debug(f"请求对象: {request}")

            # 发送请求
            response = client.update_api_v2(request)
            self.log.info(
                f"成功更新API: {resource.get('name')} (ID: {api_id})")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"更新API失败 {resource.get('name')} (ID: {api_id}): {e}", exc_info=True)
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
        """查询并获取API网关实例ID
        
        通过查询apig-instance接口获取可用的实例ID，优先使用运行中的实例
        如果未找到可用实例，则返回默认实例ID
        """
        session = local_session(self.session_factory)
        
        # 如果策略中已指定instance_id，则直接使用
        if hasattr(self, 'data') and isinstance(self.data, dict) and 'instance_id' in self.data:
            instance_id = self.data['instance_id']
            log.info(f"使用策略配置中的instance_id: {instance_id}")
            return instance_id
            
        # 查询APIG实例列表
        try:
            # 使用apig-instance服务客户端
            client = session.client('apig-instance')
            instances_request = ListInstancesV2Request()
            response = client.list_instances_v2(instances_request)
            
            if hasattr(response, 'instances') and response.instances:
                # 使用第一个运行中的实例
                for instance in response.instances:
                    if instance.status == 'Running':
                        instance_id = instance.id
                        log.info(f"使用查询到的第一个运行中实例ID: {instance_id}")
                        return instance_id
                
                # 如果没有找到运行中的实例，使用第一个实例
                if response.instances:
                    instance_id = response.instances[0].id
                    log.info(f"未找到运行中实例，使用第一个可用实例ID: {instance_id}")
                    return instance_id
        except Exception as e:
            log.error(f"查询APIG实例列表失败: {str(e)}", exc_info=True)
        
        # 如果仍然没有获取到，使用默认实例ID
        instance_id = session.get_apig_instance_id()
        log.info(f"未找到可用实例，使用配置的默认实例ID: {instance_id}")
        return instance_id
    
    def resources(self):
        """重写资源获取方法，确保正确设置instance_id"""
        session = local_session(self.session_factory)
        client = session.client('apig')
        
        # 获取实例ID
        instance_id = self.get_instance_id()
        
        # 修改：确保instance_id被正确设置
        if not instance_id:
            log.error("无法获取有效的APIG实例ID，无法继续查询环境列表")
            return []
            
        log.debug(f"使用实例ID {instance_id} 查询环境列表")
        
        # 创建请求对象
        try:
            request = ListEnvironmentsV2Request()
            # 关键修复：设置instance_id
            request.instance_id = str(instance_id)
            request.limit = 100
            
            # 直接调用API
            response = client.list_environments_v2(request)
            
            # 处理响应
            resources = []
            if hasattr(response, 'envs'):
                for env in response.envs:
                    env_dict = {}
                    # 提取环境属性，只获取基本数据类型的属性
                    for attr in dir(env):
                        if not attr.startswith('_') and not callable(getattr(env, attr)):
                            value = getattr(env, attr)
                            # 确保值是可序列化的基本类型
                            if isinstance(value, (str, int, float, bool, type(None))) or (
                                isinstance(value, (list, dict)) and not any(
                                    hasattr(item, '__dict__') for item in value) if isinstance(value, list) else True
                            ):
                                env_dict[attr] = value
                    
                    # 添加必要的字段
                    env_dict['id'] = env.id
                    env_dict['instance_id'] = instance_id
                    env_dict['tag_resource_type'] = self.resource_type.tag_resource_type
                    
                    resources.append(env_dict)
            
            log.info(f"成功从实例 {instance_id} 获取 {len(resources)} 个环境资源")
            return resources
        except exceptions.ClientRequestException as e:
            log.error(f"查询环境列表失败: {str(e)}", exc_info=True)
            return []
        
    def augment(self, resources):
        """增强资源信息，添加instance_id字段"""
        # 由于已经在resources方法中处理了资源增强，所以这里直接返回
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
            # 当资源中不含instance_id，使用manager获取
            if hasattr(self.manager, 'get_instance_id'):
                instance_id = self.manager.get_instance_id()
            else:
                # 如果没有get_instance_id方法，使用默认实例ID
                session = local_session(self.manager.session_factory)
                instance_id = session.get_apig_instance_id()
                log.info(f"未找到可用实例，使用配置的默认实例ID: {instance_id}")

        try:
            # 添加更多调试信息
            self.log.debug(f"更新环境 {env_id} (所属实例: {instance_id})")
            
            # 准备更新参数
            update_info = {}
            
            if 'name' in self.data:
                update_info['name'] = self.data['name']
            if 'description' in self.data:
                update_info['remark'] = self.data['description']
            
            # 添加其他可能的参数
            if 'enable_metrics' in self.data:
                update_info['enable_metrics'] = self.data['enable_metrics']
            if 'is_waf_enabled' in self.data:
                update_info['is_waf_enabled'] = self.data['is_waf_enabled']
            if 'is_client_certificate_required' in self.data:
                update_info['is_client_certificate_required'] = self.data['is_client_certificate_required']

            if not update_info:
                self.log.warning(
                    f"未提供更新参数，跳过环境更新 {resource.get('name')} (ID: {env_id})")
                return

            # 创建更新请求，确保instance_id是字符串类型
            request = UpdateEnvironmentV2Request(
                instance_id=str(instance_id),
                env_id=env_id,
                body=update_info
            )
            
            # 打印请求对象
            self.log.debug(f"请求对象: {request}")

            # 发送请求
            response = client.update_environment_v2(request)
            self.log.info(
                f"成功更新环境: {resource.get('name')} (ID: {env_id})")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"更新环境失败 {resource.get('name')} (ID: {env_id}): {e}", exc_info=True)
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
            # 当资源中不含instance_id，使用manager获取
            if hasattr(self.manager, 'get_instance_id'):
                instance_id = self.manager.get_instance_id()
            else:
                # 如果没有get_instance_id方法，使用默认实例ID
                session = local_session(self.manager.session_factory)
                instance_id = session.get_apig_instance_id()
                log.info(f"未找到可用实例，使用配置的默认实例ID: {instance_id}")

        try:
            # 添加更多调试信息
            self.log.debug(f"删除环境 {env_id} (所属实例: {instance_id})")
            
            # 确保instance_id是字符串类型
            request = DeleteEnvironmentV2Request(
                instance_id=str(instance_id),
                env_id=env_id
            )
            
            # 打印请求对象
            self.log.debug(f"请求对象: {request}")
            
            client.delete_environment_v2(request)
            self.log.info(
                f"成功删除环境: {resource.get('name')} (ID: {env_id})")
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"删除环境失败 {resource.get('name')} (ID: {env_id}): {e}", exc_info=True)
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
        """查询并获取API网关实例ID
        
        通过查询apig-instance接口获取可用的实例ID，优先使用运行中的实例
        如果未找到可用实例，则返回默认实例ID
        """
        session = local_session(self.session_factory)
        
        # 如果策略中已指定instance_id，则直接使用
        if hasattr(self, 'data') and isinstance(self.data, dict) and 'instance_id' in self.data:
            instance_id = self.data['instance_id']
            log.info(f"使用策略配置中的instance_id: {instance_id}")
            return instance_id
            
        # 查询APIG实例列表
        try:
            # 使用apig-instance服务客户端
            client = session.client('apig-instance')
            instances_request = ListInstancesV2Request()
            response = client.list_instances_v2(instances_request)
            
            if hasattr(response, 'instances') and response.instances:
                # 使用第一个运行中的实例
                for instance in response.instances:
                    if instance.status == 'Running':
                        instance_id = instance.id
                        log.info(f"使用查询到的第一个运行中实例ID: {instance_id}")
                        return instance_id
                
                # 如果没有找到运行中的实例，使用第一个实例
                if response.instances:
                    instance_id = response.instances[0].id
                    log.info(f"未找到运行中实例，使用第一个可用实例ID: {instance_id}")
                    return instance_id
        except Exception as e:
            log.error(f"查询APIG实例列表失败: {str(e)}", exc_info=True)
        
        # 如果仍然没有获取到，使用默认实例ID
        instance_id = session.get_apig_instance_id()
        log.info(f"未找到可用实例，使用配置的默认实例ID: {instance_id}")
        return instance_id
    
    def resources(self):
        """重写资源获取方法，确保正确设置instance_id"""
        session = local_session(self.session_factory)
        client = session.client('apig')
        
        # 获取实例ID
        instance_id = self.get_instance_id()
        
        # 修改：确保instance_id被正确设置
        if not instance_id:
            log.error("无法获取有效的APIG实例ID，无法继续查询API组列表")
            return []
            
        log.debug(f"使用实例ID {instance_id} 查询API组列表")
        
        # 创建请求对象
        try:
            request = ListApiGroupsV2Request()
            # 关键修复：设置instance_id
            request.instance_id = str(instance_id)
            request.limit = 100
            
            # 直接调用API
            response = client.list_api_groups_v2(request)
            
            # 处理响应
            resources = []
            if hasattr(response, 'groups'):
                for group in response.groups:
                    group_dict = {}
                    # 提取API组属性，只获取基本数据类型的属性
                    for attr in dir(group):
                        if not attr.startswith('_') and not callable(getattr(group, attr)):
                            value = getattr(group, attr)
                            # 确保值是可序列化的基本类型
                            if isinstance(value, (str, int, float, bool, type(None))) or (
                                isinstance(value, (list, dict)) and not any(
                                    hasattr(item, '__dict__') for item in value) if isinstance(value, list) else True
                            ):
                                group_dict[attr] = value
                    
                    # 添加必要的字段
                    group_dict['id'] = group.id
                    group_dict['instance_id'] = instance_id
                    group_dict['tag_resource_type'] = self.resource_type.tag_resource_type
                    
                    resources.append(group_dict)
            
            log.info(f"成功从实例 {instance_id} 获取 {len(resources)} 个API组资源")
            return resources
        except exceptions.ClientRequestException as e:
            log.error(f"查询API组列表失败: {str(e)}", exc_info=True)
            return []
        
    def augment(self, resources):
        """增强资源信息，添加instance_id字段"""
        # 由于已经在resources方法中处理了资源增强，所以这里直接返回
        return resources

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
                f"未指定domain_id，无法执行更新域名安全策略操作，API组ID: {group_id}")
            return

        if not instance_id:
            # 当资源中不含instance_id，使用manager获取
            if hasattr(self.manager, 'get_instance_id'):
                instance_id = self.manager.get_instance_id()
            else:
                # 如果没有get_instance_id方法，使用默认实例ID
                session = local_session(self.manager.session_factory)
                instance_id = session.get_apig_instance_id()
                log.info(f"未找到可用实例，使用配置的默认实例ID: {instance_id}")

        try:
            # 添加更多调试信息
            self.log.debug(f"更新域名安全策略 域名ID: {domain_id}, API组ID: {group_id} (所属实例: {instance_id})")
            
            # 准备更新参数
            update_info = {}
            
            if 'min_ssl_version' in self.data:
                update_info['min_ssl_version'] = self.data['min_ssl_version']
            
            if 'ssl_id' in self.data:
                update_info['ssl_id'] = self.data['ssl_id']
                update_info['ssl_name'] = '绑定到该域名的证书'
                
            if not update_info:
                self.log.warning(
                    f"未提供更新参数，跳过域名安全策略更新，域名ID: {domain_id}, API组ID: {group_id}")
                return

            # 创建更新请求，确保instance_id是字符串类型
            request = UpdateDomainV2Request(
                instance_id=str(instance_id),
                domain_id=domain_id,
                body=update_info
            )
            
            # 打印请求对象
            self.log.debug(f"请求对象: {request}")

            # 发送请求
            response = client.update_domain_v2(request)
            self.log.info(
                f"成功更新域名安全策略: API组 {resource.get('name')} (ID: {group_id}), 域名ID: {domain_id}")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"更新域名安全策略失败: API组 {resource.get('name')} (ID: {group_id}), 域名ID: {domain_id}: {e}", exc_info=True)
            raise
