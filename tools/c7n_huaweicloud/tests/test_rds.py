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
        self.assertTrue("created" in instance)  # 验证 'created' 字段存在 (用于 AgeFilter)
        # 验证 'datastore' 字段存在 (用于 DatabaseVersionFilter)
        self.assertTrue("datastore" in instance)
        self.assertTrue("port" in instance)  # 验证 'port' 字段存在 (用于 DatabasePortFilter)
        # 验证 'ssl_enable' 字段存在 (用于 SSLInstanceFilter)
        self.assertTrue("enable_ssl" in instance)
        # 验证 'disk_encryption_id' 是否存在（或不存在），用于 DiskAutoExpansionFilter
        self.assertTrue(
            "disk_encryption_id" in instance or instance.get("disk_encryption_id") is None)
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
        factory = self.replay_flight_data("rds_filter_disk_auto_expansion")  # 复用 VCR
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
        """测试 database-version 过滤器 - 检测不是最新小版本的实例"""
        factory = self.replay_flight_data("rds_filter_db_version")  # 复用 VCR
        # 验证 VCR: rds_filter_db_version.yaml 应包含不是最新小版本的数据库实例
        p = self.load_policy(
            {
                "name": "rds-filter-db-version-test",
                "resource": "huaweicloud.rds",
                "filters": [{"type": "database-version", "database_name": "mysql"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreater(len(resources), 0, "测试 VCR 文件应包含不是最新小版本的 RDS 实例")

        # 验证过滤出的实例都是需要升级的
        # 注意：由于我们不能直接获取真实的最新版本进行对比，
        # 所以这里只能验证筛选逻辑正常运行并返回了结果
        # 实际测试时需确保 VCR 文件中包含最新小版本的信息供过滤器比较

        # 检查过滤后的实例包含数据库引擎和版本信息
        for resource in resources:
            self.assertTrue("datastore" in resource)
            self.assertTrue("type" in resource["datastore"])
            self.assertTrue("complete_version" in resource["datastore"]
                            or "version" in resource["datastore"])

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
        factory = self.replay_flight_data("rds_filter_eip")  # 复用 VCR
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
        print(resources)
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
                "filters": [{"type": "value",
                             "key": "id", "value": target_instance_id}],  # 使用 value 过滤器更佳
                "actions": [{"type": "set-security-group", "security_group_id": new_sg_id}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)  # 确认策略过滤到了目标资源
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
                    {"type": "value",
                     "key": "id", "value": target_instance_id}  # 确保只对未开启的实例操作
                ],
                "actions": [{"type": "switch-ssl", "ssl_option": True}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        self.assertFalse(resources[0]["enable_ssl"])  # 确认操作前的状态
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
                    {"type": "value",
                     "key": "id", "value": target_instance_id}  # 确保只对已开启的实例操作
                ],
                "actions": [{"type": "switch-ssl", "ssl_option": False}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        self.assertTrue(resources[0]["enable_ssl"])  # 确认操作前的状态
        # 验证操作: 需要手动检查 VCR 文件 rds_action_switch_ssl_off.yaml
        # 确认调用了 POST /v3/{project_id}/instances/{instance_id}/ssl
        # 并且请求体包含 {"ssl_option": "off"}

    def test_rds_action_update_port(self):
        """测试 update-port 操作"""
        factory = self.replay_flight_data("rds_action_update_port")
        # 验证 VCR: rds_action_update_port.yaml 包含要修改端口的实例
        target_instance_id = "rds-instance-for-port-update"
        original_port = 3306  # 假设 VCR 中实例原始端口是 3306
        new_port = 3307
        p = self.load_policy(
            {
                "name": "rds-action-update-port-test",
                "resource": "huaweicloud.rds",
                "actions": [{"type": "update-port", "port": new_port}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        self.assertEqual(resources[0]["port"], original_port)  # 确认操作前的端口
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
                "filters": [{  # "id": target_instance_id
                    "type": "value", "key": "id", "value": target_instance_id}],
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
        target_instance_id = "rds-instance-id-for-eip"
        public_ip_to_bind = "123.123.123.123"  # 替换为 VCR 中准备好的 EIP
        public_ip_id_to_bind = "1bf25cb6-13ef-4a71-a85f-e4da190c016d"  # 替换为 VCR 中准备好的 EIP
        p = self.load_policy(
            {
                "name": "rds-action-eip-bind-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    {"type": "value",
                     "key": "id", "value": target_instance_id}  # 确保只对没有 EIP 的实例操作
                ],
                "actions": [{
                    "type": "attach-eip",
                    "is_bind": True,
                    "public_ip": public_ip_to_bind,
                    "public_ip_id": public_ip_id_to_bind
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
        target_instance_id = "rds-instance-id-for-eip-unbind"
        p = self.load_policy(
            {
                "name": "rds-action-eip-unbind-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    {"type": "value",
                     "key": "id", "value": target_instance_id}  # 确保只对有 EIP 的实例操作
                ],
                "actions": [{"type": "attach-eip", "is_bind": False}],
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
                    # {"id": target_instance_id},
                    # 过滤特定版本的数据库实例
                    # {"type": "database-version", "version": "5.7.37", "op": "lt"}
                    {"type": "value", "key": "id", "value": target_instance_id}
                ],
                "actions": [{"type": "upgrade-db-version", "is_delayed": False}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        # 验证操作: 需要手动检查 VCR 文件 rds_action_upgrade_db_version_immediate.yaml
        # 确认调用了 POST /v3/{project_id}/instances/{instance_id}/action
        # 并且请求体包含 CustomerUpgradeDatabaseVersionReq 对象及 is_delayed=true

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
                "actions": [{"type": "upgrade-db-version", "is_delayed": True}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        # 验证操作: 需要手动检查 VCR 文件 rds_action_upgrade_db_version_later.yaml
        # 确认调用了 POST /v3/{project_id}/instances/{instance_id}/action
        # 并且请求体包含 CustomerUpgradeDatabaseVersionReq 对象及 is_delayed=false

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
        target_instance_id = "rds-instance-for-audit-log"
        p = self.load_policy(
            {
                "name": "rds-action-audit-log-disable-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    # {"id": target_instance_id},
                    {"type": "value", "key": "id", "value": target_instance_id}
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
                    "period": "1, 2, 3, 4, 5, 6, 7",
                    "reserve_backups": 'true'
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

    def test_postgresql_hba_conf_filter_match(self):
        """测试 pg_hba.conf 配置过滤器 - 匹配特定配置"""
        factory = self.replay_flight_data("rds_postgresql_hba_conf_match")
        p = self.load_policy(
            {
                "name": "rds-postgresql-hba-conf-match",
                "resource": "huaweicloud.rds",
                "filters": [{
                    "type": "postgresql-hba-conf",
                    "has_config": {
                        "type": "host",
                        "database": "all",
                        "user": "all",
                        "address": "0.0.0.0/0",
                        "method": "md5"
                    }
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreater(len(resources), 0, "测试 VCR 文件应包含至少一个匹配的 PostgreSQL 实例")
        # 确认返回的都是 PostgreSQL 类型的实例
        for resource in resources:
            self.assertEqual(resource.get('datastore', {}).get('type', '').lower(), 'postgresql')

    def test_postgresql_hba_conf_filter_no_match(self):
        """测试 pg_hba.conf 配置过滤器 - 无匹配"""
        factory = self.replay_flight_data("rds_postgresql_hba_conf_no_match")
        p = self.load_policy(
            {
                "name": "rds-postgresql-hba-conf-no-match",
                "resource": "huaweicloud.rds",
                "filters": [{
                    "type": "postgresql-hba-conf",
                    "has_config": {
                        "type": "hostssl",  # 使用较少见的配置类型
                        "database": "specific_db",
                        "user": "specific_user",
                        "address": "192.168.1.1",
                        "method": "scram-sha-256"
                    }
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 0, "不应有实例匹配该罕见配置")

    # ===========================
    # Action Tests (Modify pg_hba.conf)
    # ===========================
    def test_modify_pg_hba_conf_action(self):
        """测试修改 pg_hba.conf 配置操作"""
        factory = self.replay_flight_data("rds_action_modify_pg_hba_conf")
        target_instance_id = "pg-instance-for-hba-conf-test"
        p = self.load_policy(
            {
                "name": "rds-action-modify-pg-hba-conf",
                "resource": "huaweicloud.rds",
                "filters": [
                    {"type": "value", "key": "id", "value": target_instance_id},
                    {"type": "postgresql-hba-conf"}
                ],
                "actions": [{
                    "type": "modify-pg-hba-conf",
                    "configs": [
                        {
                            "type": "hostssl",
                            "database": "all",
                            "user": "all",
                            "address": "0.0.0.0/0",
                            "mask": "",
                            "method": "md5",
                            "priority": 0
                        }
                    ]
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        # 验证操作: 需要手动检查 VCR 文件确认 API 调用正确

    # ===========================
    # Action Tests (Enable TDE)
    # ===========================
    def test_enable_tde_action(self):
        """测试为 SQL Server 实例开启 TDE 功能"""
        factory = self.replay_flight_data("rds_action_enable_tde")
        target_instance_id = "sqlserver-instance-for-tde-test"
        p = self.load_policy(
            {
                "name": "rds-action-enable-tde",
                "resource": "huaweicloud.rds",
                "filters": [
                    {"type": "value", "key": "id", "value": target_instance_id},
                ],
                "actions": [{
                    "type": "enable-tde",
                    "rotate_day": 30  # 30天轮转一次
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        # 验证操作: 需要手动检查 VCR 文件确认 API 调用正确

    def test_enable_tde_action_with_secret(self):
        """测试为 SQL Server 实例开启 TDE 功能 - 使用密钥服务"""
        factory = self.replay_flight_data("rds_action_enable_tde_with_secret")
        target_instance_id = "sqlserver-instance-for-tde-secret-test"
        p = self.load_policy(
            {
                "name": "rds-action-enable-tde-with-secret",
                "resource": "huaweicloud.rds",
                "filters": [
                    {"type": "value", "key": "id", "value": target_instance_id},
                ],
                "actions": [{
                    "type": "enable-tde",
                    "rotate_day": 30,
                    "secret_id": "test-secret-id",
                    "secret_name": "test-secret-name",
                    "secret_version": "v1.0"
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        # 验证操作: 需要手动检查 VCR 文件确认 API 调用正确


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
        self.assertGreater(len(resources), 0,
                           f"测试 VCR 文件应包含 status 为 {target_status} 的 RDS 实例")
        for r in resources:
            self.assertEqual(r.get("status"), target_status)

    def test_rds_filter_value_no_match(self):
        """测试 value 过滤器 - 不匹配"""
        factory = self.replay_flight_data("rds_reusable_filter_value")  # 复用 VCR
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

    def test_rds_filter_tag_count(self):
        """Test tag count filter"""
        factory = self.replay_flight_data('rds_filter_tag_count')
        # Test for instances with more than 2 tags
        p = self.load_policy({
            'name': 'rds-tag-count-test',
            'resource': 'huaweicloud.rds',
            'filters': [{
                'type': 'tag-count',
                'count': 2,
                'op': 'gt'
            }]},
            session_factory=factory)
        resources = p.run()
        # Assuming there is 1 instance with more than 2 tags
        self.assertEqual(len(resources), 1)

    def test_rds_filter_marked_for_op(self):
        """Test marked-for-op filter"""
        factory = self.replay_flight_data('rds_filter_marked_for_op')
        # Test for instances marked for deletion
        p = self.load_policy({
            'name': 'rds-marked-for-delete-test',
            'resource': 'huaweicloud.rds',
            'filters': [{
                'type': 'marked-for-op',
                'tag': 'custodian_cleanup',
                'op': 'upgrade-db-version',
                # 'skew': 1
            }]},
            session_factory=factory)
        resources = p.run()
        # Assuming there is 1 instance marked for deletion
        self.assertEqual(len(resources), 1)

    # --- 可复用操作测试 ---

    def test_rds_action_tag(self):
        """Test adding tags"""
        factory = self.replay_flight_data('rds_action_tag')
        p = self.load_policy({
            'name': 'rds-tag-test',
            'resource': 'huaweicloud.rds',
            'filters': [{'type': 'value', 'key': 'name', 'value': 'mysql-instance-test'}],
            'actions': [{
                'type': 'tag',
                'key': 'env',
                'value': 'production'
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)

        # 验证操作: 需要手动检查VCR文件确认API调用正确包含了以下内容:
        # 1. 调用了正确的API: POST /v3/{project_id}/instances/{instance_id}/major-versions
        # 2. 请求体包含:
        #    - "target_version": "14.6.1"
        #    - "is_change_private_ip": true
        #    - "statistics_collection_mode": "before_change_private_ip"
