from huaweicloud_common import BaseTest


class AomTest(BaseTest):
    """华为云AOM告警规则资源测试类

    测试AOM告警规则相关的查询、过滤和操作功能
    """

    def test_alarm_query(self):
        """测试查询AOM告警规则列表"""
        factory = self.replay_flight_data("aom_alarm_query")
        p = self.load_policy(
            {"name": "list_aom_alarms", "resource": "huaweicloud.aom-alarm"},
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_alarm_rule_filter(self):
        """测试使用告警规则过滤器根据名称过滤告警规则"""
        factory = self.replay_flight_data("aom_alarm_rule_filter")
        p = self.load_policy(
            {
                "name": "filter_aom_alarms",
                "resource": "huaweicloud.aom-alarm",
                "filters": [
                    {
                        "type": "alarm-rule",
                        "key": "alarm_rule_name",
                        "value": "test-alarm"
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["alarm_rule_name"], "test-alarm")

    def test_alarm_rule_filter_by_status(self):
        """测试使用告警规则过滤器根据启用状态过滤告警规则"""
        factory = self.replay_flight_data("aom_alarm_rule_filter_by_status")
        p = self.load_policy(
            {
                "name": "filter_aom_alarms_by_status",
                "resource": "huaweicloud.aom-alarm",
                "filters": [
                    {
                        "type": "alarm-rule",
                        "key": "alarm_rule_enable",
                        "value": True
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertTrue(resources[0]["alarm_rule_enable"])

    def test_alarm_rule_filter_by_type(self):
        """测试使用告警规则过滤器根据告警类型过滤告警规则"""
        factory = self.replay_flight_data("aom_alarm_rule_filter_by_type")
        p = self.load_policy(
            {
                "name": "filter_aom_alarms_by_type",
                "resource": "huaweicloud.aom-alarm",
                "filters": [
                    {
                        "type": "alarm-rule",
                        "key": "alarm_rule_type",
                        "value": "metric"
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["alarm_rule_type"], "metric")

    def test_delete_alarm_rule(self):
        """测试删除告警规则操作"""
        factory = self.replay_flight_data("aom_delete_alarm_rule")
        p = self.load_policy(
            {
                "name": "delete_aom_alarm",
                "resource": "huaweicloud.aom-alarm",
                "filters": [
                    {
                        "type": "alarm-rule",
                        "key": "alarm_rule_name",
                        "value": "aom_alarm_rule_1"
                    }
                ],
                "actions": ["delete"],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["alarm_rule_name"], "aom_alarm_rule_1")

    def test_update_alarm_rule_name(self):
        """测试更新告警规则名称操作"""
        factory = self.replay_flight_data("aom_update_alarm_rule_name")
        p = self.load_policy(
            {
                "name": "update_aom_alarm_name",
                "resource": "huaweicloud.aom-alarm",
                "filters": [
                    {
                        "type": "alarm-rule",
                        "key": "alarm_rule_name",
                        "value": "aom_alarm_rule_1"
                    }
                ],
                "actions": [
                    {
                        "type": "update",
                        "alarm_rule_name": "updated-alarm-name"
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["alarm_rule_name"], "aom_alarm_rule_1")

    def test_update_alarm_rule_enable(self):
        """测试更新告警规则启用状态操作"""
        factory = self.replay_flight_data("aom_update_alarm_rule_enable")
        p = self.load_policy(
            {
                "name": "update_aom_alarm_enable",
                "resource": "huaweicloud.aom-alarm",
                "filters": [
                    {
                        "type": "alarm-rule",
                        "key": "alarm_rule_name",
                        "value": "aom_alarm_rule_1"
                    }
                ],
                "actions": [
                    {
                        "type": "update",
                        "alarm_rule_enable": False
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["alarm_rule_name"], "aom_alarm_rule_1")

    def test_update_alarm_rule_notifications(self):
        """测试更新告警规则通知配置操作"""
        factory = self.replay_flight_data("aom_update_alarm_rule_notifications")
        p = self.load_policy(
            {
                "name": "update_aom_alarm_notifications",
                "resource": "huaweicloud.aom-alarm",
                "filters": [
                    {
                        "type": "alarm-rule",
                        "key": "alarm_rule_id",
                        "value": 1
                    }
                ],
                "actions": [
                    {
                        "type": "update",
                        "alarm_notifications": {
                            "notification_type": "direct",
                            "notify_triggered": True,
                            "notify_resolved": False,
                            "route_group_enable": False,
                            "notification_enable": True,
                            "bind_notification_rule_id": "notification-rule-id",
                            "notify_frequency": 0
                        }
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["alarm_rule_id"], 1)

    def test_update_metric_alarm_rule(self):
        """测试更新指标类告警规则操作"""
        factory = self.replay_flight_data("aom_update_metric_alarm_rule")
        p = self.load_policy(
            {
                "name": "update_metric_aom_alarm",
                "resource": "huaweicloud.aom-alarm",
                "filters": [
                    {
                        "type": "alarm-rule",
                        "key": "alarm_rule_id",
                        "value": 1
                    }
                ],
                "actions": [
                    {
                        "type": "update",
                        "alarm_rule_type": "metric",
                        "metric_alarm_spec": {
                            "monitor_type": "all_metric",
                            "alarm_tags": [
                                {
                                    "key": "tag_key",
                                    "value": "tag_value"
                                }
                            ],
                            "trigger_conditions": [
                                {
                                    "metric_name": "cpu_usage",
                                    "metric_namespace": "PAAS.CONTAINER",
                                    "period": 60000,
                                    "statistic": "average",
                                    "comparison_operator": ">",
                                    "threshold": 80,
                                    "filter": "resource_group_id=default_resource_group_id",
                                    "count": 3,
                                    "severity": 2
                                }
                            ]
                        }
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["alarm_rule_id"], 1)

    def test_add_metric_alarm_rule(self):
        """测试添加新的指标类告警规则操作"""
        factory = self.replay_flight_data("aom_add_metric_alarm_rule")
        p = self.load_policy(
            {
                "name": "add_metric_aom_alarm",
                "resource": "huaweicloud.aom-alarm",
                "actions": [
                    {
                        "type": "add",
                        "alarm_rule_name": "new-metric-alarm",
                        "alarm_rule_description": "新的指标告警规则",
                        "alarm_rule_type": "metric",
                        "alarm_rule_enable": True,
                        "alarm_notifications": {
                            "notification_type": "direct",
                            "route_group_enable": False,
                            "notification_enable": True,
                            "bind_notification_rule_id": "notification-rule-id",
                            "notify_resolved": False,
                            "notify_triggered": True,
                            "notify_frequency": 0
                        },
                        "metric_alarm_spec": {
                            "monitor_type": "all_metric",
                            "alarm_tags": [
                                {
                                    "key": "tag_key",
                                    "value": "tag_value"
                                }
                            ],
                            "trigger_conditions": [
                                {
                                    "metric_name": "cpu_usage",
                                    "metric_namespace": "PAAS.CONTAINER",
                                    "period": 60000,
                                    "statistic": "average",
                                    "comparison_operator": ">",
                                    "threshold": 80,
                                    "filter": "resource_group_id=default_resource_group_id",
                                    "count": 3,
                                    "severity": 2
                                }
                            ]
                        }
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["alarm_rule_name"], "new-metric-alarm")

    def test_add_event_alarm_rule(self):
        """测试添加新的事件类告警规则操作"""
        factory = self.replay_flight_data("aom_add_event_alarm_rule")
        p = self.load_policy(
            {
                "name": "add_event_aom_alarm",
                "resource": "huaweicloud.aom-alarm",
                "actions": [
                    {
                        "type": "add",
                        "alarm_rule_name": "new-event-alarm",
                        "alarm_rule_description": "新的事件告警规则",
                        "alarm_rule_type": "event",
                        "alarm_rule_enable": True,
                        "alarm_notifications": {
                            "notification_type": "direct",
                            "route_group_enable": False,
                            "notification_enable": True,
                            "bind_notification_rule_id": "notification-rule-id",
                            "notify_resolved": False,
                            "notify_triggered": True,
                            "notify_frequency": 0
                        },
                        "event_alarm_spec": {
                            "alarm_source": "systemEvent",
                            "event_source": "AOM",
                            "monitor_objects": [
                                {
                                    "event_type": "fault",
                                    "event_severity": "warning"
                                }
                            ],
                            "trigger_conditions": [
                                {
                                    "count": 1,
                                    "severity": 2
                                }
                            ]
                        }
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["alarm_rule_name"], "new-event-alarm")
