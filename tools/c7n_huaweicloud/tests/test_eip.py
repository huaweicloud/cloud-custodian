from huaweicloud_common import BaseTest


class EipTest(BaseTest):
    """
    华为云弹性公网IP资源测试类
    包含对EIP类、AssociateInstanceTypeFilter、EIPDelete和EIPDisassociate的测试用例
    """

    def test_eip_query(self):
        """
        测试EIP资源查询功能

        验证能够正确列出华为云账户中的弹性公网IP资源
        """
        factory = self.replay_flight_data("eip_query")
        p = self.load_policy(
            {"name": "list_publicips", "resource": "huaweicloud.eip"},
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertTrue("id" in resources[0])

    def test_associate_instance_type_filter_elb(self):
        """
        测试EIP关联ELB实例类型过滤器

        验证能够正确筛选出关联到ELB实例的弹性公网IP
        """
        factory = self.replay_flight_data("eip_associate_instance_type_filter_elb")
        p = self.load_policy(
            {
                "name": "eip_associate_instance_type_filter_elb",
                "resource": "huaweicloud.eip",
                "filters": [
                    {
                        "type": "associate-instance-type",
                        "instance_type": "ELB",
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["associate_instance_type"], "ELB")

    def test_associate_instance_type_filter_natgw(self):
        """
        测试EIP关联NATGW实例类型过滤器

        验证能够正确筛选出关联到NATGW实例的弹性公网IP
        """
        factory = self.replay_flight_data("eip_associate_instance_type_filter_natgw")
        p = self.load_policy(
            {
                "name": "eip_associate_instance_type_filter_natgw",
                "resource": "huaweicloud.eip",
                "filters": [
                    {
                        "type": "associate-instance-type",
                        "instance_type": "NATGW",
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["associate_instance_type"], "NATGW")

    def test_associate_instance_type_filter_port(self):
        """
        测试EIP关联PORT实例类型过滤器

        验证能够正确筛选出关联到PORT实例的弹性公网IP
        """
        factory = self.replay_flight_data("eip_associate_instance_type_filter_port")
        p = self.load_policy(
            {
                "name": "eip_associate_instance_type_filter_port",
                "resource": "huaweicloud.eip",
                "filters": [
                    {
                        "type": "associate-instance-type",
                        "instance_type": "PORT",
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["associate_instance_type"], "PORT")

    def test_associate_instance_type_filter_none(self):
        """
        测试EIP无关联实例类型过滤器

        验证能够正确筛选出未关联任何实例的弹性公网IP
        """
        factory = self.replay_flight_data("eip_associate_instance_type_filter_none")
        p = self.load_policy(
            {
                "name": "eip_associate_instance_type_filter_none",
                "resource": "huaweicloud.eip",
                "filters": [
                    {
                        "type": "associate-instance-type",
                        "instance_type": "NONE",
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].get("associate_instance_type", ""), "")

    def test_delete_eip(self):
        """
        测试EIP删除功能

        验证能够正确删除指定的弹性公网IP资源
        """
        factory = self.replay_flight_data("eip_delete")
        p = self.load_policy(
            {
                "name": "eip_delete",
                "resource": "huaweicloud.eip",
                "filters": [
                    {
                        "type": "value",
                        "key": "id",
                        "value": "eip-12345678-1234-1234-1234-123456789012",
                    }
                ],
                "actions": ["delete"],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], "eip-12345678-1234-1234-1234-123456789012")

    def test_delete_eip_failure(self):
        """
        测试EIP删除失败场景

        验证当删除弹性公网IP失败时能够正确处理异常
        """
        factory = self.replay_flight_data("eip_delete_failure")
        p = self.load_policy(
            {
                "name": "eip_delete_failure",
                "resource": "huaweicloud.eip",
                "filters": [
                    {
                        "type": "value",
                        "key": "id",
                        "value": "eip-12345678-1234-1234-1234-123456789012",
                    }
                ],
                "actions": ["delete"],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], "eip-12345678-1234-1234-1234-123456789012")

    def test_disassociate_eip(self):
        """
        测试EIP解绑功能

        验证能够正确解绑已关联实例的弹性公网IP
        """
        factory = self.replay_flight_data("eip_disassociate")
        p = self.load_policy(
            {
                "name": "eip_disassociate",
                "resource": "huaweicloud.eip",
                "filters": [
                    {
                        "type": "value",
                        "key": "id",
                        "value": "eip-12345678-1234-1234-1234-123456789012",
                    },
                    {
                        "type": "value",
                        "key": "status",
                        "value": "ACTIVE",
                    }
                ],
                "actions": ["disassociate"],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], "eip-12345678-1234-1234-1234-123456789012")
        self.assertEqual(resources[0]["status"], "ACTIVE")

    def test_disassociate_eip_inactive(self):
        """
        测试对未绑定实例的EIP执行解绑操作

        验证对未绑定实例（非ACTIVE状态）的弹性公网IP执行解绑操作时能够正确处理
        """
        factory = self.replay_flight_data("eip_disassociate_inactive")
        p = self.load_policy(
            {
                "name": "eip_disassociate_inactive",
                "resource": "huaweicloud.eip",
                "filters": [
                    {
                        "type": "value",
                        "key": "id",
                        "value": "eip-12345678-1234-1234-1234-123456789012",
                    },
                    {
                        "type": "value",
                        "key": "status",
                        "value": "DOWN",
                    }
                ],
                "actions": ["disassociate"],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], "eip-12345678-1234-1234-1234-123456789012")
        self.assertEqual(resources[0]["status"], "DOWN")

    def test_disassociate_eip_failure(self):
        """
        测试EIP解绑失败场景

        验证当解绑弹性公网IP失败时能够正确处理异常
        """
        factory = self.replay_flight_data("eip_disassociate_failure")
        p = self.load_policy(
            {
                "name": "eip_disassociate_failure",
                "resource": "huaweicloud.eip",
                "filters": [
                    {
                        "type": "value",
                        "key": "id",
                        "value": "eip-12345678-1234-1234-1234-123456789012",
                    },
                    {
                        "type": "value",
                        "key": "status",
                        "value": "ACTIVE",
                    }
                ],
                "actions": ["disassociate"],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], "eip-12345678-1234-1234-1234-123456789012")
        self.assertEqual(resources[0]["status"], "ACTIVE")

    def test_value_filter_by_status(self):
        """
        测试使用值过滤器筛选EIP资源

        验证能够根据状态值正确筛选出弹性公网IP
        """
        factory = self.replay_flight_data("eip_value_filter_by_status")
        p = self.load_policy(
            {
                "name": "eip_value_filter_by_status",
                "resource": "huaweicloud.eip",
                "filters": [
                    {
                        "type": "value",
                        "key": "status",
                        "value": "DOWN",
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["status"], "DOWN")

    def test_value_filter_by_name(self):
        """
        测试使用值过滤器筛选EIP资源

        验证能够根据名称正确筛选出弹性公网IP
        """
        factory = self.replay_flight_data("eip_value_filter_by_name")
        p = self.load_policy(
            {
                "name": "eip_value_filter_by_name",
                "resource": "huaweicloud.eip",
                "filters": [
                    {
                        "type": "value",
                        "key": "alias",
                        "value": "test-eip",
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["alias"], "test-eip")

    def test_mixed_filters(self):
        """
        测试混合使用多个过滤器

        验证能够同时使用值过滤器和关联实例类型过滤器筛选弹性公网IP
        """
        factory = self.replay_flight_data("eip_mixed_filters")
        p = self.load_policy(
            {
                "name": "eip_mixed_filters",
                "resource": "huaweicloud.eip",
                "filters": [
                    {
                        "type": "value",
                        "key": "status",
                        "value": "ACTIVE",
                    },
                    {
                        "type": "associate-instance-type",
                        "instance_type": "PORT",
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["status"], "ACTIVE")
        self.assertEqual(resources[0]["associate_instance_type"], "PORT")
