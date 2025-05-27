# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from huaweicloud_common import BaseTest


class SecmasterTest(BaseTest):
    """测试华为云SecMaster安全云脑资源、过滤器和操作"""

    # =========================
    # Resource Query Tests
    # =========================

    def test_secmaster_instance_query(self):
        """测试SecMaster实例查询 - TODO: API暂不支持"""
        # TODO: 由于查询安全账号是否购买专业版安全云脑实例的API暂不满足，
        # 此测试暂时跳过，等待API支持后再实现
        self.skipTest("SecMaster实例查询API暂不支持，列为TODO")

    def test_secmaster_workspace_query(self):
        """测试SecMaster工作空间查询"""
        factory = self.replay_flight_data("secmaster_workspace_query")
        p = self.load_policy(
            {
                "name": "secmaster-workspace-query-test",
                "resource": "huaweicloud.secmaster-workspace",
            },
            session_factory=factory,
        )
        resources = p.run()

        # 验证VCR文件中包含2个工作空间（基于录像带实际内容）
        self.assertEqual(len(resources), 2, "根据VCR文件应该返回2个工作空间")

        # 验证第一个工作空间的具体内容 - production-workspace
        workspace1 = resources[0]
        self.assertEqual(workspace1["name"], "production-workspace")
        self.assertEqual(workspace1["id"], "workspace001")
        self.assertEqual(workspace1["creator_name"], "admin")
        self.assertEqual(workspace1["description"], "生产环境工作空间")
        self.assertFalse(workspace1["is_view"])
        self.assertEqual(workspace1["region_id"], "cn-north-4")

        # 验证第二个工作空间的具体内容 - test-workspace
        workspace2 = resources[1]
        self.assertEqual(workspace2["name"], "test-workspace")
        self.assertEqual(workspace2["id"], "workspace002")
        self.assertEqual(workspace2["creator_name"], "security_admin")
        self.assertEqual(workspace2["description"], "测试环境工作空间")
        self.assertFalse(workspace2["is_view"])

    def test_secmaster_alert_query(self):
        """测试SecMaster告警查询"""
        factory = self.replay_flight_data("secmaster_alert_query")
        p = self.load_policy(
            {
                "name": "secmaster-alert-query-test",
                "resource": "huaweicloud.secmaster-alert",
            },
            session_factory=factory,
        )
        resources = p.run()

        # 验证VCR文件：1个工作空间包含2个告警
        self.assertEqual(len(resources), 2, "根据VCR文件应该返回2个告警")

        # 验证第一个告警的具体内容
        alert1 = resources[0]
        # 顶层字段
        self.assertEqual(alert1["id"], "alert-001")
        self.assertEqual(alert1["workspace_id"], "workspace001")
        self.assertEqual(alert1["workspace_name"], "production-workspace")
        self.assertEqual(alert1["format_version"], 1)

        # data_object中的字段
        data_object1 = alert1["data_object"]
        self.assertEqual(data_object1["id"], "alert-001")
        self.assertEqual(data_object1["title"], "高危端口扫描")
        self.assertEqual(data_object1["severity"], "High")
        self.assertEqual(data_object1["handle_status"], "Open")
        self.assertEqual(data_object1["description"], "检测到高危端口扫描行为")
        self.assertEqual(data_object1["confidence"], 95)
        self.assertEqual(data_object1["criticality"], 80)
        self.assertEqual(data_object1["count"], 1)
        self.assertEqual(data_object1["verification_state"], "Unknown")

        # 验证第二个告警的具体内容
        alert2 = resources[1]
        # 顶层字段
        self.assertEqual(alert2["id"], "alert-002")
        self.assertEqual(alert2["workspace_id"], "workspace001")
        self.assertEqual(alert2["workspace_name"], "production-workspace")

        # data_object中的字段
        data_object2 = alert2["data_object"]
        self.assertEqual(data_object2["id"], "alert-002")
        self.assertEqual(data_object2["title"], "权限提升尝试")
        self.assertEqual(data_object2["severity"], "Medium")
        self.assertEqual(data_object2["handle_status"], "Block")
        self.assertEqual(data_object2["description"], "检测到异常权限提升尝试")
        self.assertEqual(data_object2["confidence"], 85)
        self.assertEqual(data_object2["criticality"], 70)
        self.assertEqual(data_object2["count"], 3)
        self.assertEqual(data_object2["verification_state"], "True_Positive")

    def test_secmaster_playbook_query(self):
        """测试SecMaster剧本查询"""
        factory = self.replay_flight_data("secmaster_playbook_query")
        p = self.load_policy(
            {
                "name": "secmaster-playbook-query-test",
                "resource": "huaweicloud.secmaster-playbook",
            },
            session_factory=factory,
        )
        resources = p.run()

        # 验证VCR文件：根据修正后的VCR文件，应该返回3个剧本
        self.assertEqual(len(resources), 3, "根据VCR文件应该返回3个剧本")

        # 验证第一个剧本 - 高危操作监控剧本
        playbook1 = resources[0]
        self.assertEqual(playbook1["id"], "playbook-001")
        self.assertEqual(playbook1["name"], "高危操作监控剧本")
        self.assertEqual(playbook1["description"], "监控高危系统操作并自动响应")
        self.assertFalse(playbook1["enabled"])  # 根据VCR文件
        self.assertEqual(playbook1["workspace_id"], "workspace001")
        self.assertEqual(playbook1["workspace_name"], "production-workspace")
        self.assertEqual(playbook1["version"], "v1.0")
        self.assertEqual(playbook1["dataclass_name"], "security")

        # 验证第二个剧本 - 恶意流量监控剧本
        playbook2 = resources[1]
        self.assertEqual(playbook2["id"], "playbook-002")
        self.assertEqual(playbook2["name"], "恶意流量监控剧本")
        self.assertEqual(playbook2["description"], "监控网络异常流量")
        self.assertTrue(playbook2["enabled"])  # 根据VCR文件
        self.assertEqual(playbook2["workspace_id"], "workspace001")
        self.assertEqual(playbook2["workspace_name"], "production-workspace")
        self.assertEqual(playbook2["version"], "v1.1")
        self.assertEqual(playbook2["dataclass_name"], "network")

        # 验证第三个剧本 - 日常监控剧本
        playbook3 = resources[2]
        self.assertEqual(playbook3["id"], "playbook-003")
        self.assertEqual(playbook3["name"], "日常监控剧本")
        self.assertEqual(playbook3["description"], "日常安全监控任务")
        self.assertTrue(playbook3["enabled"])  # 根据VCR文件
        self.assertEqual(playbook3["workspace_id"], "workspace001")
        self.assertEqual(playbook3["workspace_name"], "production-workspace")
        self.assertEqual(playbook3["version"], "v2.0")
        self.assertEqual(playbook3["dataclass_name"], "general")

    # =========================
    # Filter Tests
    # =========================

    def test_secmaster_alert_age_filter_recent(self):
        """测试SecMaster告警年龄过滤器 - 较新的告警（90天以内）"""
        factory = self.replay_flight_data("secmaster_alert_age_filter")
        p = self.load_policy(
            {
                "name": "secmaster-alert-age-recent-test",
                "resource": "huaweicloud.secmaster-alert",
                "filters": [{"type": "age", "days": 90, "op": "lt"}],  # 90天以内的告警
            },
            session_factory=factory,
        )
        resources = p.run()

        # 基于2025年5月25日基准：
        # alert-new-001 (2025-03-26) 约60天前 < 90天
        # alert-recent-002 (2025-03-20) 约66天前 < 90天
        # alert-old-003 (2025-02-15) 约99天前 > 90天 (不包含)
        # alert-very-old-004 (2024-12-01) 约175天前 > 90天 (不包含)
        self.assertEqual(len(resources), 2, "根据VCR文件应该有2个90天以内的告警")

        # 验证第一个告警 - alert-new-001
        alert1 = resources[0]
        self.assertEqual(alert1["id"], "alert-new-001")
        data_object1 = alert1["data_object"]
        self.assertEqual(data_object1["title"], "最新高危告警")
        self.assertEqual(data_object1["create_time"], "2025-03-26T08:30:15Z+0800")

        # 验证第二个告警 - alert-recent-002
        alert2 = resources[1]
        self.assertEqual(alert2["id"], "alert-recent-002")
        data_object2 = alert2["data_object"]
        self.assertEqual(data_object2["title"], "近期告警")
        self.assertEqual(data_object2["create_time"], "2025-03-20T14:22:30Z+0800")

    def test_secmaster_alert_age_filter_old(self):
        """测试SecMaster告警年龄过滤器 - 较旧的告警（90天以前）"""
        factory = self.replay_flight_data("secmaster_alert_age_filter")
        p = self.load_policy(
            {
                "name": "secmaster-alert-age-old-test",
                "resource": "huaweicloud.secmaster-alert",
                "filters": [
                    {
                        "type": "age",
                        "days": 90,
                        "op": "gte",  # 90天以前的告警（大于等于90天）
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()

        # 基于2025年5月25日基准：
        # alert-old-003 (2025-02-15) 约99天前 >= 90天
        # alert-very-old-004 (2024-12-01) 约175天前 >= 90天
        self.assertEqual(len(resources), 2, "根据VCR文件应该有2个90天以前的告警")

        # 验证第一个告警 - alert-old-003
        alert1 = resources[0]
        self.assertEqual(alert1["id"], "alert-old-003")
        data_object1 = alert1["data_object"]
        self.assertEqual(data_object1["title"], "较旧告警")
        self.assertEqual(data_object1["create_time"], "2025-02-15T10:00:00Z+0800")

        # 验证第二个告警 - alert-very-old-004
        alert2 = resources[1]
        self.assertEqual(alert2["id"], "alert-very-old-004")
        data_object2 = alert2["data_object"]
        self.assertEqual(data_object2["title"], "很旧的告警")
        self.assertEqual(data_object2["create_time"], "2024-12-01T09:00:00Z+0800")

    def test_secmaster_playbook_value_filter_enabled(self):
        """测试SecMaster剧本值过滤器 - 已启用的剧本"""
        factory = self.replay_flight_data("secmaster_playbook_value_filter")
        p = self.load_policy(
            {
                "name": "secmaster-playbook-enabled-test",
                "resource": "huaweicloud.secmaster-playbook",
                "filters": [{"type": "value", "key": "enabled", "value": True}],
            },
            session_factory=factory,
        )
        resources = p.run()

        # 验证VCR文件：5个剧本中有3个启用的（playbook-002, 003, 005）
        self.assertEqual(len(resources), 3, "根据VCR文件应该有3个启用的剧本")

        # 验证所有返回的剧本都是启用状态
        expected_enabled_ids = ["playbook-002", "playbook-003", "playbook-005"]
        for i, playbook in enumerate(resources):
            self.assertTrue(playbook["enabled"], "过滤后的剧本应该都是启用状态")
            self.assertEqual(playbook["id"], expected_enabled_ids[i])
            self.assertIn("name", playbook)

    def test_secmaster_playbook_value_filter_disabled(self):
        """测试SecMaster剧本值过滤器 - 未启用的剧本"""
        factory = self.replay_flight_data("secmaster_playbook_value_filter")
        p = self.load_policy(
            {
                "name": "secmaster-playbook-disabled-test",
                "resource": "huaweicloud.secmaster-playbook",
                "filters": [{"type": "value", "key": "enabled", "value": False}],
            },
            session_factory=factory,
        )
        resources = p.run()

        # 验证VCR文件：5个剧本中有2个未启用的（playbook-001, 004）
        self.assertEqual(len(resources), 2, "根据VCR文件应该有2个未启用的剧本")

        # 验证所有返回的剧本都是未启用状态
        expected_disabled_ids = ["playbook-001", "playbook-004"]
        for i, playbook in enumerate(resources):
            self.assertFalse(playbook["enabled"], "过滤后的剧本应该都是未启用状态")
            self.assertEqual(playbook["id"], expected_disabled_ids[i])
            self.assertIn("name", playbook)

    def test_secmaster_playbook_name_filter(self):
        """测试SecMaster剧本名称过滤器"""
        factory = self.replay_flight_data("secmaster_playbook_name_filter")
        p = self.load_policy(
            {
                "name": "secmaster-playbook-name-test",
                "resource": "huaweicloud.secmaster-playbook",
                "filters": [
                    {"type": "value", "key": "name", "value": "*监控*", "op": "glob"}
                ],
            },
            session_factory=factory,
        )
        resources = p.run()

        # 验证VCR文件：应该返回4个包含"监控"字样的剧本
        self.assertEqual(len(resources), 4, "根据VCR文件应该返回4个包含'监控'的剧本")

        # 验证每个剧本名称都包含"监控"
        expected_names = [
            "高危操作监控剧本",
            "恶意流量监控剧本",
            "日常监控剧本",
            "权限监控剧本",
        ]

        for i, playbook in enumerate(resources):
            self.assertEqual(
                playbook["name"],
                expected_names[i],
                f"第{i + 1}个剧本名称应该是{expected_names[i]}",
            )
            self.assertIn("监控", playbook["name"], "剧本名称应该包含'监控'")
            self.assertIn("id", playbook)
            self.assertEqual(playbook["workspace_id"], "workspace001")

    def test_secmaster_workspace_is_view_filter(self):
        """测试SecMaster工作空间is_view过滤器 - 过滤真正的工作空间（非视图）"""
        factory = self.replay_flight_data("secmaster_workspace_is_view_filter")
        p = self.load_policy(
            {
                "name": "secmaster-workspace-is-view-test",
                "resource": "huaweicloud.secmaster-workspace",
                "filters": [{"type": "value", "key": "is_view", "value": False}],
            },
            session_factory=factory,
        )
        resources = p.run()

        # 验证is_view过滤器功能
        self.assertIsInstance(resources, list, "应该返回列表类型")

        # 根据VCR文件：总共3个工作空间，过滤后应该有2个（is_view=false）
        self.assertEqual(len(resources), 2, "根据VCR文件应该有2个非视图工作空间")

        # 验证第一个工作空间 - production-workspace
        workspace1 = resources[0]
        self.assertEqual(workspace1["name"], "production-workspace")
        self.assertEqual(workspace1["id"], "workspace001")
        self.assertEqual(workspace1["creator_name"], "admin")
        self.assertFalse(workspace1["is_view"])

        # 验证第二个工作空间 - test-workspace
        workspace2 = resources[1]
        self.assertEqual(workspace2["name"], "test-workspace")
        self.assertEqual(workspace2["id"], "workspace002")
        self.assertEqual(workspace2["creator_name"], "security_admin")
        self.assertFalse(workspace2["is_view"])

        # 确保没有包含视图工作空间
        workspace_names = [ws["name"] for ws in resources]
        self.assertNotIn("workspace-view", workspace_names, "不应该包含视图工作空间")

    # =========================
    # Action Tests
    # =========================

    def test_secmaster_workspace_send_msg_normal(self):
        """测试工作空间发送消息动作 - 正常情况"""
        factory = self.replay_flight_data("secmaster_workspace_send_msg")
        p = self.load_policy(
            {
                "name": "secmaster-workspace-send-msg-test",
                "resource": "huaweicloud.secmaster-workspace",
                "actions": [
                    {
                        "type": "send-msg",
                        "message": "工作空间状态检查完成",
                        "subject": "SecMaster工作空间检查",
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()

        # 验证VCR文件：应该返回2个工作空间，发送消息动作对每个都执行
        self.assertEqual(len(resources), 2, "根据VCR文件应该有2个工作空间执行动作")

        # 验证第一个工作空间
        workspace1 = resources[0]
        self.assertEqual(workspace1["name"], "production-workspace")
        self.assertEqual(workspace1["id"], "workspace001")
        self.assertEqual(workspace1["creator_name"], "admin")

        # 验证第二个工作空间
        workspace2 = resources[1]
        self.assertEqual(workspace2["name"], "test-workspace")
        self.assertEqual(workspace2["id"], "workspace002")
        self.assertEqual(workspace2["creator_name"], "security_admin")

    def test_secmaster_workspace_send_msg_when_empty(self):
        """测试工作空间发送消息动作 - 空工作空间情况"""
        factory = self.replay_flight_data("secmaster_workspace_send_msg_empty")
        p = self.load_policy(
            {
                "name": "secmaster-workspace-send-msg-empty-test",
                "resource": "huaweicloud.secmaster-workspace",
                "actions": [
                    {
                        "type": "send-msg",
                        "message": "警告：未发现任何SecMaster工作空间",
                        "subject": "SecMaster工作空间缺失警告",
                        "send_when_empty": True,
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()

        # 根据VCR文件：返回空工作空间列表
        # 设置了send_when_empty=True，但action不创建虚拟资源，而是在process中处理空列表的通知逻辑
        # 最终仍然返回空列表
        self.assertEqual(
            len(resources),
            0,
            "即使send_when_empty=True，也应该返回空列表，通知逻辑在action内部处理",
        )

    def test_secmaster_alert_send_msg(self):
        """测试告警发送消息动作"""
        factory = self.replay_flight_data("secmaster_alert_send_msg")
        p = self.load_policy(
            {
                "name": "secmaster-alert-send-msg-test",
                "resource": "huaweicloud.secmaster-alert",
                "filters": [{"type": "age", "days": 70, "op": "lt"}],  # 70天以内的告警
                "actions": [
                    {
                        "type": "send-msg",
                        "message": "发现较新的告警",
                        "subject": "SecMaster告警通知",
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()

        # 基于2025年5月25日基准：
        # alert-new-001 (2025-03-26) 约60天前 < 70天 (包含)
        self.assertEqual(len(resources), 1, "根据VCR文件应该返回1个70天以内的告警")

        # 验证告警的具体内容
        alert = resources[0]
        # 顶层字段
        self.assertEqual(alert["id"], "alert-new-001", "告警ID应该是alert-new-001")
        self.assertEqual(alert["workspace_id"], "workspace001", "应该有工作空间ID")
        self.assertEqual(
            alert["workspace_name"], "production-workspace", "应该有工作空间名称"
        )

        # data_object中的字段
        data_object = alert["data_object"]
        self.assertEqual(
            data_object["title"], "最新高危告警", "告警标题应该是'最新高危告警'"
        )
        self.assertEqual(data_object["severity"], "High", "告警级别应该是High")
        self.assertEqual(data_object["handle_status"], "Open", "处理状态应该是Open")
        self.assertEqual(
            data_object["create_time"], "2025-03-26T08:30:15Z+0800", "创建时间应该匹配"
        )

    def test_secmaster_playbook_enable_action(self):
        """测试剧本开启动作"""
        factory = self.replay_flight_data("secmaster_playbook_enable_action")
        p = self.load_policy(
            {
                "name": "secmaster-playbook-enable-test",
                "resource": "huaweicloud.secmaster-playbook",
                "filters": [{"type": "value", "key": "enabled", "value": False}],
                "actions": [{"type": "enable-playbook"}],
            },
            session_factory=factory,
        )
        resources = p.run()

        # 根据VCR文件：返回2个未启用的剧本（playbook-001, playbook-004）
        self.assertEqual(len(resources), 2, "根据VCR文件应该返回2个未启用的剧本")

        # 验证第一个剧本
        playbook1 = resources[0]
        self.assertEqual(
            playbook1["id"], "playbook-001", "第一个剧本ID应该是playbook-001"
        )
        self.assertEqual(
            playbook1["name"], "高危操作监控剧本", "第一个剧本名称应该匹配"
        )
        self.assertFalse(playbook1["enabled"], "过滤条件：应该是未启用状态")
        self.assertEqual(playbook1["workspace_id"], "workspace001", "应该有工作空间ID")
        self.assertEqual(
            playbook1["workspace_name"], "production-workspace", "应该有工作空间名称"
        )

        # 验证第二个剧本
        playbook2 = resources[1]
        self.assertEqual(
            playbook2["id"], "playbook-004", "第二个剧本ID应该是playbook-004"
        )
        self.assertEqual(playbook2["name"], "权限监控剧本", "第二个剧本名称应该匹配")
        self.assertFalse(playbook2["enabled"], "过滤条件：应该是未启用状态")
        self.assertEqual(playbook2["workspace_id"], "workspace001", "应该有工作空间ID")

    def test_secmaster_playbook_send_msg(self):
        """测试剧本发送消息动作"""
        factory = self.replay_flight_data("secmaster_playbook_send_msg")
        p = self.load_policy(
            {
                "name": "secmaster-playbook-send-msg-test",
                "resource": "huaweicloud.secmaster-playbook",
                "actions": [
                    {
                        "type": "send-msg",
                        "message": "剧本状态审计完成",
                        "subject": "SecMaster剧本审计报告",
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()

        # 根据VCR文件：返回2个剧本
        self.assertEqual(len(resources), 2, "根据VCR文件应该返回2个剧本")

        # 验证第一个剧本
        playbook1 = resources[0]
        self.assertEqual(
            playbook1["id"], "playbook-001", "第一个剧本ID应该是playbook-001"
        )
        self.assertEqual(
            playbook1["name"], "高危操作监控剧本", "第一个剧本名称应该匹配"
        )
        self.assertFalse(playbook1["enabled"], "第一个剧本应该是未启用状态")
        self.assertEqual(playbook1["workspace_id"], "workspace001", "应该有工作空间ID")
        self.assertEqual(
            playbook1["workspace_name"], "production-workspace", "应该有工作空间名称"
        )

        # 验证第二个剧本
        playbook2 = resources[1]
        self.assertEqual(
            playbook2["id"], "playbook-002", "第二个剧本ID应该是playbook-002"
        )
        self.assertEqual(
            playbook2["name"], "恶意流量监控剧本", "第二个剧本名称应该匹配"
        )
        self.assertTrue(playbook2["enabled"], "第二个剧本应该是启用状态")
        self.assertEqual(playbook2["workspace_id"], "workspace001", "应该有工作空间ID")

    def test_secmaster_combined_playbook_actions(self):
        """测试剧本组合动作 - 开启剧本并发送通知"""
        factory = self.replay_flight_data("secmaster_playbook_combined_actions")
        p = self.load_policy(
            {
                "name": "secmaster-playbook-combined-test",
                "resource": "huaweicloud.secmaster-playbook",
                "filters": [
                    {
                        "type": "value",
                        "key": "name",
                        "value": "*高危操作*",
                        "op": "glob",
                    },
                    {"type": "value", "key": "enabled", "value": False},
                ],
                "actions": [
                    {"type": "enable-playbook"},
                    {
                        "type": "send-msg",
                        "message": "高危操作监控剧本已自动开启",
                        "subject": "SecMaster剧本状态变更",
                    },
                ],
            },
            session_factory=factory,
        )
        resources = p.run()

        # 根据VCR文件：返回1个符合条件的剧本（名称包含"高危操作"且未启用）
        self.assertEqual(len(resources), 1, "根据VCR文件应该返回1个符合条件的剧本")

        # 验证剧本内容
        playbook = resources[0]
        self.assertEqual(playbook["id"], "playbook-001", "剧本ID应该是playbook-001")
        self.assertEqual(
            playbook["name"], "高危操作监控剧本", "剧本名称应该包含'高危操作'"
        )
        self.assertFalse(playbook["enabled"], "过滤条件：应该是未启用状态")
        self.assertEqual(playbook["workspace_id"], "workspace001", "应该有工作空间ID")
        self.assertEqual(
            playbook["workspace_name"], "production-workspace", "应该有工作空间名称"
        )

    # =========================
    # Integration Tests
    # =========================

    def test_secmaster_workspace_based_security_check(self):
        """测试基于工作空间的安全检查集成"""
        factory = self.replay_flight_data("secmaster_workspace_security_check")
        p = self.load_policy(
            {
                "name": "workspace-based-security-check",
                "resource": "huaweicloud.secmaster-workspace",
                "filters": [
                    {
                        "type": "value",
                        "key": "name",
                        "value": "production*",
                        "op": "glob",
                    }
                ],
                "actions": [
                    {
                        "type": "send-msg",
                        "message": "生产环境工作空间安全检查完成",
                        "subject": "生产环境SecMaster安全检查",
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()

        # 根据VCR文件：返回2个以'production'开头的工作空间
        self.assertEqual(len(resources), 2, "根据VCR文件应该返回2个production工作空间")

        # 验证第一个工作空间 - production-main
        workspace1 = resources[0]
        self.assertEqual(
            workspace1["name"],
            "production-main",
            "第一个工作空间名称应该是production-main",
        )
        self.assertEqual(
            workspace1["id"], "39*************bf", "第一个工作空间ID应该匹配"
        )
        self.assertEqual(
            workspace1["creator_name"], "admin", "第一个工作空间创建者应该是admin"
        )
        self.assertEqual(
            workspace1["description"],
            "生产环境主工作空间",
            "第一个工作空间描述应该匹配",
        )
        self.assertFalse(workspace1["is_view"], "第一个工作空间不应该是视图")

        # 验证第二个工作空间 - production-backup
        workspace2 = resources[1]
        self.assertEqual(
            workspace2["name"],
            "production-backup",
            "第二个工作空间名称应该是production-backup",
        )
        self.assertEqual(
            workspace2["id"], "28*************ae", "第二个工作空间ID应该匹配"
        )
        self.assertEqual(
            workspace2["creator_name"],
            "security_admin",
            "第二个工作空间创建者应该是security_admin",
        )
        self.assertEqual(
            workspace2["description"],
            "生产环境备用工作空间",
            "第二个工作空间描述应该匹配",
        )
        self.assertFalse(workspace2["is_view"], "第二个工作空间不应该是视图")

        # 验证所有工作空间名称都以'production'开头
        for workspace in resources:
            self.assertTrue(
                workspace["name"].startswith("production"),
                f"工作空间 {workspace['name']} 应该以'production'开头",
            )


class SecmasterErrorHandlingTest(BaseTest):
    """测试SecMaster错误处理和边界情况"""

    def test_secmaster_workspace_empty_response(self):
        """测试工作空间空响应处理"""
        factory = self.replay_flight_data("secmaster_workspace_empty_response")
        p = self.load_policy(
            {
                "name": "secmaster-workspace-empty-test",
                "resource": "huaweicloud.secmaster-workspace",
            },
            session_factory=factory,
        )
        resources = p.run()

        # 验证VCR文件：应该返回空的工作空间列表
        self.assertEqual(len(resources), 0, "空响应应该返回空列表")

    def test_secmaster_alert_no_workspace(self):
        """测试告警查询在没有工作空间时的处理"""
        factory = self.replay_flight_data("secmaster_alert_no_workspace")
        p = self.load_policy(
            {
                "name": "secmaster-alert-no-workspace-test",
                "resource": "huaweicloud.secmaster-alert",
            },
            session_factory=factory,
        )
        resources = p.run()

        # 验证VCR文件：没有工作空间时应该返回空的告警列表
        self.assertEqual(len(resources), 0, "没有工作空间时应该返回空的告警列表")

    def test_secmaster_playbook_no_workspace(self):
        """测试剧本查询在没有工作空间时的处理"""
        factory = self.replay_flight_data("secmaster_playbook_no_workspace")
        p = self.load_policy(
            {
                "name": "secmaster-playbook-no-workspace-test",
                "resource": "huaweicloud.secmaster-playbook",
            },
            session_factory=factory,
        )
        resources = p.run()

        # 验证VCR文件：没有工作空间时应该返回空的剧本列表
        self.assertEqual(len(resources), 0, "没有工作空间时应该返回空的剧本列表")
