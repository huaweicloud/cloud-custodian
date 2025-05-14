from huaweicloud_common import BaseTest


class EipTest(BaseTest):
    """
    HuaweiCloud Elastic IP Resource Test Class
    Contains test cases for EIP class, AssociateInstanceTypeFilter, EIPDelete and EIPDisassociate
    """

    def test_eip_query(self):
        """
        Test EIP resource query functionality

        Verifies the ability to correctly list elastic IP resources in the HuaweiCloud account
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
        Test EIP association with ELB instance type filter

        Verifies the ability to correctly filter elastic IPs associated with ELB instances
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
        Test EIP association with NATGW instance type filter

        Verifies the ability to correctly filter elastic IPs associated with NATGW instances
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
        Test EIP association with PORT instance type filter

        Verifies the ability to correctly filter elastic IPs associated with PORT instances
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
        Test EIP with no associated instance type filter

        Verifies the ability to correctly filter elastic IPs not associated with any instance
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
        Test EIP deletion functionality

        Verifies the ability to correctly delete specified elastic IP resources
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
        Test EIP deletion failure scenario

        Verifies proper exception handling when elastic IP deletion fails
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
        Test EIP disassociation functionality

        Verifies the ability to correctly disassociate elastic IPs from associated instances
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
        Test disassociation operation on unbound EIPs

        Verifies proper handling when disassociation is attempted on EIPs not bound to instances
        (non-ACTIVE status)
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
        Test EIP disassociation failure scenario

        Verifies proper exception handling when elastic IP disassociation fails
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
        Test using value filter to filter EIP resources by status

        Verifies the ability to correctly filter elastic IPs based on status value
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
        Test using value filter to filter EIP resources by name

        Verifies the ability to correctly filter elastic IPs based on name
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
        Test using multiple filters together

        Verifies the ability to correctly filter elastic
         IPs using both value and associate instance type
        filters simultaneously
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
