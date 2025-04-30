# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from c7n.filters import Filter, ValueFilter, AgeFilter
from c7n.filters.core import OPERATORS, type_schema
from c7n.utils import local_session
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

from dateutil.parser import parse
from huaweicloudsdkrds.v3 import (
    ListInstancesRequest, SetSecurityGroupRequest, SwitchSslRequest,
    UpdatePortRequest, CustomerModifyAutoEnlargePolicyReq, AttachEipRequest,
    UpgradeDbVersionRequest, CustomerUpgradeDatabaseVersionReq,
    SetAuditlogPolicyRequest, ShowAuditlogPolicyRequest, ListDatastoresRequest,
    ShowAutoEnlargePolicyRequest, ShowBackupPolicyRequest, SetBackupPolicyRequest,
    SetBackupPolicyRequestBody, ShowInstanceConfigurationRequest, 
    UpdateInstanceConfigurationRequest, UpdateInstanceConfigurationRequestBody
)
from huaweicloudsdkcore.exceptions import exceptions

log = logging.getLogger("custodian.huaweicloud.resources.rds")


@resources.register('rds')
class RDS(QueryResourceManager):
    """华为云RDS资源管理器

    用于管理华为云关系型数据库服务中的实例。

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-instance-list
            resource: huaweicloud.rds
            filters:
              - type: value
                key: status
                value: ACTIVE
    """
    class resource_type(TypeInfo):
        service = 'rds'
        enum_spec = ('list_instances', 'instances', 'offset')
        id = 'id'
        name = 'name'
        filter_name = 'id'
        filter_type = 'scalar'
        date = 'created'
        taggable = True
        tag_resource_type = 'instances'


@RDS.filter_registry.register('rds-list')
class RDSListFilter(Filter):
    """过滤特定实例ID的RDS实例

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-list-filter
            resource: huaweicloud.rds
            filters:
              - type: rds-list
                ids:
                  - 5fc738f6-67da-4f1f-a78b-f9d61588fdee
                  - 76e4bc08-2e5b-4ccc-b26a-e6484f022365
    """
    schema = type_schema(
        'rds-list',
        ids={'type': 'array', 'items': {'type': 'string'}}
    )

    def process(self, resources, event=None):
        ids = self.data.get('ids', [])
        if not ids:
            return resources
        return [r for r in resources if r['id'] in ids]


@RDS.filter_registry.register('disk-auto-expansion')
class DiskAutoExpansionFilter(Filter):
    """过滤存储空间自动扩容状态的RDS实例

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-disk-auto-expansion-disabled
            resource: huaweicloud.rds
            filters:
              - type: disk-auto-expansion
                enabled: false
    """
    schema = type_schema(
        'disk-auto-expansion',
        enabled={'type': 'boolean'}
    )

    def process(self, resources, event=None):
        enabled = self.data.get('enabled', True)
        client = local_session(self.manager.session_factory).client("rds")
        matched_resources = []

        for resource in resources:
            instance_id = resource['id']
            try:
                # 查询实例存储空间自动扩容策略
                # API文档: https://support.huaweicloud.com/api-rds/rds_05_0027.html
                # GET /v3/{project_id}/instances/{instance_id}/disk-auto-expansion
                # 直接调用API路径，不使用SDK中的预定义请求对象

                request = ShowAutoEnlargePolicyRequest(instance_id=instance_id)
                response = client.show_auto_enlarge_policy(request)
                
                # 根据API响应判断是否启用了自动扩容
                auto_expansion_enabled = response.switch_option
                
                if auto_expansion_enabled == enabled:
                    matched_resources.append(resource)
            except Exception as e:
                print(e)
                self.log.error(f"获取RDS实例 {resource['name']} (ID: {instance_id}) 的自动扩容策略失败: {e}")
                # 如果无法获取自动扩容策略，假设其未开启
                if not enabled:
                    matched_resources.append(resource)
                
        return matched_resources


@RDS.filter_registry.register('database-version')
class DatabaseVersionFilter(Filter):
    """过滤数据库版本的RDS实例

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-old-version
            resource: huaweicloud.rds
            filters:
              - type: database-version
                version: 5.7
                op: lt
                database_name: mysql  # 可选，指定数据库引擎类型
    """
    schema = type_schema(
        'database-version',
        required=['version'],
        version={'type': 'string'},
        op={'enum': list(OPERATORS.keys()), 'default': 'eq'},
        database_name={'enum': ['mysql', 'postgresql', 'sqlserver'], 'default': 'mysql'}
    )

    def process(self, resources, event=None):
        client = local_session(self.manager.session_factory).client("rds")
        version = self.data.get('version')
        op_name = self.data.get('op', 'eq')
        op = OPERATORS.get(op_name)
        database_name = self.data.get('database_name', 'mysql').lower()
        
        # 获取可用的数据库版本列表
        try:
            # 调用API获取指定数据库引擎可用的版本列表
            # API文档: https://support.huaweicloud.com/api-rds/rds_06_0001.html
            # GET /v3/{project_id}/datastores/{database_name}
            request = ListDatastoresRequest()
            request.database_name = database_name
            response = client.list_datastores(request)
            
            available_versions = {}
            for datastore in response.data_stores:
                available_versions[datastore.name] = datastore.id
                
            self.log.debug(f"获取到 {database_name} 引擎的可用版本: {available_versions}")
        except Exception as e:
            self.log.error(f"获取数据库引擎 {database_name} 的版本列表失败: {e}")
            # 如果无法获取版本列表，则回退到原始的过滤逻辑
            matched = []
            for resource in resources:
                datastore = resource.get('datastore', {})
                resource_version = datastore.get('name', '')
                if op(resource_version, version):
                    matched.append(resource)
            return matched
            
        # 使用获取的版本信息过滤资源
        matched = []
        for resource in resources:
            datastore = resource.get('datastore', {})
            resource_version = datastore.get('version', '')
            
            # 检查资源的数据库引擎类型是否与请求的一致
            resource_type = datastore.get('type', '').lower()
            if resource_type != database_name:
                continue
                
            if op(resource_version, version):
                matched.append(resource)
                
        return matched


@RDS.filter_registry.register('eip')
class EIPFilter(Filter):
    """过滤是否绑定弹性公网IP的RDS实例

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-with-eip
            resource: huaweicloud.rds
            filters:
              - type: eip
                exists: true
    """
    schema = type_schema(
        'eip',
        exists={'type': 'boolean'}
    )

    def process(self, resources, event=None):
        exists = self.data.get('exists', True)
        matched = []
        for resource in resources:
            has_eip = resource.get('public_ips') is not None and len(resource.get('public_ips', [])) > 0
            if has_eip == exists:
                matched.append(resource)
        return matched


@RDS.filter_registry.register('audit-log-disabled')
class AuditLogDisabledFilter(Filter):
    """过滤未开启审计日志的RDS实例

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-audit-log-disabled
            resource: huaweicloud.rds
            filters:
              - type: audit-log-disabled
    """
    schema = type_schema('audit-log-disabled')

    def process(self, resources, event=None):
        client = local_session(self.manager.session_factory).client("rds")
        matched_resources = []

        for resource in resources:
            instance_id = resource['id']
            try:
                request = ShowAuditlogPolicyRequest()
                request.instance_id = instance_id
                response = client.show_auditlog_policy(request)
                
                # keep_days为0表示审计日志策略关闭
                if response.keep_days == 0:
                    matched_resources.append(resource)
            except Exception as e:
                self.log.error(f"获取RDS实例 {resource['name']} (ID: {instance_id}) 的审计日志策略失败: {e}")
                # 如果无法获取审计日志策略，假设其未开启
                matched_resources.append(resource)
                
        return matched_resources


@RDS.filter_registry.register('backup-policy-disabled')
class BackupPolicyDisabledFilter(Filter):
    """过滤未开启自动备份策略的RDS实例

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-backup-policy-disabled
            resource: huaweicloud.rds
            filters:
              - type: backup-policy-disabled
    """
    schema = type_schema('backup-policy-disabled')

    def process(self, resources, event=None):
        client = local_session(self.manager.session_factory).client("rds")
        matched_resources = []

        for resource in resources:
            instance_id = resource['id']
            try:
                # 查询实例备份策略
                # API文档: https://support.huaweicloud.com/api-rds/rds_09_0003.html
                # GET /v3/{project_id}/instances/{instance_id}/backups/policy
                request = ShowBackupPolicyRequest()
                request.instance_id = instance_id
                response = client.show_backup_policy(request)
                
                # 检查是否启用了自动备份
                # 如果keep_days为0或者backup_type为空，则认为未开启自动备份
                keep_days = response.backup_policy.keep_days
                backup_type = getattr(response.backup_policy, 'backup_type', '')
                
                if keep_days == 0 or not backup_type:
                    matched_resources.append(resource)
            except Exception as e:
                self.log.error(f"获取RDS实例 {resource['name']} (ID: {instance_id}) 的备份策略失败: {e}")
                # 如果无法获取备份策略，假设其未开启
                matched_resources.append(resource)
                
        return matched_resources


@RDS.filter_registry.register('instance-parameter')
class InstanceParameterFilter(Filter):
    """过滤特定参数配置的RDS实例

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-max-connections-too-low
            resource: huaweicloud.rds
            filters:
              - type: instance-parameter
                name: max_connections
                value: 500
                op: lt
    """
    schema = type_schema(
        'instance-parameter',
        required=['name'],
        name={'type': 'string'},
        value={'oneOf': [
            {'type': 'string'},
            {'type': 'integer'},
            {'type': 'boolean'}
        ]},
        op={'enum': list(OPERATORS.keys()), 'default': 'eq'}
    )

    def process(self, resources, event=None):
        client = local_session(self.manager.session_factory).client("rds")
        param_name = self.data.get('name')
        param_value = self.data.get('value')
        op_name = self.data.get('op', 'eq')
        op = OPERATORS.get(op_name)
        
        matched_resources = []
        
        for resource in resources:
            instance_id = resource['id']
            try:
                # 查询实例参数模板
                # API文档: https://support.huaweicloud.com/api-rds/rds_09_0306.html
                # GET /v3/{project_id}/instances/{instance_id}/configurations
                request = ShowInstanceConfigurationRequest()
                request.instance_id = instance_id
                response = client.show_instance_configuration(request)
                
                # 在参数列表中查找目标参数
                found = False
                for param in response.configuration_parameters:
                    if param.name == param_name:
                        found = True
                        # 根据参数类型进行值的转换和比较
                        current_value = param.value
                        if param.type == 'integer':
                            current_value = int(current_value)
                        elif param.type == 'boolean':
                            current_value = (current_value.lower() == 'true')
                        
                        # 对参数值应用操作符进行比较
                        if op(current_value, param_value):
                            matched_resources.append(resource)
                        break
                
                if not found:
                    self.log.debug(f"RDS实例 {resource['name']} (ID: {instance_id}) 没有参数 {param_name}")
            except Exception as e:
                self.log.error(f"获取RDS实例 {resource['name']} (ID: {instance_id}) 的参数模板失败: {e}")
                
        return matched_resources


@RDS.action_registry.register('set-security-group')
class SetSecurityGroupAction(HuaweiCloudBaseAction):
    """修改RDS实例安全组

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-set-security-group
            resource: huaweicloud.rds
            filters:
              - type: value
                key: name
                value: test-mysql
            actions:
              - type: set-security-group
                security_group_id: 438d0abe-0616-47bc-9573-ee1ed51c7e44
    """
    schema = type_schema(
        'set-security-group',
        required=['security_group_id'],
        security_group_id={'type': 'string'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        security_group_id = self.data['security_group_id']
        
        try:
            request = SetSecurityGroupRequest()
            request.instance_id = instance_id
            request.security_group_id = security_group_id
            response = client.set_security_group(request)
            self.log.info(f"成功为RDS实例 {resource['name']} (ID: {instance_id}) 设置安全组")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(f"无法为RDS实例 {resource['name']} (ID: {instance_id}) 设置安全组: {e}")
            raise


@RDS.action_registry.register('switch-ssl')
class SwitchSSLAction(HuaweiCloudBaseAction):
    """开启或关闭RDS实例的SSL加密

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-enable-ssl
            resource: huaweicloud.rds
            filters:
              - type: ssl-instance
                enabled: false
            actions:
              - type: switch-ssl
                ssl_enable: true
    """
    schema = type_schema(
        'switch-ssl',
        required=['ssl_enable'],
        ssl_enable={'type': 'boolean'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        ssl_enable = self.data['ssl_enable']
        
        try:
            request = SwitchSslRequest()
            request.instance_id = instance_id
            request.ssl_option = "on" if ssl_enable else "off"
            response = client.switch_ssl(request)
            self.log.info(f"成功为RDS实例 {resource['name']} (ID: {instance_id}) {'启用' if ssl_enable else '禁用'}SSL加密")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(f"无法为RDS实例 {resource['name']} (ID: {instance_id}) {'启用' if ssl_enable else '禁用'}SSL加密: {e}")
            raise


@RDS.action_registry.register('update-port')
class UpdatePortAction(HuaweiCloudBaseAction):
    """修改RDS实例的数据库端口

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-update-port
            resource: huaweicloud.rds
            filters:
              - type: database-port
                value: 3306
            actions:
              - type: update-port
                port: 3307
    """
    schema = type_schema(
        'update-port',
        required=['port'],
        port={'type': 'integer', 'minimum': 1, 'maximum': 65535}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        port = self.data['port']
        
        try:
            request = UpdatePortRequest()
            request.instance_id = instance_id
            request.port = port
            response = client.update_port(request)
            self.log.info(f"成功为RDS实例 {resource['name']} (ID: {instance_id}) 修改端口为 {port}")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(f"无法为RDS实例 {resource['name']} (ID: {instance_id}) 修改端口: {e}")
            raise


@RDS.action_registry.register('set-auto-enlarge-policy')
class SetAutoEnlargePolicyAction(HuaweiCloudBaseAction):
    """设置RDS实例的存储空间自动扩容策略

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-enable-auto-enlarge
            resource: huaweicloud.rds
            filters:
              - type: disk-auto-expansion
                enabled: false
            actions:
              - type: set-auto-enlarge-policy
                switch_option: true
                limit_size: 4000
                trigger_threshold: 10
                step_percent: 20
    """
    schema = type_schema(
        'set-auto-enlarge-policy',
        required=['switch_option'],
        switch_option={'type': 'boolean'},
        limit_size={'type': 'integer', 'minimum': 40, 'maximum': 4000},
        trigger_threshold={'type': 'integer', 'minimum': 5, 'maximum': 15},
        step_percent={'type': 'integer', 'minimum': 5, 'maximum': 100}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        switch_option = self.data['switch_option']
        
        try:
            # 通过API直接构建请求
            # API文档: https://support.huaweicloud.com/api-rds/rds_05_0028.html
            # POST /v3/{project_id}/instances/{instance_id}/disk-auto-expansion
            body = {
                "switch_option": switch_option
            }
            
            if switch_option:
                # 当开启自动扩容时，需要设置相关参数
                if 'limit_size' in self.data:
                    body["limit_size"] = self.data['limit_size']
                if 'trigger_threshold' in self.data:
                    body["trigger_threshold"] = self.data['trigger_threshold']
                if 'step_percent' in self.data:
                    body["step_percent"] = self.data['step_percent']
            
            # 由于SDK中可能没有直接的请求类，使用客户端直接调用API
            response = client.set_disk_auto_expansion(instance_id, body)
            self.log.info(f"成功为RDS实例 {resource['name']} (ID: {instance_id}) {'启用' if switch_option else '禁用'}自动扩容策略")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(f"无法为RDS实例 {resource['name']} (ID: {instance_id}) 设置自动扩容策略: {e}")
            raise


@RDS.action_registry.register('attach-eip')
class AttachEIPAction(HuaweiCloudBaseAction):
    """绑定或解绑RDS实例的弹性公网IP

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-bind-eip
            resource: huaweicloud.rds
            filters:
              - type: eip
                exists: false
            actions:
              - type: attach-eip
                public_ip: 122.112.244.240
                bind_type: bind
    """
    schema = type_schema(
        'attach-eip',
        required=['bind_type'],
        bind_type={'enum': ['bind', 'unbind']},
        public_ip={'type': 'string'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        bind_type = self.data['bind_type']
        public_ip = self.data.get('public_ip')
        
        if bind_type == 'bind' and not public_ip:
            self.log.error(f"绑定弹性公网IP时必须提供 public_ip 参数")
            return
            
        try:
            request = AttachEipRequest()
            request.instance_id = instance_id
            request.bind_type = bind_type
            if bind_type == 'bind':
                request.public_ip = public_ip
            
            response = client.attach_eip(request)
            self.log.info(f"成功为RDS实例 {resource['name']} (ID: {instance_id}) {'绑定' if bind_type == 'bind' else '解绑'}弹性公网IP")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(f"无法为RDS实例 {resource['name']} (ID: {instance_id}) {'绑定' if bind_type == 'bind' else '解绑'}弹性公网IP: {e}")
            raise


@RDS.action_registry.register('upgrade-db-version')
class UpgradeDBVersionAction(HuaweiCloudBaseAction):
    """对RDS实例进行小版本升级

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-upgrade-minor-version
            resource: huaweicloud.rds
            filters:
              - type: database-version
                version: 5.7.37
                op: lt
            actions:
              - type: upgrade-db-version
                is_immediately: false
                target_version: 5.7.41  # 可选参数，指定目标版本
                set_backup: true  # 可选参数，是否设置自动备份
    """
    schema = type_schema(
        'upgrade-db-version',
        is_immediately={'type': 'boolean'},
        target_version={'type': 'string'},
        set_backup={'type': 'boolean'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        is_immediately = self.data.get('is_immediately', False)
        target_version = self.data.get('target_version')
        set_backup = self.data.get('set_backup', False)
        
        try:
            # 构建版本升级请求
            # API文档: https://support.huaweicloud.com/api-rds/rds_05_0041.html
            # POST /v3/{project_id}/instances/{instance_id}/action
            request = UpgradeDbVersionRequest()
            request.instance_id = instance_id
            
            # 设置升级参数
            upgrade_req = CustomerUpgradeDatabaseVersionReq()
            upgrade_req.is_immediately = is_immediately
            
            # 如果指定了目标版本，则设置目标版本
            if target_version:
                # 先获取可用版本列表
                try:
                    datastore = resource.get('datastore', {})
                    database_name = datastore.get('type', 'mysql').lower()
                    
                    # 获取可用版本列表
                    datastores_request = ListDatastoresRequest()
                    datastores_request.database_name = database_name
                    datastores_response = client.list_datastores(datastores_request)
                    
                    # 验证目标版本是否有效
                    valid_version = False
                    for datastore_info in datastores_response.data_stores:
                        if datastore_info.name == target_version:
                            upgrade_req.target_version = datastore_info.id
                            self.log.info(f"找到目标版本 {target_version}, ID: {datastore_info.id}")
                            valid_version = True
                            break
                            
                    if not valid_version:
                        self.log.warning(f"找不到指定的目标版本 {target_version}，将使用默认版本升级")
                except Exception as e:
                    self.log.error(f"获取可用版本列表失败: {e}")
            
            # 是否设置备份
            if set_backup:
                upgrade_req.with_backup = True
            
            # 设置请求体
            request.body = upgrade_req
            
            # 执行升级请求
            response = client.upgrade_db_version(request)
            self.log.info(f"成功为RDS实例 {resource['name']} (ID: {instance_id}) 提交数据库版本升级请求")
            
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(f"无法为RDS实例 {resource['name']} (ID: {instance_id}) 升级数据库版本: {e}")
            raise


@RDS.action_registry.register('set-audit-log-policy')
class SetAuditLogPolicyAction(HuaweiCloudBaseAction):
    """设置RDS实例的审计日志策略

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-enable-audit-log
            resource: huaweicloud.rds
            filters:
              - type: audit-log-disabled
            actions:
              - type: set-audit-log-policy
                keep_days: 7
                audit_types:
                  - SELECT
                  - INSERT
                  - UPDATE
                  - DELETE
    """
    schema = type_schema(
        'set-audit-log-policy',
        required=['keep_days'],
        keep_days={'type': 'integer', 'minimum': 0, 'maximum': 732},
        reserve_auditlogs={'type': 'boolean'},
        audit_types={'type': 'array', 'items': {'type': 'string'}}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        keep_days = self.data['keep_days']
        reserve_auditlogs = self.data.get('reserve_auditlogs', True)
        audit_types = self.data.get('audit_types', [])
        
        try:
            request = SetAuditlogPolicyRequest()
            request.instance_id = instance_id
            request.keep_days = keep_days
            
            if keep_days == 0:
                request.reserve_auditlogs = reserve_auditlogs
            
            if audit_types and keep_days > 0:
                request.audit_types = audit_types
            
            response = client.set_auditlog_policy(request)
            self.log.info(f"成功为RDS实例 {resource['name']} (ID: {instance_id}) {'启用' if keep_days > 0 else '禁用'}审计日志策略")
            return response
        except Exception as e:
            self.log.error(f"无法为RDS实例 {resource['name']} (ID: {instance_id}) 设置审计日志策略: {e}")
            raise


@RDS.action_registry.register('set-backup-policy')
class SetBackupPolicyAction(HuaweiCloudBaseAction):
    """设置RDS实例的自动备份策略

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-enable-backup
            resource: huaweicloud.rds
            filters:
              - type: backup-policy-disabled
            actions:
              - type: set-backup-policy
                keep_days: 7
                start_time: "01:00-02:00"
                period: "1,2,3,4,5,6,7"
                backup_type: "auto"
    """
    schema = type_schema(
        'set-backup-policy',
        required=['keep_days', 'start_time', 'period'],
        keep_days={'type': 'integer', 'minimum': 1, 'maximum': 732},
        start_time={'type': 'string'},
        period={'type': 'string'},
        backup_type={'enum': ['auto', 'manual'], 'default': 'auto'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        keep_days = self.data['keep_days']
        start_time = self.data['start_time']
        period = self.data['period']
        backup_type = self.data.get('backup_type', 'auto')
        
        try:
            # 设置备份策略
            # API文档: https://support.huaweicloud.com/api-rds/rds_09_0002.html
            # PUT /v3/{project_id}/instances/{instance_id}/backups/policy
            request = SetBackupPolicyRequest()
            request.instance_id = instance_id
            
            # 构建请求体
            request_body = SetBackupPolicyRequestBody(
                keep_days=keep_days,
                start_time=start_time,
                period=period,
                backup_type=backup_type
            )
            request.body = request_body
            
            response = client.set_backup_policy(request)
            self.log.info(f"成功为RDS实例 {resource['name']} (ID: {instance_id}) 设置自动备份策略")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(f"无法为RDS实例 {resource['name']} (ID: {instance_id}) 设置自动备份策略: {e}")
            raise


@RDS.action_registry.register('update-instance-parameter')
class UpdateInstanceParameterAction(HuaweiCloudBaseAction):
    """修改RDS实例的参数配置

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-update-max-connections
            resource: huaweicloud.rds
            filters:
              - type: instance-parameter
                name: max_connections
                value: 500
                op: lt
            actions:
              - type: update-instance-parameter
                parameters:
                  - name: max_connections
                    value: "1000"
    """
    schema = type_schema(
        'update-instance-parameter',
        required=['parameters'],
        parameters={'type': 'array', 'items': {
            'type': 'object',
            'properties': {
                'name': {'type': 'string'},
                'value': {'type': 'string'}
            },
            'required': ['name', 'value']
        }}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        parameters = self.data['parameters']
        
        try:
            # 修改实例参数
            # API文档: https://support.huaweicloud.com/api-rds/rds_09_0303.html
            # PUT /v3/{project_id}/instances/{instance_id}/configurations
            request = UpdateInstanceConfigurationRequest()
            request.instance_id = instance_id
            
            # 构建请求体
            request_body = UpdateInstanceConfigurationRequestBody(
                values={}
            )
            
            for param in parameters:
                request_body.values[param['name']] = param['value']
            
            request.body = request_body
            
            response = client.update_instance_configuration(request)
            self.log.info(f"成功为RDS实例 {resource['name']} (ID: {instance_id}) 修改参数配置")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(f"无法为RDS实例 {resource['name']} (ID: {instance_id}) 修改参数配置: {e}")
            raise
