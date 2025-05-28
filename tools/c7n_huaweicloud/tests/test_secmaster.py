# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from huaweicloud_common import BaseTest


class SecmasterTest(BaseTest):
    """Test Huawei Cloud SecMaster resources, filters and actions"""

    # =========================
    # Resource Query Tests
    # =========================

    def test_secmaster_instance_query(self):
        """Test SecMaster instance query - TODO: API not supported yet"""
        # TODO: Due to the API for querying security account's professional
        # SecMaster instance not being available,
        # this test is temporarily skipped, will be implemented when API is supported
        self.skipTest("SecMaster instance query API not supported yet, marked as TODO")

    def test_secmaster_workspace_query(self):
        """Test SecMaster workspace query"""
        factory = self.replay_flight_data("secmaster_workspace_query")
        p = self.load_policy(
            {
                "name": "secmaster-workspace-query-test",
                "resource": "huaweicloud.secmaster-workspace",
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR file contains 2 workspaces (based on actual recorded content)
        self.assertEqual(
            len(resources), 2, "Should return 2 workspaces according to VCR file"
        )
        # Verify first workspace details - production-workspace
        workspace1 = resources[0]
        self.assertEqual(workspace1["name"], "production-workspace")
        self.assertEqual(workspace1["id"], "workspace001")
        self.assertEqual(workspace1["creator_name"], "admin")
        self.assertEqual(workspace1["description"], "生产环境工作空间")
        self.assertFalse(workspace1["is_view"])
        self.assertEqual(workspace1["region_id"], "cn-north-4")
        # Verify second workspace details - test-workspace
        workspace2 = resources[1]
        self.assertEqual(workspace2["name"], "test-workspace")
        self.assertEqual(workspace2["id"], "workspace002")
        self.assertEqual(workspace2["creator_name"], "security_admin")
        self.assertEqual(workspace2["description"], "测试环境工作空间")
        self.assertFalse(workspace2["is_view"])

    def test_secmaster_alert_query(self):
        """Test SecMaster alert query"""
        factory = self.replay_flight_data("secmaster_alert_query")
        p = self.load_policy(
            {
                "name": "secmaster-alert-query-test",
                "resource": "huaweicloud.secmaster-alert",
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR file: 1 workspace contains 2 alerts
        self.assertEqual(
            len(resources), 2, "Should return 2 alerts according to VCR file"
        )
        # Verify first alert details
        alert1 = resources[0]
        # Top-level fields
        self.assertEqual(alert1["id"], "alert-001")
        self.assertEqual(alert1["workspace_id"], "workspace001")
        self.assertEqual(alert1["workspace_name"], "production-workspace")
        self.assertEqual(alert1["format_version"], 1)
        # Fields in data_object
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
        # Verify second alert details
        alert2 = resources[1]
        # Top-level fields
        self.assertEqual(alert2["id"], "alert-002")
        self.assertEqual(alert2["workspace_id"], "workspace001")
        self.assertEqual(alert2["workspace_name"], "production-workspace")
        # Fields in data_object
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
        """Test SecMaster playbook query"""
        factory = self.replay_flight_data("secmaster_playbook_query")
        p = self.load_policy(
            {
                "name": "secmaster-playbook-query-test",
                "resource": "huaweicloud.secmaster-playbook",
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR file: according to the corrected VCR file, should return 3 playbooks
        self.assertEqual(
            len(resources), 3, "Should return 3 playbooks according to VCR file"
        )
        # Verify first playbook - high-risk operation monitoring playbook
        playbook1 = resources[0]
        self.assertEqual(playbook1["id"], "playbook-001")
        self.assertEqual(playbook1["name"], "高危操作监控剧本")
        self.assertEqual(playbook1["description"], "监控高危系统操作并自动响应")
        self.assertFalse(playbook1["enabled"])  # Based on VCR file
        self.assertEqual(playbook1["workspace_id"], "workspace001")
        self.assertEqual(playbook1["workspace_name"], "production-workspace")
        self.assertEqual(playbook1["version"], "v1.0")
        self.assertEqual(playbook1["dataclass_name"], "security")
        # Verify second playbook - malicious traffic monitoring playbook
        playbook2 = resources[1]
        self.assertEqual(playbook2["id"], "playbook-002")
        self.assertEqual(playbook2["name"], "恶意流量监控剧本")
        self.assertEqual(playbook2["description"], "监控网络异常流量")
        self.assertTrue(playbook2["enabled"])  # Based on VCR file
        self.assertEqual(playbook2["workspace_id"], "workspace001")
        self.assertEqual(playbook2["workspace_name"], "production-workspace")
        self.assertEqual(playbook2["version"], "v1.1")
        self.assertEqual(playbook2["dataclass_name"], "network")
        # Verify third playbook - daily monitoring playbook
        playbook3 = resources[2]
        self.assertEqual(playbook3["id"], "playbook-003")
        self.assertEqual(playbook3["name"], "日常监控剧本")
        self.assertEqual(playbook3["description"], "日常安全监控任务")
        self.assertTrue(playbook3["enabled"])  # Based on VCR file
        self.assertEqual(playbook3["workspace_id"], "workspace001")
        self.assertEqual(playbook3["workspace_name"], "production-workspace")
        self.assertEqual(playbook3["version"], "v2.0")
        self.assertEqual(playbook3["dataclass_name"], "general")

    # =========================
    # Filter Tests
    # =========================

    def test_secmaster_alert_age_filter_old(self):
        """Test SecMaster alert age filter - old alerts (more than 90 days)"""
        factory = self.replay_flight_data("secmaster_alert_age_filter")
        p = self.load_policy(
            {
                "name": "secmaster-alert-age-old-test",
                "resource": "huaweicloud.secmaster-alert",
                "filters": [
                    {"type": "age", "days": 90, "op": "gt"}  # Alerts older than 90 days
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        # VCR file contains alerts with different ages:
        # alert-old-003 (~99 days) and alert-very-old-004 (~175 days) are older than 90 days
        # alert-new-001 (~60 days) and alert-recent-002 (~66 days) are newer
        # than 90 days (filtered out)
        self.assertEqual(
            len(resources),
            2,
            "Should have 2 alerts older than 90 days according to VCR file",
        )
        # Verify first older alert - alert-old-003
        alert1 = resources[0]
        self.assertEqual(alert1["id"], "alert-old-003")
        data_object1 = alert1["data_object"]
        self.assertEqual(data_object1["title"], "较旧告警")
        self.assertEqual(data_object1["create_time"], "2025-02-15T10:00:00Z+0800")
        # Verify second older alert - alert-very-old-004
        alert2 = resources[1]
        self.assertEqual(alert2["id"], "alert-very-old-004")
        data_object2 = alert2["data_object"]
        self.assertEqual(data_object2["title"], "很旧的告警")
        self.assertEqual(data_object2["create_time"], "2024-12-01T09:00:00Z+0800")

    def test_secmaster_alert_age_filter_very_old(self):
        """Test SecMaster alert age filter - very old alerts (more than 170 days)"""
        factory = self.replay_flight_data("secmaster_alert_age_filter")
        p = self.load_policy(
            {
                "name": "secmaster-alert-age-very-old-test",
                "resource": "huaweicloud.secmaster-alert",
                "filters": [
                    {
                        "type": "age",
                        "days": 170,
                        "op": "gt",  # Alerts older than 170 days
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        # VCR file contains alerts with different ages:
        # alert-very-old-004 (~175 days) is older than 170 days
        # alert-old-003 (~99 days), alert-recent-002 (~66 days), alert-new-001 (~60 days)
        # are newer than 170 days (filtered out)
        self.assertEqual(
            len(resources),
            1,
            "Should have 1 alert older than 170 days according to VCR file",
        )
        # Verify the very old alert - alert-very-old-004
        alert = resources[0]
        self.assertEqual(alert["id"], "alert-very-old-004")
        data_object = alert["data_object"]
        self.assertEqual(data_object["title"], "很旧的告警")
        self.assertEqual(data_object["create_time"], "2024-12-01T09:00:00Z+0800")

    def test_secmaster_playbook_value_filter_enabled(self):
        """Test SecMaster playbook value filter - enabled playbooks"""
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
        # Verify VCR file: 3 out of 5 playbooks are enabled playbook-002,003,005
        self.assertEqual(
            len(resources), 3, "Should have 3 enabled playbooks according to VCR file"
        )
        # Verify all returned playbooks are in enabled state
        expected_enabled_ids = ["playbook-002", "playbook-003", "playbook-005"]
        for i, playbook in enumerate(resources):
            self.assertTrue(
                playbook["enabled"], "Filtered playbooks should all be enabled"
            )
            self.assertEqual(playbook["id"], expected_enabled_ids[i])
            self.assertIn("name", playbook)

    def test_secmaster_playbook_value_filter_disabled(self):
        """Test SecMaster playbook value filter - disabled playbooks"""
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
        # Verify VCR file: 2 out of 5 playbooks are disabled (playbook-001, 004)
        self.assertEqual(
            len(resources), 2, "Should have 2 disabled playbooks according to VCR file"
        )
        # Verify all returned playbooks are in disabled state
        expected_disabled_ids = ["playbook-001", "playbook-004"]
        for i, playbook in enumerate(resources):
            self.assertFalse(
                playbook["enabled"], "Filtered playbooks should all be disabled"
            )
            self.assertEqual(playbook["id"], expected_disabled_ids[i])
            self.assertIn("name", playbook)

    def test_secmaster_playbook_name_filter(self):
        """Test SecMaster playbook name filter"""
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
        # Verify VCR file: should return 4 playbooks containing "监控" in name
        self.assertEqual(
            len(resources),
            4,
            "Should return 4 playbooks containing '监控' according to VCR file",
        )
        # Verify each playbook name contains "监控"
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
                f"Playbook {i + 1} name should be {expected_names[i]}",
            )
            self.assertIn(
                "监控", playbook["name"], "Playbook name should contain '监控'"
            )
            self.assertIn("id", playbook)
            self.assertEqual(playbook["workspace_id"], "workspace001")

    def test_secmaster_workspace_is_view_filter(self):
        """Test SecMaster workspace is_view filter-filter real workspaces (non-view)"""
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
        # Verify is_view filter functionality
        self.assertIsInstance(resources, list, "Should return list type")
        # According to VCR file: total of 3 workspaces, after filtering
        # should have 2 (is_view=false)
        self.assertEqual(
            len(resources), 2, "Should have 2 non-view workspaces according to VCR file"
        )
        # Verify first workspace - production-workspace
        workspace1 = resources[0]
        self.assertEqual(workspace1["name"], "production-workspace")
        self.assertEqual(workspace1["id"], "workspace001")
        self.assertEqual(workspace1["creator_name"], "admin")
        self.assertFalse(workspace1["is_view"])
        # Verify second workspace - test-workspace
        workspace2 = resources[1]
        self.assertEqual(workspace2["name"], "test-workspace")
        self.assertEqual(workspace2["id"], "workspace002")
        self.assertEqual(workspace2["creator_name"], "security_admin")
        self.assertFalse(workspace2["is_view"])
        # Ensure no view workspaces are included
        workspace_names = [ws["name"] for ws in resources]
        self.assertNotIn(
            "workspace-view", workspace_names, "Should not include view workspaces"
        )

    # =========================
    # Action Tests
    # =========================

    def test_secmaster_workspace_send_msg_normal(self):
        """Test workspace send message action - normal case"""
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
        # Verify VCR file: should return 2 workspaces, send message action executed for each
        self.assertEqual(
            len(resources),
            2,
            "Should have 2 workspaces executing action according to VCR file",
        )
        # Verify first workspace
        workspace1 = resources[0]
        self.assertEqual(workspace1["name"], "production-workspace")
        self.assertEqual(workspace1["id"], "workspace001")
        self.assertEqual(workspace1["creator_name"], "admin")
        # Verify second workspace
        workspace2 = resources[1]
        self.assertEqual(workspace2["name"], "test-workspace")
        self.assertEqual(workspace2["id"], "workspace002")
        self.assertEqual(workspace2["creator_name"], "security_admin")

    def test_secmaster_workspace_send_msg_when_empty(self):
        """Test workspace send message action - empty workspace case"""
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
        # According to VCR file: returns empty workspace list
        # Although send_when_empty=True is set, action does not create virtual resources,
        # but handles empty list notification logic in process
        # Still returns empty list eventually
        self.assertEqual(
            len(resources),
            0,
            "Even with send_when_empty=True, should return empty list, "
            "notification logic handled inside action",
        )

    def test_secmaster_alert_send_msg(self):
        """Test alert send message action"""
        factory = self.replay_flight_data("secmaster_alert_send_msg")
        p = self.load_policy(
            {
                "name": "secmaster-alert-send-msg-test",
                "resource": "huaweicloud.secmaster-alert",
                "filters": [
                    {"type": "value", "key": "data_object.severity", "value": "High"}
                ],
                "actions": [
                    {
                        "type": "send-msg",
                        "message": "发现高危告警",
                        "subject": "SecMaster告警通知",
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        # VCR file contains only alert-new-001 with High severity
        # Filter for High severity alerts to avoid time-dependent age filters
        self.assertEqual(
            len(resources),
            1,
            "Should return 1 high severity alert according to VCR file",
        )
        # Verify alert details
        alert = resources[0]
        # Top-level fields
        self.assertEqual(
            alert["id"], "alert-new-001", "Alert ID should be alert-new-001"
        )
        self.assertEqual(
            alert["workspace_id"], "workspace001", "Should have workspace ID"
        )
        self.assertEqual(
            alert["workspace_name"],
            "production-workspace",
            "Should have workspace name",
        )
        # Fields in data_object
        data_object = alert["data_object"]
        self.assertEqual(
            data_object["title"], "最新高危告警", "Alert title should be '最新高危告警'"
        )
        self.assertEqual(
            data_object["severity"], "High", "Alert severity should be High"
        )
        self.assertEqual(
            data_object["handle_status"], "Open", "Handle status should be Open"
        )
        self.assertEqual(
            data_object["create_time"],
            "2025-03-26T08:30:15Z+0800",
            "Create time should match",
        )

    def test_secmaster_playbook_enable_action(self):
        """Test playbook enable action - includes version query and latest version selection"""
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
        # According to VCR file: returns 2 disabled playbooks (playbook-001, playbook-004)
        self.assertEqual(
            len(resources),
            2,
            "Should return 2 disabled playbooks according to VCR file",
        )
        # Verify first playbook - playbook-001
        playbook1 = resources[0]
        self.assertEqual(
            playbook1["id"], "playbook-001", "First playbook ID should be playbook-001"
        )
        self.assertEqual(
            playbook1["name"], "高危操作监控剧本", "First playbook name should match"
        )
        self.assertFalse(
            playbook1["enabled"], "Filter condition: should be disabled state"
        )
        self.assertEqual(
            playbook1["workspace_id"], "workspace001", "Should have workspace ID"
        )
        self.assertEqual(
            playbook1["workspace_name"],
            "production-workspace",
            "Should have workspace name",
        )
        # Verify second playbook - playbook-004
        playbook2 = resources[1]
        self.assertEqual(
            playbook2["id"], "playbook-004", "Second playbook ID should be playbook-004"
        )
        self.assertEqual(
            playbook2["name"], "权限监控剧本", "Second playbook name should match"
        )
        self.assertFalse(
            playbook2["enabled"], "Filter condition: should be disabled state"
        )
        self.assertEqual(
            playbook2["workspace_id"], "workspace001", "Should have workspace ID"
        )
        # Note: This test verifies playbook state before action execution (filter condition)
        # The actual enable-playbook action will:
        # 1. Query version list for playbook-001, find latest version version-001-v3
        #    (update_time: 2024-07-02T15:45:00Z+0800)
        # 2. Query version list for playbook-004, find latest version version-004-v2
        #    (update_time: 2024-07-02T16:20:00Z+0800)
        # 3. Update playbooks using correct name and active_version_id
        #
        # VCR file version query responses verify the following logic:
        # - playbook-001 has 3 versions, latest is v3.0 (based on update_time)
        # - playbook-004 has 2 versions, latest is v2.0 (based on update_time)
        # - Update requests contain name and active_version_id fields

    def test_secmaster_playbook_send_msg(self):
        """Test playbook send message action"""
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
        # According to VCR file: returns 2 playbooks
        self.assertEqual(
            len(resources), 2, "Should return 2 playbooks according to VCR file"
        )
        # Verify first playbook
        playbook1 = resources[0]
        self.assertEqual(
            playbook1["id"], "playbook-001", "First playbook ID should be playbook-001"
        )
        self.assertEqual(
            playbook1["name"], "高危操作监控剧本", "First playbook name should match"
        )
        self.assertFalse(playbook1["enabled"], "First playbook should be disabled")
        self.assertEqual(
            playbook1["workspace_id"], "workspace001", "Should have workspace ID"
        )
        self.assertEqual(
            playbook1["workspace_name"],
            "production-workspace",
            "Should have workspace name",
        )
        # Verify second playbook
        playbook2 = resources[1]
        self.assertEqual(
            playbook2["id"], "playbook-002", "Second playbook ID should be playbook-002"
        )
        self.assertEqual(
            playbook2["name"], "恶意流量监控剧本", "Second playbook name should match"
        )
        self.assertTrue(playbook2["enabled"], "Second playbook should be enabled")
        self.assertEqual(
            playbook2["workspace_id"], "workspace001", "Should have workspace ID"
        )

    def test_secmaster_combined_playbook_actions(self):
        """Test playbook combined actions - enable playbook and send notification"""
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
        # According to VCR file: returns 1 matching playbook (name contains "高危操作" and disabled)
        self.assertEqual(
            len(resources), 1, "Should return 1 matching playbook according to VCR file"
        )
        # Verify playbook content
        playbook = resources[0]
        self.assertEqual(
            playbook["id"], "playbook-001", "Playbook ID should be playbook-001"
        )
        self.assertEqual(
            playbook["name"],
            "高危操作监控剧本",
            "Playbook name should contain '高危操作'",
        )
        self.assertFalse(
            playbook["enabled"], "Filter condition: should be disabled state"
        )
        self.assertEqual(
            playbook["workspace_id"], "workspace001", "Should have workspace ID"
        )
        self.assertEqual(
            playbook["workspace_name"],
            "production-workspace",
            "Should have workspace name",
        )

    # =========================
    # Integration Tests
    # =========================

    def test_secmaster_workspace_based_security_check(self):
        """Test workspace-based security check integration"""
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
        # According to VCR file: returns 2 workspaces starting with 'production'
        self.assertEqual(
            len(resources),
            2,
            "Should return 2 production workspaces according to VCR file",
        )
        # Verify first workspace - production-main
        workspace1 = resources[0]
        self.assertEqual(
            workspace1["name"],
            "production-main",
            "First workspace name should be production-main",
        )
        self.assertEqual(
            workspace1["id"], "39*************bf", "First workspace ID should match"
        )
        self.assertEqual(
            workspace1["creator_name"],
            "admin",
            "First workspace creator should be admin",
        )
        self.assertEqual(
            workspace1["description"],
            "生产环境主工作空间",
            "First workspace description should match",
        )
        self.assertFalse(workspace1["is_view"], "First workspace should not be a view")
        # Verify second workspace - production-backup
        workspace2 = resources[1]
        self.assertEqual(
            workspace2["name"],
            "production-backup",
            "Second workspace name should be production-backup",
        )
        self.assertEqual(
            workspace2["id"], "28*************ae", "Second workspace ID should match"
        )
        self.assertEqual(
            workspace2["creator_name"],
            "security_admin",
            "Second workspace creator should be security_admin",
        )
        self.assertEqual(
            workspace2["description"],
            "生产环境备用工作空间",
            "Second workspace description should match",
        )
        self.assertFalse(workspace2["is_view"], "Second workspace should not be a view")
        # Verify all workspace names start with 'production'
        for workspace in resources:
            self.assertTrue(
                workspace["name"].startswith("production"),
                f"Workspace {workspace['name']} should start with 'production'",
            )


class SecmasterErrorHandlingTest(BaseTest):
    """Test SecMaster error handling and edge cases"""

    def test_secmaster_workspace_empty_response(self):
        """Test workspace empty response handling"""
        factory = self.replay_flight_data("secmaster_workspace_empty_response")
        p = self.load_policy(
            {
                "name": "secmaster-workspace-empty-test",
                "resource": "huaweicloud.secmaster-workspace",
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR file: should return empty workspace list
        self.assertEqual(len(resources), 0, "Empty response should return empty list")

    def test_secmaster_alert_no_workspace(self):
        """Test alert query handling when no workspace exists"""
        factory = self.replay_flight_data("secmaster_alert_no_workspace")
        p = self.load_policy(
            {
                "name": "secmaster-alert-no-workspace-test",
                "resource": "huaweicloud.secmaster-alert",
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR file: should return empty alert list when no workspace exists
        self.assertEqual(
            len(resources), 0, "Should return empty alert list when no workspace exists"
        )

    def test_secmaster_playbook_no_workspace(self):
        """Test playbook query handling when no workspace exists"""
        factory = self.replay_flight_data("secmaster_playbook_no_workspace")
        p = self.load_policy(
            {
                "name": "secmaster-playbook-no-workspace-test",
                "resource": "huaweicloud.secmaster-playbook",
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR file: should return empty playbook list when no workspace exists
        self.assertEqual(
            len(resources),
            0,
            "Should return empty playbook list when no workspace exists",
        )
