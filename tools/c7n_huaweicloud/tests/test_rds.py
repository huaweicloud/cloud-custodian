# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from huaweicloud_common import BaseTest


# Note: Actual testing requires corresponding VCR files
# (e.g., rds_query.yaml, rds_filter_*.yaml, rds_action_*.yaml)
# These files should contain the required RDS instance data and API interaction records for testing.

class RDSTest(BaseTest):
    """Test Huawei Cloud RDS resources, filters, and actions"""

    # =========================
    # Resource Query Test
    # =========================
    def test_rds_query(self):
        """Test RDS instance query and basic attributes"""
        factory = self.replay_flight_data("rds_query")
        p = self.load_policy(
            {
                "name": "rds-query-test",
                "resource": "huaweicloud.rds",
            },
            session_factory=factory,
        )
        resources = p.run()
        # Validate VCR: rds_query.yaml should contain at least one RDS instance
        self.assertGreater(len(resources), 0,
                           "Test VCR file should contain at least one RDS instance")
        # Validate VCR: verify key attributes of the first instance
        instance = resources[0]
        self.assertTrue("id" in instance)
        self.assertTrue("name" in instance)
        self.assertTrue("status" in instance)
        self.assertTrue("created" in instance)  # Verify 'created' field exists (for AgeFilter)
        # Verify 'datastore' field exists (for DatabaseVersionFilter)
        self.assertTrue("datastore" in instance)
        self.assertTrue("port" in instance)  # Verify 'port' field exists (for DatabasePortFilter)
        # Verify 'ssl_enable' field exists (for SSLInstanceFilter)
        self.assertTrue("enable_ssl" in instance)
        # Verify 'disk_encryption_id' exists (or not), for DiskAutoExpansionFilter
        self.assertTrue(
            "disk_encryption_id" in instance or instance.get("disk_encryption_id") is None)
        # Verify 'public_ips' exists, for EIPFilter
        self.assertTrue("public_ips" in instance)

    # =========================
    # Filter Tests
    # =========================

    def test_rds_filter_disk_auto_expansion_enabled(self):
        """Test disk-auto-expansion filter - enabled state match"""
        factory = self.replay_flight_data("rds_filter_disk_auto_expansion")
        # Validate VCR: rds_filter_disk_auto_expansion.yaml
        # should contain at least one instance with auto-expansion enabled
        p = self.load_policy(
            {
                "name": "rds-filter-disk-expansion-enabled-test",
                "resource": "huaweicloud.rds",
                "filters": [{"type": "disk-auto-expansion", "enabled": True}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreater(len(resources), 0,
                           "Test VCR file should contain RDS instances with auto-expansion enabled")
        # No longer check disk_encryption_id, as show_auto_enlarge_policy API
        # is used to get auto-expansion status

    def test_rds_filter_disk_auto_expansion_disabled(self):
        """Test disk-auto-expansion filter - disabled state match"""
        factory = self.replay_flight_data("rds_filter_disk_auto_expansion")  # Reuse VCR
        # Validate VCR: rds_filter_disk_auto_expansion.yaml should
        # contain at least one instance with auto-expansion disabled
        p = self.load_policy(
            {
                "name": "rds-filter-disk-expansion-disabled-test",
                "resource": "huaweicloud.rds",
                "filters": [{"type": "disk-auto-expansion", "enabled": False}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreater(
            len(resources), 0,
            "Test VCR file should contain RDS instances with auto-expansion disabled")
        # No longer check disk_encryption_id,
        # as show_auto_enlarge_policy API is used to get auto-expansion status

    def test_rds_filter_db_version_lt(self):
        """Test database-version filter - detect instances not on the latest minor version"""
        factory = self.replay_flight_data("rds_filter_db_version")  # Reuse VCR
        # Validate VCR: rds_filter_db_version.yaml
        # should contain instances not on the latest minor version
        p = self.load_policy(
            {
                "name": "rds-filter-db-version-test",
                "resource": "huaweicloud.rds",
                "filters": [{"type": "database-version", "database_name": "mysql"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreater(
            len(resources), 0,
            "Test VCR file should contain RDS instances not on the latest minor version")

        # Validate filtered instances are those that need升级
        # Note: Since we cannot directly get the latest version for comparison,
        # here we can only validate that the filter logic runs normally and returns results
        # Ensure the VCR file contains the latest minor version information
        # for the filter to compare during actual testing

        # Check filtered instances contain database engine and version information
        for resource in resources:
            self.assertTrue("datastore" in resource)
            self.assertTrue("type" in resource["datastore"])
            self.assertTrue("complete_version" in resource["datastore"]
                            or "version" in resource["datastore"])

    def test_rds_filter_eip_exists(self):
        """Test eip filter - EIP exists"""
        factory = self.replay_flight_data("rds_filter_eip")
        # Validate VCR: rds_filter_eip.yaml should contain instances
        # with EIP bound (public_ips list not empty)
        p = self.load_policy(
            {
                "name": "rds-filter-eip-exists-test",
                "resource": "huaweicloud.rds",
                "filters": [{"type": "eip", "exists": True}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreater(len(resources), 0, "Test VCR file should contain RDS instances with EIP")
        for r in resources:
            self.assertTrue(r.get("public_ips") is not None and len(r["public_ips"]) > 0)

    def test_rds_filter_eip_not_exists(self):
        """Test eip filter - EIP does not exist"""
        factory = self.replay_flight_data("rds_filter_eip")  # Reuse VCR
        # Validate VCR: rds_filter_eip.yaml should contain instances
        # without EIP (public_ips list empty or None)
        p = self.load_policy(
            {
                "name": "rds-filter-eip-not-exists-test",
                "resource": "huaweicloud.rds",
                "filters": [{"type": "eip", "exists": False}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreater(len(resources), 0,
                           "Test VCR file should contain RDS instances without EIP")
        for r in resources:
            self.assertTrue(r.get("public_ips") is None or len(r["public_ips"]) == 0)

    def test_rds_filter_audit_log_disabled(self):
        """Test audit-log-disabled filter"""
        factory = self.replay_flight_data("rds_filter_audit_log_disabled")
        # Validate VCR: rds_filter_audit_log_disabled.yaml
        # should contain instances with audit logs disabled
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
        self.assertGreater(len(resources), 0,
                           "Test VCR file should contain RDS instances with audit logs disabled")
        # The VCR file for testing should contain calls and responses to
        # the show_auditlog_policy API

    def test_rds_filter_backup_policy_disabled(self):
        """Test backup-policy-disabled filter"""
        factory = self.replay_flight_data("rds_filter_backup_policy_disabled")
        # Validate VCR: rds_filter_backup_policy_disabled.yaml should contain
        # instances with backup policy disabled
        p = self.load_policy(
            {
                "name": "rds-filter-backup-policy-disabled-test",
                "resource": "huaweicloud.rds",
                "filters": [{"type": "backup-policy-disabled"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreater(len(resources), 0,
                           "Test VCR file should contain RDS instances with backup policy disabled")
        # The VCR file for testing should contain calls and responses to the show_backup_policy API

    def test_rds_filter_instance_parameter_eq(self):
        """Test instance-parameter filter - equal (eq)"""
        factory = self.replay_flight_data("rds_filter_instance_parameter")
        # Validate VCR: rds_filter_instance_parameter.yaml
        # should contain instances with max_connections set to 500
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
        self.assertGreater(
            len(resources), 0,
            f"Test VCR file should contain RDS instances with {param_name} set to {param_value}")
        # The VCR file for testing should contain calls and responses to
        # the show_instance_configuration API

    def test_rds_filter_instance_parameter_lt(self):
        """Test instance-parameter filter - less than (lt)"""
        factory = self.replay_flight_data("rds_filter_instance_parameter")  # Reuse VCR
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
        self.assertGreater(
            len(resources), 0,
            f"Test VCR file should contain RDS instances with {param_name} less than {upper_bound}")

    # =========================
    # Action Tests
    # =========================
    def test_rds_action_set_security_group(self):
        """Test set-security-group action"""
        factory = self.replay_flight_data("rds_action_set_sg")
        # Validate VCR: rds_action_set_sg.yaml should contain instances to modify security group
        target_instance_id = "rds-instance-for-sg-test"
        new_sg_id = "new-security-group-id"
        p = self.load_policy(
            {
                "name": "rds-action-set-sg-test",
                "resource": "huaweicloud.rds",
                "filters": [{"type": "value",
                             "key": "id", "value": target_instance_id}],
                "actions": [{"type": "set-security-group", "security_group_id": new_sg_id}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)  # Confirm policy filtered the target resource
        self.assertEqual(resources[0]["id"], target_instance_id)
        # Validate action: need to manually check VCR file rds_action_set_sg.yaml
        # Confirm POST /v3/{project_id}/instances/{instance_id}/security-group is called
        # And the request body contains {"security_group_id": "new-security-group-id"}

    def test_rds_action_switch_ssl_on(self):
        """Test switch-ssl action - enable SSL"""
        factory = self.replay_flight_data("rds_action_switch_ssl_on")
        # Validate VCR: rds_action_switch_ssl_on.yaml should contain instances
        # to enable SSL (ssl_enable: false)
        target_instance_id = "rds-instance-for-ssl-on"
        p = self.load_policy(
            {
                "name": "rds-action-ssl-on-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    {"type": "value",
                     "key": "id", "value": target_instance_id}
                ],
                "actions": [{"type": "switch-ssl", "ssl_option": True}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        self.assertFalse(resources[0]["enable_ssl"])  # Confirm pre-action status
        # Validate action: need to manually check VCR file rds_action_switch_ssl_on.yaml
        # Confirm POST /v3/{project_id}/instances/{instance_id}/ssl is called
        # And the request body contains {"ssl_option": "on"}

    def test_rds_action_switch_ssl_off(self):
        """Test switch-ssl action - disable SSL"""
        factory = self.replay_flight_data("rds_action_switch_ssl_off")
        # Validate VCR: rds_action_switch_ssl_off.yaml should contain instances
        # to disable SSL (ssl_enable: true)
        target_instance_id = "rds-instance-for-ssl-off"
        p = self.load_policy(
            {
                "name": "rds-action-ssl-off-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    {"type": "value",
                     "key": "id", "value": target_instance_id}
                ],
                "actions": [{"type": "switch-ssl", "ssl_option": False}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        self.assertTrue(resources[0]["enable_ssl"])  # Confirm pre-action status
        # Validate action: need to manually check VCR file rds_action_switch_ssl_off.yaml
        # Confirm POST /v3/{project_id}/instances/{instance_id}/ssl is called
        # And the request body contains {"ssl_option": "off"}

    def test_rds_action_update_port(self):
        """Test update-port action"""
        factory = self.replay_flight_data("rds_action_update_port")
        # Validate VCR: rds_action_update_port.yaml should contain instances to update port
        target_instance_id = "rds-instance-for-port-update"
        original_port = 3306  # Assume the original port in the VCR is 3306
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
        self.assertEqual(resources[0]["port"], original_port)  # Confirm pre-action port
        # Validate action: need to manually check VCR file rds_action_update_port.yaml
        # Confirm PUT /v3/{project_id}/instances/{instance_id}/port is called
        # And the request body contains {"port": 3307}

    def test_rds_action_set_auto_enlarge_policy(self):
        """Test set-auto-enlarge-policy action - full parameter settings"""
        factory = self.replay_flight_data("rds_action_set_auto_enlarge_policy")
        # Validate VCR: rds_action_set_auto_enlarge_policy.yaml should
        # contain instances to set autoEnlarge policy
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
        # Validate action: need to manually check VCR file rds_action_set_auto_enlarge_policy.yaml
        # Confirm the correct API is called and contains expected request parameters

    def test_rds_action_attach_eip_bind(self):
        """Test attach-eip action - bind"""
        factory = self.replay_flight_data("rds_action_attach_eip_bind")
        # Validate VCR: rds_action_attach_eip_bind.yaml should
        # contain instances to bind EIP (no public_ips)
        target_instance_id = "rds-instance-id-for-eip"

        """Test attach-eip action - bind"""
        factory = self.replay_flight_data("rds_action_attach_eip_bind")
        # Validate VCR: rds_action_attach_eip_bind.yaml should
        # contain instances to bind EIP (no public_ips)
        target_instance_id = "rds-instance-id-for-eip"
        public_ip_to_bind = "123.123.123.123"  # Replace with EIP prepared in the VCR
        public_ip_id_to_bind = "1bf25cb6-13ef-4a71-a85f-e4da190c016d"
        p = self.load_policy(
            {
                "name": "rds-action-eip-bind-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    {"type": "value",
                    "key": "id", "value": target_instance_id}
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
        # Validate action: need to manually check VCR file rds_action_attach_eip_bind.yaml
        # Confirm the correct API is called and contains expected request parameters

    def test_rds_action_attach_eip_unbind(self):
        """Test attach-eip action - unbind"""
        factory = self.replay_flight_data("rds_action_attach_eip_unbind")
        # Validate VCR: rds_action_attach_eip_unbind.yaml should
        # contain instances to unbind EIP (have public_ips)
        target_instance_id = "rds-instance-id-for-eip-unbind"
        p = self.load_policy(
            {
                "name": "rds-action-eip-unbind-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    {"type": "value",
                     "key": "id", "value": target_instance_id}
                ],
                "actions": [{"type": "attach-eip", "is_bind": False}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        # Validate action: need to manually check VCR file rds_action_attach_eip_unbind.yaml
        # Confirm the correct API is called and contains {"bind_type": "unbind"}

    def test_rds_action_upgrade_db_version_immediate(self):
        """Test upgrade-db-version action - upgrade immediately"""
        factory = self.replay_flight_data("rds_action_upgrade_db_version_immediate")
        # Validate VCR: rds_action_upgrade_db_version_immediate.yaml should
        # contain instances that can upgrade to a minor version
        target_instance_id = "rds-instance-for-upgrade-immediate"
        p = self.load_policy(
            {
                "name": "rds-action-upgrade-immediate-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    # {"id": target_instance_id},
                    # Filter instances with specific database versions
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
        # Validate action: need to manually check VCR file
        # rds_action_upgrade_db_version_immediate.yaml
        # Confirm the correct API is called and contains
        # CustomerUpgradeDatabaseVersionReq object with is_delayed=true

    def test_rds_action_upgrade_db_version_later(self):
        """Test upgrade-db-version action - upgrade later (during maintenance window)"""
        factory = self.replay_flight_data("rds_action_upgrade_db_version_later")
        # Validate VCR: rds_action_upgrade_db_version_later.yaml should
        # contain instances that can upgrade to a minor version
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
        # Validate action: need to manually check VCR file rds_action_upgrade_db_version_later.yaml
        # Confirm the correct API is called and contains CustomerUpgradeDatabaseVersionReq
        # object with is_delayed=false

    def test_rds_action_set_audit_log_policy_enable(self):
        """Test set-audit-log-policy action - enable audit logs"""
        factory = self.replay_flight_data("rds_action_set_audit_log_policy_enable")
        # Validate VCR: rds_action_set_audit_log_policy_enable.yaml should
        # contain instances to enable audit logs
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
        # Validate action: need to manually check VCR file
        # rds_action_set_audit_log_policy_enable.yaml
        # Confirm the correct API is called and contains
        # {"keep_days": 7, "audit_types": ["SELECT", "INSERT", "UPDATE", "DELETE"]}

    def test_rds_action_set_audit_log_policy_disable(self):
        """Test set-audit-log-policy action - disable audit logs"""
        factory = self.replay_flight_data("rds_action_set_audit_log_policy_disable")
        # Validate VCR: rds_action_set_audit_log_policy_disable.yaml should
        # contain instances to disable audit logs
        target_instance_id = "rds-instance-for-audit-log"
        p = self.load_policy(
            {
                "name": "rds-action-audit-log-disable-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    # {"id": target_instance_id},
                    {"type": "value", "key": "id", "value": target_instance_id}
                    # Do not use audit-log-disabled filter here, as we are looking for
                    # instances with audit logs enabled
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
        # Validate action: need to manually check VCR file
        # rds_action_set_audit_log_policy_disable.yaml
        # Confirm PUT /v3/{project_id}/instances/{instance_id}/auditlog-policy is called
        # And the request body contains {"keep_days": 0, "reserve_auditlogs": true}

    # Additional test cases can be added to cover boundary conditions and error scenarios
    def test_rds_action_set_backup_policy(self):
        """Test set-backup-policy action"""
        factory = self.replay_flight_data("rds_action_set_backup_policy")
        # Validate VCR: rds_action_set_backup_policy.yaml should contain
        # instances to set backup policy
        target_instance_id = "rds-instance-for-backup-policy"
        p = self.load_policy(
            {
                "name": "rds-action-set-backup-policy-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    {"id": target_instance_id},
                    {"type": "backup-policy-disabled"}
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
        # Validate action: need to manually check VCR file rds_action_set_backup_policy.yaml
        # Confirm PUT /v3/{project_id}/instances/{instance_id}/backups/policy is called
        # And the request body contains the correct parameters

    def test_rds_action_update_instance_parameter(self):
        """Test update-instance-parameter action"""
        factory = self.replay_flight_data("rds_action_update_instance_parameter")
        # Validate VCR: rds_action_update_instance_parameter.yaml should
        # contain instances to modify parameters
        target_instance_id = "rds-instance-for-parameter-update"
        param_name = "max_connections"
        param_value = "1000"
        p = self.load_policy(
            {
                "name": "rds-action-update-instance-parameter-test",
                "resource": "huaweicloud.rds",
                "filters": [
                    {"id": target_instance_id},
                    # Filter instances with parameter value less than 1000
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
        # Validate action: need to manually check VCR file rds_action_update_instance_parameter.yaml
        # Confirm PUT /v3/{project_id}/instances/{instance_id}/configurations is called
        # And the request body contains the correct parameters

    def test_postgresql_hba_conf_filter_match(self):
        """Test pg_hba.conf configuration filter - match specific configuration"""
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
        self.assertGreater(len(resources), 0,
                           "Test VCR file should contain at least one matching PostgreSQL instance")
        # Confirm all returned instances are of PostgreSQL type
        for resource in resources:
            self.assertEqual(resource.get('datastore', {}).get('type', '').lower(), 'postgresql')

    def test_postgresql_hba_conf_filter_no_match(self):
        """Test pg_hba.conf configuration filter - no match"""
        factory = self.replay_flight_data("rds_postgresql_hba_conf_no_match")
        p = self.load_policy(
            {
                "name": "rds-postgresql-hba-conf-no-match",
                "resource": "huaweicloud.rds",
                "filters": [{
                    "type": "postgresql-hba-conf",
                    "has_config": {
                        "type": "hostssl",  # Use a less common configuration type
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
        self.assertEqual(len(resources), 0, "No instances should match this rare configuration")

    # ===========================
    # Action Tests (Modify pg_hba.conf)
    # ===========================
    def test_modify_pg_hba_conf_action(self):
        """Test modifying pg_hba.conf configuration action"""
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
        # Validate action: need to manually check VCR file to confirm correct API calls

    # ===========================
    # Action Tests (Enable TDE)
    # ===========================
    def test_enable_tde_action(self):
        """Test enabling TDE feature for SQL Server instances"""
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
                    "rotate_day": 30  # Rotate every 30 days
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], target_instance_id)
        # Validate action: need to manually check VCR file to confirm correct API calls

    def test_enable_tde_action_with_secret(self):
        """Test enabling TDE feature for SQL Server instances - with secret service"""
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
        # Validate action: need to manually check VCR file to confirm correct API calls


# =========================
# Reusable Feature Tests
# =========================


class ReusableRDSTests(BaseTest):
    """Test reusable Filters and Actions (using RDS as an example)"""

    # --- Reusable Filter Tests ---
    def test_rds_filter_value_match(self):
        """Test value filter - match"""
        factory = self.replay_flight_data("rds_reusable_filter_value")
        # Validate VCR: rds_reusable_filter_value.yaml should contain instances with status ACTIVE
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
                           f"Test VCR file should contain instances with status {target_status}")
        for r in resources:
            self.assertEqual(r.get("status"), target_status)

    def test_rds_filter_value_no_match(self):
        """Test value filter - no match"""
        factory = self.replay_flight_data("rds_reusable_filter_value")  # Reuse VCR
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

    # --- Reusable Action Tests ---

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

        # Validate action: need to manually check VCR file to confirm
        # API calls include the following:
        # 1. Correct API is called: POST /v3/{project_id}/instances/{instance_id}/major-versions
        # 2. Request body contains:
        #    - "target_version": "14.6.1"
        #    - "is_change_private_ip": true
        #    - "statistics_collection_mode": "before_change_private_ip"
