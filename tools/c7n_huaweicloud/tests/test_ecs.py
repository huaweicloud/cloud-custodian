from huaweicloud_common import BaseTest


class InstanceStartTest(BaseTest):

    def test_instance_query(self):
        factory = self.replay_flight_data("ecs_instance_query")
        p = self.load_policy(
            {"name": "list_servers_details", "resource": "huaweicloud.ecs"},
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_instance_stop_active(self):
        factory = self.replay_flight_data("ecs_instance_stop_active")
        p = self.load_policy(
            {
                "name": "ecs_instance_stop_active",
                "resource": "huaweicloud.ecs",
                "filters": [
                    {
                        "type": "value",
                        "key": "id",
                        "value": "bac642b0-a9ca-4a13-b6b9-9e41b35905b6",
                    }
                ],
                "actions": [{"type": "instance-stop", "mode": "HARD"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], "bac642b0-a9ca-4a13-b6b9-9e41b35905b6")

    def test_instance_stop_shutoff(self):
        factory = self.replay_flight_data("ecs_instance_stop_shutoff")
        p = self.load_policy(
            {
                "name": "ecs_instance_stop_shutoff",
                "resource": "huaweicloud.ecs",
                "filters": [
                    {
                        "type": "value",
                        "key": "id",
                        "value": "bac642b0-a9ca-4a13-b6b9-9e41b35905b6",
                    }
                ],
                "actions": [{"type": "instance-stop", "mode": "HARD"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], "bac642b0-a9ca-4a13-b6b9-9e41b35905b6")

    def test_instance_start_shutoff(self):
        factory = self.replay_flight_data("ecs_instance_start_shutoff")
        p = self.load_policy(
            {
                "name": "ecs_instance_start_shutoff",
                "resource": "huaweicloud.ecs",
                "filters": [
                    {
                        "type": "value",
                        "key": "id",
                        "value": "bac642b0-a9ca-4a13-b6b9-9e41b35905b6",
                    }
                ],
                "actions": ["instance-start"],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], "bac642b0-a9ca-4a13-b6b9-9e41b35905b6")

    def test_instance_start_active(self):
        factory = self.replay_flight_data("ecs_instance_start_active")
        p = self.load_policy(
            {
                "name": "ecs_instance_start_active",
                "resource": "huaweicloud.ecs",
                "filters": [
                    {
                        "type": "value",
                        "key": "id",
                        "value": "bac642b0-a9ca-4a13-b6b9-9e41b35905b6",
                    }
                ],
                "actions": ["instance-start"],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], "bac642b0-a9ca-4a13-b6b9-9e41b35905b6")

    def test_instance_reboot_active(self):
        factory = self.replay_flight_data("ecs_instance_reboot_active")
        p = self.load_policy(
            {
                "name": "ecs_instance_reboot_active",
                "resource": "huaweicloud.ecs",
                "filters": [
                    {
                        "type": "value",
                        "key": "id",
                        "value": "bac642b0-a9ca-4a13-b6b9-9e41b35905b6",
                    }
                ],
                "actions": ["instance-reboot"],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], "bac642b0-a9ca-4a13-b6b9-9e41b35905b6")

    def test_instance_reboot_shutoff(self):
        factory = self.replay_flight_data("ecs_instance_reboot_shutoff")
        p = self.load_policy(
            {
                "name": "ecs_instance_reboot_shutoff",
                "resource": "huaweicloud.ecs",
                "filters": [
                    {
                        "type": "value",
                        "key": "id",
                        "value": "bac642b0-a9ca-4a13-b6b9-9e41b35905b6",
                    }
                ],
                "actions": ["instance-reboot"],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], "bac642b0-a9ca-4a13-b6b9-9e41b35905b6")

    def test_fetch_job_status(self):
        factory = self.replay_flight_data("ecs_fetch_job_status")
        p = self.load_policy(
            {
                "name": "ecs_fetch_job_status",
                "resource": "huaweicloud.ecs",
                "actions": [
                    {
                        "type": "fetch-job-status",
                        "job_id": "ff8080829585af7f0195c1e776d9475c",
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_instance_terminate(self):
        factory = self.replay_flight_data("ecs_instance_terminate")
        p = self.load_policy(
            {
                "name": "ecs_instance_terminate",
                "resource": "huaweicloud.ecs",
                "filters": [
                    {
                        "type": "value",
                        "key": "id",
                        "value": "bac642b0-a9ca-4a13-b6b9-9e41b35905b6",
                    }
                ],
                "actions": [{"type": "instance-terminate"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], "bac642b0-a9ca-4a13-b6b9-9e41b35905b6")

    def test_instance_add_security_groups(self):
        factory = self.replay_flight_data("ecs_instance_add_security_groups")
        p = self.load_policy(
            {
                "name": "ecs_instance_add_security_groups",
                "resource": "huaweicloud.ecs",
                "filters": [
                    {
                        "type": "value",
                        "key": "id",
                        "value": "bac642b0-a9ca-4a13-b6b9-9e41b35905b6",
                    }
                ],
                "actions": [
                    {"type": "instance-add-security-groups", "name": "sg-default-smb"}
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], "bac642b0-a9ca-4a13-b6b9-9e41b35905b6")

    def test_instance_delete_security_groups(self):
        factory = self.replay_flight_data("ecs_instance_delete_security_groups")
        p = self.load_policy(
            {
                "name": "ecs_instance_delete_security_groups",
                "resource": "huaweicloud.ecs",
                "filters": [
                    {
                        "type": "value",
                        "key": "id",
                        "value": "bac642b0-a9ca-4a13-b6b9-9e41b35905b6",
                    }
                ],
                "actions": [
                    {
                        "type": "instance-delete-security-groups",
                        "name": "sg-default-smb",
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], "bac642b0-a9ca-4a13-b6b9-9e41b35905b6")

    def test_instance_resize(self):
        factory = self.replay_flight_data("ecs_instance_resize")
        p = self.load_policy(
            {
                "name": "ecs_instance_resize",
                "resource": "huaweicloud.ecs",
                "filters": [
                    {
                        "type": "value",
                        "key": "id",
                        "value": "bac642b0-a9ca-4a13-b6b9-9e41b35905b6",
                    }
                ],
                "actions": [
                    {
                        "type": "instance-resize",
                        "flavor_ref": "x1.1u.4g",
                        "mode": "withStopServer",
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], "bac642b0-a9ca-4a13-b6b9-9e41b35905b6")

    def test_set_instance_profile(self):
        factory = self.replay_flight_data("ecs_set_instance_profile")
        p = self.load_policy(
            {
                "name": "ecs_set_instance_profile",
                "resource": "huaweicloud.ecs",
                "filters": [
                    {
                        "type": "value",
                        "key": "id",
                        "value": "bac642b0-a9ca-4a13-b6b9-9e41b35905b6",
                    }
                ],
                "actions": [
                    {"type": "set-instance-profile", "metadata": {"key": "value"}}
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], "bac642b0-a9ca-4a13-b6b9-9e41b35905b6")

    # -------------------------------Filter Test---------------------------------#

    def test_instance_age(self):
        factory = self.replay_flight_data("ecs_instance_age")
        p = self.load_policy(
            {
                "name": "ecs_instance_age",
                "resource": "huaweicloud.ecs",
                "filters": [{"type": "instance-age", "op": "ge", "days": 1}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], "bac642b0-a9ca-4a13-b6b9-9e41b35905b6")

    def test_instance_uptime(self):
        factory = self.replay_flight_data("ecs_instance_uptime")
        p = self.load_policy(
            {
                "name": "ecs_instance_uptime",
                "resource": "huaweicloud.ecs",
                "filters": [{"type": "instance-uptime", "op": "ge", "days": 1}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], "bac642b0-a9ca-4a13-b6b9-9e41b35905b6")

    def test_instance_attribute(self):
        factory = self.replay_flight_data("ecs_instance_attribute")
        p = self.load_policy(
            {
                "name": "ecs_instance_attribute",
                "resource": "huaweicloud.ecs",
                "filters": [
                    {
                        "type": "instance-attribute",
                        "attribute": "OS-EXT-SRV-ATTR:user_data",
                        "key": "Value",
                        "op": "regex",
                        "value": "(?smi).*user=",
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 0)

    def test_ephemeral(self):
        factory = self.replay_flight_data("ecs_ephemeral")
        p = self.load_policy(
            {
                "name": "ecs_ephemeral",
                "resource": "huaweicloud.ecs",
                "filters": [{"type": "ephemeral"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 0)

    def test_instance_user_data(self):
        factory = self.replay_flight_data("ecs_instance_user_data")
        p = self.load_policy(
            {
                "name": "ecs_instance_user_data",
                "resource": "huaweicloud.ecs",
                "filters": [
                    {
                        "type": "instance-user-data",
                        "op": "regex",
                        "value": "(?smi).*user=",
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 0)

    def test_instance_evs(self):
        factory = self.replay_flight_data("ecs_instance_evs")
        p = self.load_policy(
            {
                "name": "ecs_instance_evs",
                "resource": "huaweicloud.ecs",
                "filters": [
                    {
                        "type": "instance-evs",
                        "key": "encrypted",
                        "op": "eq",
                        "value": "false",
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 0)

    # TODO ims、vpc、cbr的相关UT
    def test_instance_vpc(self):
        factory = self.replay_flight_data("ecs_instance_vpc")
        p = self.load_policy(
            {
                "name": "ecs_instance_vpc",
                "resource": "huaweicloud.ecs",
                "filters": [
                    {
                        "type": "instance-vpc",
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
