# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from c7n.filters import Filter
from c7n.filters.core import OPERATORS, type_schema
from c7n.utils import local_session
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

from huaweicloudsdkrds.v3 import (
    SetSecurityGroupRequest, SwitchSslRequest,
    UpdatePortRequest, CustomerModifyAutoEnlargePolicyReq, AttachEipRequest,
    CustomerUpgradeDatabaseVersionReq,
    SetAuditlogPolicyRequest, ShowAuditlogPolicyRequest, ListDatastoresRequest,
    ShowAutoEnlargePolicyRequest, ShowBackupPolicyRequest, SetBackupPolicyRequest,
    SetBackupPolicyRequestBody, ShowInstanceConfigurationRequest,
    UpdateInstanceConfigurationRequest, UpdateInstanceConfigurationRequestBody, BackupPolicy,
    SetAutoEnlargePolicyRequest, UpgradeDbVersionNewRequest,
    ListPostgresqlHbaInfoRequest, ModifyPostgresqlHbaConfRequest,
    UpdateTdeStatusRequest
)
from huaweicloudsdkcore.exceptions import exceptions

log = logging.getLogger("custodian.huaweicloud.resources.rds")


# Define a local TagEntity class to simplify tag operations
class TagEntity:
    """Simple tag structure to represent key-value pairs"""

    def __init__(self, key, value=None):
        """
        Initialize a tag entity
        :param key: Tag key (required)
        :param value: Tag value (optional)
        """
        self.key = key
        self.value = value


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
        tag_resource_type = 'rds'


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
                self.log.error(
                    f"获取RDS实例 {resource['name']} (ID: {instance_id}) 的自动扩容策略失败: {e}")
                # 如果无法获取自动扩容策略，假设其未开启
                if not enabled:
                    matched_resources.append(resource)
        return matched_resources


@RDS.filter_registry.register('database-version')
class DatabaseVersionFilter(Filter):
    """过滤不是最新小版本的RDS实例

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-outdated-version
            resource: huaweicloud.rds
            filters:
              - type: database-version
                database_name: mysql  # 可选，指定数据库引擎类型
    """
    schema = type_schema(
        'database-version',
        database_name={'enum': ['mysql', 'postgresql', 'sqlserver'], 'default': 'mysql'}
    )

    def process(self, resources, event=None):
        client = local_session(self.manager.session_factory).client("rds")
        database_name = self.data.get('database_name', 'mysql').lower()

        # 获取所有数据库版本的最新小版本信息
        try:
            # 调用API获取指定数据库引擎可用的版本列表
            # API文档: https://support.huaweicloud.com/api-rds/rds_06_0001.html
            # GET /v3/{project_id}/datastores/{database_name}
            request = ListDatastoresRequest()
            request.database_name = database_name
            response = client.list_datastores(request)

            # 存储每个主版本的最新小版本号
            latest_versions = {}
            for datastore in response.data_stores:
                version_parts = datastore.name.split('.')
                if len(version_parts) >= 2:
                    # 提取主版本号，如 5.7, 8.0 等
                    major_version = '.'.join(version_parts[:2])

                    # 如果该主版本尚未记录或当前版本更新，则更新记录
                    if major_version not in latest_versions or self._compare_versions(
                            datastore.name, latest_versions[major_version]) > 0:
                        latest_versions[major_version] = datastore.name

            self.log.debug(f"获取到 {database_name} 引擎各主版本的最新小版本: {latest_versions}")
        except Exception as e:
            self.log.error(f"获取数据库引擎 {database_name} 的版本列表失败: {e}")
            return []

        # 筛选出不是最新小版本的实例
        outdated_resources = []
        for resource in resources:
            datastore = resource.get('datastore', {})
            resource_type = datastore.get('type', '').lower()

            # 跳过不匹配的数据库类型
            if resource_type != database_name:
                continue

            # 从完整版本号中获取主版本号
            complete_version = datastore.get('complete_version', datastore.get('version', ''))
            if not complete_version:
                continue

            version_parts = complete_version.split('.')
            if len(version_parts) < 2:
                continue

            # 提取主版本号
            major_version = '.'.join(version_parts[:2])

            # 截取前三部分作为比较版本号（如8.0.28.231003 -> 8.0.28）
            instance_version_to_compare = '.'.join(version_parts[:3]) \
                if len(version_parts) >= 3 else complete_version

            # 检查主版本是否有对应的最新小版本
            if major_version in latest_versions:
                latest_version = latest_versions[major_version]
                latest_version_parts = latest_version.split('.')
                latest_version_to_compare = '.'.join(latest_version_parts[:3]) \
                    if len(latest_version_parts) >= 3 else latest_version

                # 比较版本时只比较前三部分，忽略后面的构建号
                if self._compare_versions(instance_version_to_compare,
                                          latest_version_to_compare) < 0:
                    self.log.debug(
                        f"实例 {resource['name']} "
                        f"的版本 {complete_version} 不是最新小版本 {latest_version}")
                    outdated_resources.append(resource)
            else:
                self.log.debug(
                    f"找不到实例 {resource['name']} 的主版本 {major_version} 对应的最新小版本")

        return outdated_resources

    def _compare_versions(self, version1, version2):
        """比较两个版本号的大小，只比较前三个部分（如8.0.28），忽略后面的构建号
        返回值:
            -1: version1 < version2
             0: version1 = version2
             1: version1 > version2
        """
        # 确保只比较前三个版本号部分
        v1_parts = version1.split('.')[:3]
        v2_parts = version2.split('.')[:3]
        for i in range(max(len(v1_parts), len(v2_parts))):
            # 如果一个版本号部分不存在，则视为0
            v1 = int(v1_parts[i]) if i < len(v1_parts) else 0
            v2 = int(v2_parts[i]) if i < len(v2_parts) else 0

            if v1 < v2:
                return -1
            elif v1 > v2:
                return 1

        return 0


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
            has_eip = resource.get('public_ips') is not None and len(
                resource.get('public_ips', [])) > 0
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
                self.log.error(
                    f"获取RDS实例 {resource['name']} (ID: {instance_id}) 的审计日志策略失败: {e}")
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

                if keep_days == 0:
                    matched_resources.append(resource)
            except Exception as e:
                self.log.error(
                    f"获取RDS实例 {resource['name']} (ID: {instance_id}) 的备份策略失败: {e}")
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
                    self.log.debug(
                        f"RDS实例 {resource['name']} (ID: {instance_id}) 没有参数 {param_name}")
            except Exception as e:
                self.log.error(
                    f"获取RDS实例 {resource['name']} (ID: {instance_id}) 的参数模板失败: {e}")

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
            request_body = {
                'security_group_id': security_group_id
            }
            request.body = request_body
            response = client.set_security_group(request)
            self.log.info(f"成功为RDS实例 {resource['name']} (ID: {instance_id}) 设置安全组")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(f"无法为RDS实例 {resource['name']} (ID: {instance_id}) 设置安全组: {e}")
            raise


@RDS.action_registry.register('switch-ssl')
class SwitchSSLAction(HuaweiCloudBaseAction):
    """开启或关闭RDS实例的SSL加密,只支持MySQL,pg通过修改参数控制

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-enable-ssl
            resource: huaweicloud.rds
            filters:
            - type: value
                key: enable_ssl
                value: true
            actions:
              - type: switch-ssl
                ssl_option: false
    """
    schema = type_schema(
        'switch-ssl',
        required=['ssl_option'],
        ssl_option={'type': 'boolean'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        ssl_option = self.data['ssl_option']

        try:
            request = SwitchSslRequest()
            request.instance_id = instance_id
            ssl_option = True if ssl_option else False
            request_body = {
                'ssl_option': ssl_option
            }
            request.body = request_body
            response = client.switch_ssl(request)
            self.log.info(
                f"成功为RDS实例 {resource['name']} (ID: {instance_id}) "
                f"{'启用' if ssl_option else '禁用'}SSL加密")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"无法为RDS实例 {resource['name']} (ID: {instance_id}) "
                f"{'启用' if ssl_option else '禁用'}SSL加密: {e}")
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
              - type: value
                key: name
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
            # 构建请求体
            request_body = {
                'port': port
            }
            request.instance_id = instance_id
            request.body = request_body
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

        if switch_option:
            body = CustomerModifyAutoEnlargePolicyReq(
                switch_option=switch_option,
                limit_size=self.data['limit_size'],
                trigger_threshold=self.data['trigger_threshold'],
                step_percent=self.data['step_percent'],
            )
        else:
            body = CustomerModifyAutoEnlargePolicyReq(
                switch_option=switch_option,
            )

        request = SetAutoEnlargePolicyRequest(instance_id=instance_id, body=body)

        try:
            response = client.set_auto_enlarge_policy(request)
            self.log.info(
                f"成功为RDS实例 {resource['name']} (ID: {instance_id}) "
                f"{'启用' if switch_option else '禁用'}自动扩容策略")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"无法为RDS实例 {resource['name']} (ID: {instance_id}) 设置自动扩容策略: {e}")
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
              - type: rds-list
                ids:
                  - 926dfdb3ff654c6e9506ca91e0b403b3in03
            actions:
              - type: attach-eip
                is_bind: true
                public_ip: 1.178.45.199
                public_ip_id: 1bf25cb6-13ef-4a71-a85f-e4da190c016d
    """
    schema = type_schema(
        'attach-eip',
        required=['is_bind'],
        is_bind={'type': 'boolean'},
        public_ip={'type': 'string'},
        public_ip_id={'type': 'string'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        is_bind = self.data['is_bind']
        public_ip = self.data.get('public_ip')
        public_ip_id = self.data.get('public_ip_id')

        if is_bind == 'bind' and (not public_ip or not public_ip_id):
            self.log.error("绑定弹性公网IP时必须提供public_ip和public_ip_id参数")
            return

        try:
            request = AttachEipRequest()
            request.instance_id = instance_id
            request_body = {
                'is_bind': is_bind
            }
            if is_bind:
                request_body['public_ip'] = public_ip
                request_body['public_ip_id'] = public_ip_id
            request.body = request_body
            response = client.attach_eip(request)
            self.log.info(
                f"成功为RDS实例 {resource['name']} (ID: {instance_id}) "
                f"{'绑定' if is_bind else '解绑'}弹性公网IP")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"无法为RDS实例 {resource['name']} (ID: {instance_id}) "
                f"{'绑定' if is_bind else '解绑'}弹性公网IP: {e}")
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
                is_delayed: false
                target_version: 5.7.41  # 可选参数，指定目标版本
                set_backup: true  # 可选参数，是否设置自动备份
    """
    schema = type_schema(
        'upgrade-db-version',
        is_delayed={'type': 'boolean'},
        target_version={'type': 'string'},
        set_backup={'type': 'boolean'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        is_delayed = self.data.get('is_delayed', False)
        target_version = self.data.get('target_version')
        set_backup = self.data.get('set_backup', False)

        try:
            # 构建版本升级请求
            # API文档: https://support.huaweicloud.com/api-rds/rds_05_0041.html
            # POST /v3/{project_id}/instances/{instance_id}
            request = UpgradeDbVersionNewRequest()
            request.instance_id = instance_id

            # 设置升级参数
            upgrade_req = CustomerUpgradeDatabaseVersionReq()
            upgrade_req.delay = is_delayed

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
                        self.log.warning(
                            f"找不到指定的目标版本 {target_version}，将使用默认版本升级")
                except Exception as e:
                    self.log.error(f"获取可用版本列表失败: {e}")

            # 是否设置备份
            if set_backup:
                upgrade_req.with_backup = True

            # 设置请求体
            request.body = upgrade_req

            # 执行升级请求
            response = client.upgrade_db_version_new(request)
            self.log.info(
                f"成功为RDS实例 {resource['name']} (ID: {instance_id}) 提交数据库版本升级请求")

            return response
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"无法为RDS实例 {resource['name']} (ID: {instance_id}) 升级数据库版本: {e}")
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
            request.body = {}
            request.instance_id = instance_id
            request.body['keep_days'] = keep_days

            if keep_days == 0:
                request.body['reserve_auditlogs'] = reserve_auditlogs

            if audit_types and keep_days > 0:
                request.body['audit_types'] = audit_types

            response = client.set_auditlog_policy(request)
            self.log.info(
                f"成功为RDS实例 {resource['name']} (ID: {instance_id}) "
                f"{'启用' if keep_days > 0 else '禁用'}审计日志策略")
            return response
        except Exception as e:
            self.log.error(
                f"无法为RDS实例 {resource['name']} (ID: {instance_id}) 设置审计日志策略: {e}")
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
                keep_days: 3
                start_time: "01:00-02:00"
                period: "1,2,3,4"
                reserve_backups: "true"
    """
    schema = type_schema(
        'set-backup-policy',
        required=['keep_days', 'start_time', 'period'],
        keep_days={'type': 'integer', 'minimum': 1, 'maximum': 732},
        start_time={'type': 'string'},
        period={'type': 'string'},
        reserve_backups={'enum': ['true', 'false'], 'default': 'true'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        keep_days = self.data['keep_days']
        start_time = self.data['start_time']
        period = self.data['period']
        reserve_backups = self.data.get('reserve_backups', 'true')

        try:
            # 设置备份策略
            # API文档: https://support.huaweicloud.com/api-rds/rds_09_0002.html
            # PUT /v3/{project_id}/instances/{instance_id}/backups/policy
            request = SetBackupPolicyRequest()
            request.instance_id = instance_id

            backupPolicyBody = BackupPolicy(keep_days=keep_days,
                                            start_time=start_time,
                                            period=period)

            # 构建请求体
            request_body = SetBackupPolicyRequestBody(
                backup_policy=backupPolicyBody,
                reserve_backups=reserve_backups
            )
            request.body = request_body

            response = client.set_backup_policy(request)
            self.log.info(f"成功为RDS实例 {resource['name']} (ID: {instance_id}) 设置自动备份策略")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"无法为RDS实例 {resource['name']} (ID: {instance_id}) 设置自动备份策略: {e}")
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
            self.log.error(
                f"无法为RDS实例 {resource['name']} (ID: {instance_id}) 修改参数配置: {e}")
            raise


@RDS.filter_registry.register('postgresql-hba-conf')
class PostgresqlHbaConfFilter(Filter):
    """过滤基于pg_hba.conf配置的PostgreSQL RDS实例

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-pg-hba-conf-check
            resource: huaweicloud.rds
            filters:
              - type: postgresql-hba-conf
                has_config:
                  type: host
                  database: all
                  user: all
                  address: 0.0.0.0/0
                  method: md5
    """
    schema = type_schema(
        'postgresql-hba-conf',
        has_config={
            'type': 'object',
            'properties': {
                'type': {'type': 'string'},
                'database': {'type': 'string'},
                'user': {'type': 'string'},
                'address': {'type': 'string'},
                'mask': {'type': 'string'},
                'method': {'type': 'string'}
            }
        }
    )

    def process(self, resources, event=None):
        client = local_session(self.manager.session_factory).client("rds")
        has_config = self.data.get('has_config')
        matched_resources = []

        for resource in resources:
            # 只处理PostgreSQL实例
            if resource.get('datastore', {}).get('type', '').lower() != 'postgresql':
                continue

            instance_id = resource['id']
            try:
                # 查询实例的pg_hba.conf文件配置
                # API文档: https://support.huaweicloud.com/api-rds/rds_11_0020.html
                request = ListPostgresqlHbaInfoRequest()
                request.instance_id = instance_id
                response = client.list_postgresql_hba_info(request)

                if not has_config:
                    # 如果没有指定过滤条件，返回所有PostgreSQL实例
                    matched_resources.append(resource)
                    continue

                # configs = response.hba_conf_items
                # match_found = False

                # 检查每一个配置是否匹配过滤条件
                for config in response.body:
                    config_match = True

                    # 检查每个指定的属性
                    for key, value in has_config.items():
                        if key == 'type' and getattr(config, 'type', None) != value:
                            config_match = False
                            break
                        elif key == 'database' and getattr(config, 'database', None) != value:
                            config_match = False
                            break
                        elif key == 'user' and getattr(config, 'user', None) != value:
                            config_match = False
                            break
                        elif key == 'address' and getattr(config, 'address', None) != value:
                            config_match = False
                            break
                        elif key == 'mask' and getattr(config, 'mask', None) != value:
                            config_match = False
                            break
                        elif key == 'method' and getattr(config, 'method', None) != value:
                            config_match = False
                            break

                    if config_match:
                        match_found = True
                        break

                if match_found:
                    matched_resources.append(resource)
            except Exception as e:
                self.log.error(
                    f"获取RDS PostgreSQL实例 {resource['name']} "
                    f"(ID: {instance_id}) 的pg_hba.conf配置失败: {e}")

        return matched_resources


@RDS.action_registry.register('modify-pg-hba-conf')
class ModifyPgHbaConfAction(HuaweiCloudBaseAction):
    """修改pg_hba.conf文件的单个或多个配置

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-modify-pg-hba-conf
            resource: huaweicloud.rds
            filters:
              - type: postgresql-hba-conf
                has_config:
                  type: host
                  database: all
                  user: all
                  address: 0.0.0.0/0
                  method: md5
            actions:
              - type: modify-pg-hba-conf
                configs:
                  - type: hostssl
                    database: all
                    user: all
                    address: 0.0.0.0/0
                    mask: ""
                    method: scram-sha-256
                    priority: 0
    """
    schema = type_schema(
        'modify-pg-hba-conf',
        required=['configs'],
        configs={
            'type': 'array',
            'items': {
                'type': 'object',
                'required': ['type', 'database', 'user', 'address', 'method', 'priority'],
                'properties': {
                    'type': {'type': 'string'},
                    'database': {'type': 'string'},
                    'user': {'type': 'string'},
                    'address': {'type': 'string'},
                    'mask': {'type': 'string'},
                    'method': {'type': 'string'},
                    'priority': {'type': 'integer'}
                }
            }
        }
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        configs = self.data.get('configs', [])

        # 只处理PostgreSQL实例
        if resource.get('datastore', {}).get('type', '').lower() != 'postgresql':
            self.log.warning(f"实例 {resource['name']}"
                             f" (ID: {instance_id}) 不是PostgreSQL实例，跳过修改pg_hba.conf的操作")
            return

        try:
            # 修改pg_hba.conf文件配置
            # API文档: https://support.huaweicloud.com/api-rds/rds_11_0021.html
            request = ModifyPostgresqlHbaConfRequest()
            request.instance_id = instance_id
            request.body = configs

            response = client.modify_postgresql_hba_conf(request)
            self.log.info(f"成功修改RDS PostgreSQL实例 {resource['name']}"
                          f" (ID: {instance_id}) 的pg_hba.conf配置")
            return response
        except Exception as e:
            self.log.error(f"修改RDS PostgreSQL实例 {resource['name']}"
                           f" (ID: {instance_id}) 的pg_hba.conf配置失败: {e}")
            raise


@RDS.action_registry.register('enable-tde')
class EnableTDEAction(HuaweiCloudBaseAction):
    """为SQL Server实例开启TDE（透明数据加密）功能

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-enable-tde
            resource: huaweicloud.rds
            filters:
              - type: value
                key: datastore.type
                value: SQLServer
            actions:
              - type: enable-tde
    """
    schema = type_schema(
        'enable-tde',
        rotate_day={'type': 'integer', 'minimum': 1, 'maximum': 100000},
        secret_id={'type': 'string'},
        secret_name={'type': 'string'},
        secret_version={'type': 'string'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']

        # 检查是否为SQL Server实例
        if resource.get('datastore', {}).get('type', '').lower() != 'sqlserver':
            self.log.warning(f"实例 {resource['name']}"
                             f" (ID: {instance_id}) 不是SQL Server实例，跳过开启TDE功能")
            return

        try:
            # 开启TDE功能
            # API文档: https://support.huaweicloud.com/api-rds/rds_06_0045.html
            # PUT /v3/{project_id}/instances/{instance_id}/tde
            request = UpdateTdeStatusRequest()
            request.instance_id = instance_id

            # 如果需要使用TDE轮转功能，则添加相应参数
            rotate_day = self.data.get('rotate_day')
            secret_id = self.data.get('secret_id')
            secret_name = self.data.get('secret_name')
            secret_version = self.data.get('secret_version')

            # 构建请求体，仅在使用轮转功能时添加相关参数
            body = {}
            if rotate_day is not None:
                body['rotate_day'] = rotate_day
            if secret_id is not None:
                body['secret_id'] = secret_id
            if secret_name is not None:
                body['secret_name'] = secret_name
            if secret_version is not None:
                body['secret_version'] = secret_version

            request.body = body

            response = client.update_tde_status(request)
            self.log.info(f"成功为RDS SQL Server实例 {resource['name']}"
                          f" (ID: {instance_id}) 开启TDE功能")
            return response
        except Exception as e:
            self.log.error(f"无法为RDS SQL Server实例 {resource['name']}"
                           f" (ID: {instance_id}) 开启TDE功能: {e}")
            raise
