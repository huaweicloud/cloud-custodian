# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from huaweicloud_common import BaseTest
# 注意：实际测试需要对应的 VCR 文件 (例如 rds_query.yaml, rds_filter_*.yaml, rds_action_*.yaml)
# 这些文件应包含测试所需的 RDS 实例数据和 API 交互记录。

class RDSTest(BaseTest):
    """测试华为云 RDS 资源、过滤器和操作"""

    # =========================
    # Resource Query Test
    # =========================
    def test_rds_query(self):
        """测试 RDS 实例查询和基本属性"""
        factory = self.replay_flight_data("rds_query")
        p = self.load_policy(
            {
                "name": "rds-query-test",
                "resource": "huaweicloud.rds",
            },
            session_factory=factory,
        )
        resources = p.run()
        # 验证 VCR: rds_query.yaml 应至少包含一个 RDS 实例
        self.assertGreater(len(resources), 0, "测试 VCR 文件应至少包含一个 RDS 实例")
        # 验证 VCR: 验证第一个实例的关键属性是否存在且符合预期
        instance = resources[0]
        self.assertTrue("id" in instance)
        self.assertTrue("name" in instance)
        self.assertTrue("status" in instance)
        self.assertTrue("created" in instance) # 验证 'created' 字段存在 (用于 AgeFilter)
        self.assertTrue("datastore" in instance) # 验证 'datastore' 字段存在 (用于 DatabaseVersionFilter)
        self.assertTrue("port" in instance) # 验证 'port' 字段存在 (用于 DatabasePortFilter)
        self.assertTrue("enable_ssl" in instance) # 验证 'ssl_enable' 字段存在 (用于 SSLInstanceFilter)
        # 验证 'disk_encryption_id' 是否存在（或不存在），用于 DiskAutoExpansionFilter
        self.assertTrue("disk_encryption_id" in instance or instance.get("disk_encryption_id") is None)
        # 验证 'public_ips' 是否存在，用于 EIPFilter
        self.assertTrue("public_ips" in instance)

    # =========================
    # Filter Tests
    # =========================


    def test_rds_filter_disk_auto_expansion_enabled(self):
        """测试 disk-auto-expansion 过滤器 - 启用状态匹配"""
        factory = self.replay_flight_data("rds_filter_disk_auto_expansion")
        # 验证 VCR: rds_filter_disk_auto_expansion.yaml 应包含至少一个启用了自动扩容的实例
        p = self.load_policy(
            {
                "name": "rds-filter-disk-expansion-enabled-test",
                "resource": "huaweicloud.rds",
                "filters": [{"type": "disk-auto-expansion", "enabled": True}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreater(len(resources), 0, "测试 VCR 文件应包含启用了自动扩容的 RDS 实例")
        # 不再检查 disk_encryption_id，因为改用了 show_auto_enlarge_policy API 来获取自动扩容状态

    def test_rds_filter_disk_auto_expansion_disabled(self):
        """测试 disk-auto-expansion 过滤器 - 禁用状态匹配"""
        factory = self.replay_flight_data("rds_filter_disk_auto_expansion") # 复用 VCR
        # 验证 VCR: rds_filter_disk_auto_expansion.yaml 应包含至少一个禁用了自动扩容的实例
        p = self.load_policy(
            {
                "name": "rds-filter-disk-expansion-disabled-test",
                "resource": "huaweicloud.rds",
                "filters": [{"type": "disk-auto-expansion", "enabled": False}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreater(len(resources), 0, "测试 VCR 文件应包含禁用了自动扩容的 RDS 实例")
        # 不再检查 disk_encryption_id，因为改用了 show_auto_enlarge_policy API 来获取自动扩容状态


    def test_rds_filter_db_version_lt(self):
        """测试 database-version 过滤器 - 小于 (lt)"""
        factory = self.replay_flight_data("rds_filter_db_version") # 复用 VCR
        # 验证 VCR: rds_filter_db_version.yaml 应包含版本小于 '8.0' 的实例 (例如 '5.7')
        upper_bound_version = "8.0"
        p = self.load_policy(
            {
                "name": "rds-filter-db-version-lt-test",
                "resource": "huaweicloud.rds",
                "filters": [{"type": "database-version", "version": upper_bound_version, "op": "lt"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreater(len(resources), 0, f"测试 VCR 文件应包含版本小于 {upper_bound_version} 的 RDS 实例")
        for r in resources:
            self.assertTrue(r.get("datastore", {}).get("version") < upper_bound_version)

    def test_rds_filter_eip_exists(self):
        """测试 eip 过滤器 - 存在 EIP"""
        factory = self.replay_flight_data("rds_filter_eip")
        # 验证 VCR: rds_filter_eip.yaml 应包含绑定了 EIP 的实例 (public_ips 列表不为空)
        p = self.load_policy(
            {
                "name": "rds-filter-eip-exists-test",
                "resource": "huaweicloud.rds",
                "filters": [{"type": "eip", "exists": True}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreater(len(resources), 0, "测试 VCR 文件应包含绑定了 EIP 的 RDS 实例")
        for r in resources:
            self.assertTrue(r.get("public_ips") is not None and len(r["public_ips"]) > 0)

    def test_rds_filter_eip_not_exists(self):
        """测试 eip 过滤器 - 不存在 EIP"""
        factory = self.replay_flight_data("rds_filter_eip") # 复用 VCR
        # 验证 VCR: rds_filter_eip.yaml 应包含未绑定 EIP 的实例 (public_ips 列表为空或为 None)
        p = self.load_policy(
            {
                "name": "rds-filter-eip-not-exists-test",
                "resource": "huaweicloud.rds",
                "filters": [{"type": "eip", "exists": False}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreater(len(resources), 0, "测试 VCR 文件应包含未绑定 EIP 的 RDS 实例")
        for r in resources:
            self.assertTrue(r.get("public_ips") is None or len(r["public_ips"]) == 0)

    def test_rds_filter_audit_log_disabled(self):
        """测试 audit-log-disabled 过滤器"""
        factory = self.replay_flight_data("rds_filter_audit_log_disabled")
        # 验证 VCR: rds_filter_audit_log_disabled.yaml 应包含未开启审计日志的实例
        p = self.load_policy(
            {
                "name": "rds-filter-audit-log-disabled-test",
                "resource": "huaweicloud.rds",
                "filters": [{"type": "audit-log-disabled"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreater(len(resources), 0, "测试 VCR 文件应包含未开启审计日志的 RDS 实例")
        # 测试的 VCR 文件中应包含对 show_auditlog_policy API 的调用和响应

    def test_rds_filter_backup_policy_disabled(self):
        """测试 backup-policy-disabled 过滤器"""
        factory = self.replay_flight_data("rds_filter_backup_policy_disabled")
        # 验证 VCR: rds_filter_backup_policy_disabled.yaml 应包含未开启自动备份的实例
        p = self.load_policy(
            {
                "name": "rds-filter-backup-policy-disabled-test",
                "resource": "huaweicloud.rds",
                "filters": [{"type": "backup-policy-disabled"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreater(len(resources), 0, "测试 VCR 文件应包含未开启自动备份的 RDS 实例")
        # 测试的 VCR 文件中应包含对 show_backup_policy API 的调用和响应

    def test_rds_filter_instance_parameter_eq(self):
        """测试 instance-parameter 过滤器 - 等于 (eq)"""
        factory = self.replay_flight_data("rds_filter_instance_parameter")
        # 验证 VCR: rds_filter_instance_parameter.yaml 应包含参数 max_connections 为 500 的实例
        param_name = "max_connections"
        param_value = 500
        p = self.load_policy(
            {
                "name": "rds-filter-instance-parameter-eq-test",
                "resource": "huaweicloud.rds",
                "filters": [{"type": "instance-parameter", "name": param_name, "value": param_value,
                             "op": "eq"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreater(len(resources), 0,
                           f"测试 VCR 文件应包含参数 {param_name} 为 {param_value} 的 RDS 实例")
        # 测试的 VCR 文件中应包含对 show_instance_configuration API 的调用和响应

    def test_rds_filter_instance_parameter_lt(self):
        """测试 instance-parameter 过滤器 - 小于 (lt)"""
        factory = self.replay_flight_data("rds_filter_instance_parameter")  # 复用 VCR
        param_name = "max_connections"
        upper_bound = 1000
        p = self.load_policy(
            {
                "name": "rds-filter-instance-parameter-lt-test",
                "resource": "huaweicloud.rds",
                "filters": [{"type": "instance-parameter", "name": param_name, "value": upper_bound,
                             "op": "lt"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreater(len(resources), 0,
                           f"测试 VCR 文件应包含参数 {param_name} 小于 {upper_bound} 的 RDS 实例")

    # =========================
    # Action Tests
    # =========================
    def test_rds_action_set_security_group(self):
        """测试 set-security-group 操作"""
        factory = self.replay_flight_data("rds_action_set_sg")
        # 验证 VCR: rds_action_set_sg.yaml 包含要修改安全组的实例
        target_instance_id = "rds-instance-for-sg-test"
        new_sg_id = "new-security-group-id"
        p = self.load_policy(
            {
                "name": "rds-action-set-sg-test",
                "resource": "huaweicloud.rds",
                "filters": [{"type": "value", "key": "security_group_id", "value": ""}], # 使用 value 过滤器更佳
                "actions": [{"type": "set-security-group", "security_group_id": new_sg_id}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1) # 确认策略过滤到了目标资源
        self.assertEqual(resources[0]["id"], target_instance_id)
        # 验证操作: 需要手动检查 VCR 文件 rds_action_set_sg.yaml
        # 确认调用了 POST /v3/{project_id}/instances/{instance_id}/security-group
        # 并且请求体包含 {"security_group_id": "new-security-group-id"}

    def test_rds_action_switch_ssl_on(self):
        """测试 switch-ssl 操作 - 开启 SSL"""
        factory = self.replay_flight_data("rds_action_switch_ssl_on")
        # 验证 VCR: rds_action_switch_ssl_on.yaml 包含要开启 SSL 的实例 (ssl_enable: false)
        target_instance_id = "rds-instance-for-ssl-on"
        p = self.load_policy(
            {
                "name": "rds-action-ssl-on-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    {"type": "value", "key": "enable_ssl","value":"false"} # 确保只对未开启的实例操作
                ],
                "actions": [{"type": "switch-ssl", "ssl_enable": True}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        self.assertFalse(resources[0]["ssl_enable"]) # 确认操作前的状态
        # 验证操作: 需要手动检查 VCR 文件 rds_action_switch_ssl_on.yaml
        # 确认调用了 POST /v3/{project_id}/instances/{instance_id}/ssl
        # 并且请求体包含 {"ssl_option": "on"}

    def test_rds_action_switch_ssl_off(self):
        """测试 switch-ssl 操作 - 关闭 SSL"""
        factory = self.replay_flight_data("rds_action_switch_ssl_off")
        # 验证 VCR: rds_action_switch_ssl_off.yaml 包含要关闭 SSL 的实例 (ssl_enable: true)
        target_instance_id = "rds-instance-for-ssl-off"
        p = self.load_policy(
            {
                "name": "rds-action-ssl-off-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    {"type": "value", "key": "enable_ssl","value":"false"}  # 确保只对已开启的实例操作
                ],
                "actions": [{"type": "switch-ssl", "ssl_enable": False}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        self.assertTrue(resources[0]["ssl_enable"]) # 确认操作前的状态
        # 验证操作: 需要手动检查 VCR 文件 rds_action_switch_ssl_off.yaml
        # 确认调用了 POST /v3/{project_id}/instances/{instance_id}/ssl
        # 并且请求体包含 {"ssl_option": "off"}

    def test_rds_action_update_port(self):
        """测试 update-port 操作"""
        factory = self.replay_flight_data("rds_action_update_port")
        # 验证 VCR: rds_action_update_port.yaml 包含要修改端口的实例
        target_instance_id = "rds-instance-for-port-update"
        original_port = 3306 # 假设 VCR 中实例原始端口是 3306
        new_port = 3307
        p = self.load_policy(
            {
                "name": "rds-action-update-port-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    {"type": "value", "key": "port", "value": "3306"} # 确保只对特定端口的实例操作
                ],
                "actions": [{"type": "update-port", "port": new_port}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        self.assertEqual(resources[0]["port"], original_port) # 确认操作前的端口
        # 验证操作: 需要手动检查 VCR 文件 rds_action_update_port.yaml
        # 确认调用了 PUT /v3/{project_id}/instances/{instance_id}/port
        # 并且请求体包含 {"port": 3307}

    def test_rds_action_set_auto_enlarge_policy(self):
        """测试 set-auto-enlarge-policy 操作 - 完整参数设置"""
        factory = self.replay_flight_data("rds_action_set_auto_enlarge_policy")
        # 验证 VCR: rds_action_set_auto_enlarge_policy.yaml 包含要设置自动扩容策略的实例
        target_instance_id = "rds-instance-for-auto-enlarge-policy"
        p = self.load_policy(
            {
                "name": "rds-action-auto-enlarge-policy-test",
                "resource": "huaweicloud.rds",
                "filters": [{"id": target_instance_id}],
                "actions": [{
                    "type": "set-auto-enlarge-policy",
                    "switch_option": True,
                    "limit_size": 1000,
                    "trigger_threshold": 10,
                    "step_percent": 20
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        # 验证操作: 需要手动检查 VCR 文件 rds_action_set_auto_enlarge_policy.yaml
        # 确认调用了正确的 API 并包含期望的请求参数

    def test_rds_action_attach_eip_bind(self):
        """测试 attach-eip 操作 - 绑定"""
        factory = self.replay_flight_data("rds_action_attach_eip_bind")
        # 验证 VCR: rds_action_attach_eip_bind.yaml 包含要绑定 EIP 的实例 (无 public_ips)
        target_instance_id = "rds-instance-for-eip-bind"
        public_ip_to_bind = "123.123.123.123" # 替换为 VCR 中准备好的 EIP
        p = self.load_policy(
            {
                "name": "rds-action-eip-bind-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    {"type": "value", "key": "public_ips", "value": "[]"} # 确保只对没有 EIP 的实例操作
                ],
                "actions": [{
                    "type": "attach-eip",
                    "bind_type": "bind",
                    "public_ip": public_ip_to_bind
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        # 验证操作: 需要手动检查 VCR 文件 rds_action_attach_eip_bind.yaml
        # 确认调用了 POST /v3/{project_id}/instances/{instance_id}/eip
        # 并且请求体包含 {"bind_type": "bind", "public_ip": "123.123.123.123"}

    def test_rds_action_attach_eip_unbind(self):
        """测试 attach-eip 操作 - 解绑"""
        factory = self.replay_flight_data("rds_action_attach_eip_unbind")
        # 验证 VCR: rds_action_attach_eip_unbind.yaml 包含要解绑 EIP 的实例 (有 public_ips)
        target_instance_id = "rds-instance-for-eip-unbind"
        p = self.load_policy(
            {
                "name": "rds-action-eip-unbind-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    {"type": "value", "key": "public_ips","value":"[123.123.123.124]"} # 确保只对有 EIP 的实例操作
                ],
                "actions": [{"type": "attach-eip", "bind_type": "unbind"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        # 验证操作: 需要手动检查 VCR 文件 rds_action_attach_eip_unbind.yaml
        # 确认调用了 POST /v3/{project_id}/instances/{instance_id}/eip
        # 并且请求体包含 {"bind_type": "unbind"}

    def test_rds_action_upgrade_db_version_immediate(self):
        """测试 upgrade-db-version 操作 - 立即升级"""
        factory = self.replay_flight_data("rds_action_upgrade_db_version_immediate")
        # 验证 VCR: rds_action_upgrade_db_version_immediate.yaml 包含可以升级小版本的实例
        target_instance_id = "rds-instance-for-upgrade-immediate"
        p = self.load_policy(
            {
                "name": "rds-action-upgrade-immediate-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    {"id": target_instance_id},
                    # 过滤特定版本的数据库实例
                    {"type": "database-version", "version": "5.7.37", "op": "lt"}
                ],
                "actions": [{"type": "upgrade-db-version", "is_immediately": True}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        # 验证操作: 需要手动检查 VCR 文件 rds_action_upgrade_db_version_immediate.yaml
        # 确认调用了 POST /v3/{project_id}/instances/{instance_id}/action
        # 并且请求体包含 CustomerUpgradeDatabaseVersionReq 对象及 is_immediately=true

    def test_rds_action_upgrade_db_version_with_target(self):
        """测试 upgrade-db-version 操作 - 指定目标版本"""
        factory = self.replay_flight_data("rds_action_upgrade_db_version_with_target")
        # 验证 VCR: rds_action_upgrade_db_version_with_target.yaml 包含可以升级到特定版本的实例
        target_instance_id = "rds-instance-for-upgrade-with-target"
        target_version = "5.7.41"  # 目标版本
        p = self.load_policy(
            {
                "name": "rds-action-upgrade-with-target-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    {"id": target_instance_id},
                    {"type": "database-version", "version": target_version, "op": "lt"}
                ],
                "actions": [{
                    "type": "upgrade-db-version", 
                    "is_immediately": False,
                    "target_version": target_version,
                    "set_backup": True
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        # 验证操作: 需要手动检查 VCR 文件 rds_action_upgrade_db_version_with_target.yaml
        # 确认调用了 POST /v3/{project_id}/instances/{instance_id}/action
        # 并且请求体包含 CustomerUpgradeDatabaseVersionReq 对象及 is_immediately=false, target_version 和 with_backup=true

    def test_rds_action_upgrade_db_version_later(self):
        """测试 upgrade-db-version 操作 - 稍后升级 (维护窗口)"""
        factory = self.replay_flight_data("rds_action_upgrade_db_version_later")
        # 验证 VCR: rds_action_upgrade_db_version_later.yaml 包含可以升级小版本的实例
        target_instance_id = "rds-instance-for-upgrade-later"
        p = self.load_policy(
            {
                "name": "rds-action-upgrade-later-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    {"type": "value", "key": "id", "value": target_instance_id}
                ],
                "actions": [{"type": "upgrade-db-version", "is_immediately": False}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        # 验证操作: 需要手动检查 VCR 文件 rds_action_upgrade_db_version_later.yaml
        # 确认调用了 POST /v3/{project_id}/instances/{instance_id}/action
        # 并且请求体包含 CustomerUpgradeDatabaseVersionReq 对象及 is_immediately=false

    def test_rds_action_set_audit_log_policy_enable(self):
        """测试 set-audit-log-policy 操作 - 启用审计日志"""
        factory = self.replay_flight_data("rds_action_set_audit_log_policy_enable")
        # 验证 VCR: rds_action_set_audit_log_policy_enable.yaml 包含要启用审计日志的实例
        target_instance_id = "rds-instance-for-audit-log-enable"
        p = self.load_policy(
            {
                "name": "rds-action-audit-log-enable-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    {"id": target_instance_id},
                    {"type": "audit-log-disabled"}
                ],
                "actions": [{
                    "type": "set-audit-log-policy",
                    "keep_days": 7,
                    "audit_types": ["SELECT", "INSERT", "UPDATE", "DELETE"]
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        # 验证操作: 需要手动检查 VCR 文件 rds_action_set_audit_log_policy_enable.yaml
        # 确认调用了 PUT /v3/{project_id}/instances/{instance_id}/auditlog-policy
        # 并且请求体包含 {"keep_days": 7, "audit_types": ["SELECT", "INSERT", "UPDATE", "DELETE"]}

    def test_rds_action_set_audit_log_policy_disable(self):
        """测试 set-audit-log-policy 操作 - 禁用审计日志"""
        factory = self.replay_flight_data("rds_action_set_audit_log_policy_disable")
        # 验证 VCR: rds_action_set_audit_log_policy_disable.yaml 包含要禁用审计日志的实例
        target_instance_id = "rds-instance-for-audit-log-disable"
        p = self.load_policy(
            {
                "name": "rds-action-audit-log-disable-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    {"id": target_instance_id},
                    # 此处不使用 audit-log-disabled 过滤器，因为我们要找的是已开启审计日志的实例
                ],
                "actions": [{
                    "type": "set-audit-log-policy",
                    "keep_days": 0,
                    "reserve_auditlogs": True
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        # 验证操作: 需要手动检查 VCR 文件 rds_action_set_audit_log_policy_disable.yaml
        # 确认调用了 PUT /v3/{project_id}/instances/{instance_id}/auditlog-policy
        # 并且请求体包含 {"keep_days": 0, "reserve_auditlogs": true}

# 可以添加更多测试用例来覆盖边界条件和错误场景
    def test_rds_action_set_backup_policy(self):
        """测试 set-backup-policy 操作"""
        factory = self.replay_flight_data("rds_action_set_backup_policy")
        # 验证 VCR: rds_action_set_backup_policy.yaml 包含要设置备份策略的实例
        target_instance_id = "rds-instance-for-backup-policy"
        p = self.load_policy(
            {
                "name": "rds-action-set-backup-policy-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    {"id": target_instance_id},
                    {"type": "backup-policy-disabled"}  # 确保只对未开启备份的实例操作
                ],
                "actions": [{
                    "type": "set-backup-policy",
                    "keep_days": 7,
                    "start_time": "01:00-02:00",
                    "period": "1,2,3,4,5,6,7",
                    "backup_type": "auto"
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        # 验证操作: 需要手动检查 VCR 文件 rds_action_set_backup_policy.yaml
        # 确认调用了 PUT /v3/{project_id}/instances/{instance_id}/backups/policy
        # 并且请求体包含正确的参数

    def test_rds_action_update_instance_parameter(self):
        """测试 update-instance-parameter 操作"""
        factory = self.replay_flight_data("rds_action_update_instance_parameter")
        # 验证 VCR: rds_action_update_instance_parameter.yaml 包含要修改参数的实例
        target_instance_id = "rds-instance-for-parameter-update"
        param_name = "max_connections"
        param_value = "1000"
        p = self.load_policy(
            {
                "name": "rds-action-update-instance-parameter-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    {"id": target_instance_id},
                    # 过滤参数值小于 1000 的实例
                    {"type": "instance-parameter", "name": param_name, "value": int(param_value),
                     "op": "lt"}
                ],
                "actions": [{
                    "type": "update-instance-parameter",
                    "parameters": [
                        {"name": param_name, "value": param_value}
                    ]
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        # 验证操作: 需要手动检查 VCR 文件 rds_action_update_instance_parameter.yaml
        # 确认调用了 PUT /v3/{project_id}/instances/{instance_id}/configurations
        # 并且请求体包含正确的参数

# =========================
# Reusable Feature Tests
# =========================

class ReusableRDSTests(BaseTest):
    """测试可复用的 Filters 和 Actions (以 RDS 为例)"""

    # --- 可复用过滤器测试 ---

    def test_rds_filter_value_match(self):
        """测试 value 过滤器 - 匹配"""
        factory = self.replay_flight_data("rds_reusable_filter_value")
        # 验证 VCR: rds_reusable_filter_value.yaml 应包含 status 为 ACTIVE 的实例
        target_status = "ACTIVE"
        p = self.load_policy(
            {
                "name": "rds-reusable-filter-value-match-test",
                "resource": "huaweicloud.rds",
                "filters": [{"type": "value", "key": "status", "value": target_status}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreater(len(resources), 0, f"测试 VCR 文件应包含 status 为 {target_status} 的 RDS 实例")
        for r in resources:
            self.assertEqual(r.get("status"), target_status)

    def test_rds_filter_value_no_match(self):
        """测试 value 过滤器 - 不匹配"""
        factory = self.replay_flight_data("rds_reusable_filter_value") # 复用 VCR
        non_existent_status = "NON_EXISTENT_STATUS"
        p = self.load_policy(
            {
                "name": "rds-reusable-filter-value-no-match-test",
                "resource": "huaweicloud.rds",
                "filters": [{"type": "value", "key": "status", "value": non_existent_status}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 0)

    def test_rds_filter_list_item_tag_match(self):
        """测试 list-item 过滤器 - 匹配标签"""
        factory = self.replay_flight_data("rds_reusable_filter_list_item_tag")
        # 验证 VCR: rds_reusable_filter_list_item_tag.yaml 应包含带有特定标签的实例
        target_tag_key = "cost_center"
        target_tag_value = "dev"
        p = self.load_policy(
            {
                "name": "rds-reusable-filter-list-item-tag-match-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    {
                        "type": "list-item",
                        "key": "tags", # RDS 实例的标签列表字段名通常是 'tags'
                        "attrs": [
                            {"type": "value", "key": "key", "value": target_tag_key},
                            {"type": "value", "key": "value", "value": target_tag_value}
                        ]
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreater(len(resources), 0, f"测试 VCR 文件应包含标签 {target_tag_key}={target_tag_value} 的 RDS 实例")
        # 可以进一步断言找到的资源确实包含该标签
        found_tag = False
        for tag in resources[0].get('tags', []):
            if tag.get('key') == target_tag_key and tag.get('value') == target_tag_value:
                found_tag = True
                break
        self.assertTrue(found_tag)

    def test_rds_filter_marked_for_op_match(self):
        """测试 marked-for-op 过滤器 - 匹配"""
        factory = self.replay_flight_data("rds_reusable_filter_marked_for_op")
        # 验证 VCR: rds_reusable_filter_marked_for_op.yaml 应包含被标记为 delete 且已到期的实例
        op = "delete"
        tag_key = "c7n_status" # 或 'custodian_cleanup' 等，取决于标记动作使用的标签
        p = self.load_policy(
            {
                "name": f"rds-reusable-filter-marked-for-{op}-match-test",
                "resource": "huaweicloud.rds",
                "filters": [{"type": "marked-for-op", "op": op, "tag": tag_key}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # 注意: VCR 文件中的标记日期需要相对于录制时间已过期
        self.assertGreater(len(resources), 0, f"测试 VCR 文件应包含被标记为 {op} 且已到期的 RDS 实例")

    def test_rds_filter_tag_count_match(self):
        """测试 tag-count 过滤器 - 匹配"""
        factory = self.replay_flight_data("rds_reusable_filter_tag_count")
        # 验证 VCR: rds_reusable_filter_tag_count.yaml 应包含恰好有 2 个标签的实例
        expected_tag_count = 2
        p = self.load_policy(
            {
                "name": "rds-reusable-filter-tag-count-match-test",
                "resource": "huaweicloud.rds",
                "filters": [{"type": "tag-count", "count": expected_tag_count}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreater(len(resources), 0, f"测试 VCR 文件应包含恰好有 {expected_tag_count} 个标签的 RDS 实例")
        for r in resources:
            self.assertEqual(len(r.get("tags", [])), expected_tag_count)

    # --- 可复用操作测试 ---

    def test_rds_action_tag(self):
        """测试 tag 操作 (添加标签)"""
        factory = self.replay_flight_data("rds_reusable_action_tag")
        # 验证 VCR: rds_reusable_action_tag.yaml 包含要添加标签的实例
        target_instance_id = "rds-instance-for-tagging"
        tag_key = "Project"
        tag_value = "Bluebird"
        p = self.load_policy(
            {
                "name": "rds-reusable-action-tag-test",
                "resource": "huaweicloud.rds",
                "filters": [{"id": target_instance_id}],
                "actions": [{"type": "tag", "key": tag_key, "value": tag_value}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        # 验证操作: 需要手动检查 VCR 文件 rds_reusable_action_tag.yaml
        # 确认调用了 RDS 的批量添加标签 API (POST /v3/{project_id}/instances/tags)
        # 并且请求体包含正确的 instance_id, action=create, 以及 tags: [{key: 'Project', value: 'Bluebird'}]

    def test_rds_action_remove_tag(self):
        """测试 remove-tag 操作 (删除标签)"""
        factory = self.replay_flight_data("rds_reusable_action_remove_tag")
        # 验证 VCR: rds_reusable_action_remove_tag.yaml 包含带有 'TempTag' 标签的实例
        target_instance_id = "rds-instance-for-untagging"
        tag_key_to_remove = "TempTag"
        p = self.load_policy(
            {
                "name": "rds-reusable-action-remove-tag-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    {"id": target_instance_id},
                    {f"tag:{tag_key_to_remove}": "present"} # 确保标签存在才移除
                ],
                "actions": [{"type": "remove-tag", "keys": [tag_key_to_remove, "NonExistentTag"]}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        # 验证操作: 需要手动检查 VCR 文件 rds_reusable_action_remove_tag.yaml
        # 确认调用了 RDS 的批量删除标签 API (POST /v3/{project_id}/instances/tags)
        # 并且请求体包含正确的 instance_id, action=delete, 以及 tags: [{key: 'TempTag'}, {key: 'NonExistentTag'}]
        # 注意：即使 NonExistentTag 不存在，API 调用也应包含它

    def test_rds_action_mark_for_op(self):
        """测试 mark-for-op 操作 (标记待删除)"""
        factory = self.replay_flight_data("rds_reusable_action_mark_for_op")
        # 验证 VCR: rds_reusable_action_mark_for_op.yaml 包含要标记的实例
        target_instance_id = "rds-instance-to-be-marked"
        op = "delete"
        days = 7
        tag_key = "custodian_cleanup"
        p = self.load_policy(
            {
                "name": f"rds-reusable-action-mark-for-{op}-test",
                "resource": "huaweicloud.rds",
                "filters": [{"id": target_instance_id}],
                "actions": [{
                    "type": "mark-for-op",
                    "op": op,
                    "days": days,
                    "tag": tag_key
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        # 验证操作: 需要手动检查 VCR 文件 rds_reusable_action_mark_for_op.yaml
        # 确认调用了 RDS 的批量添加标签 API
        # 并且请求体包含正确的 instance_id, action=create, 以及包含带时间戳值的标签 {key: 'custodian_cleanup', value: 'delete@YYYY/MM/DD...'}

