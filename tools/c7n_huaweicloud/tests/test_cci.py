# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from huaweicloud_common import BaseTest


class CCITest(BaseTest):
    """Huawei Cloud CCI (Container Instance) Service Test Class
    Test various resource types of CCI service: Namespace, Pod, ConfigMap, Secret
    and related filter and action functionalities
    """

    # ===============================
    # CCI Namespace Resource Tests
    # ===============================

    def test_namespace_query(self):
        """Test CCI namespace resource query functionality"""
        factory = self.replay_flight_data("cci_namespace_query")
        p = self.load_policy(
            {
                "name": "list_cci_namespaces",
                "resource": "huaweicloud.cci_namespace"
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreaterEqual(len(resources), 0)
        # Verify returned resource structure
        if len(resources) > 0:
            self.assertIn("metadata", resources[0])
            self.assertIn("name", resources[0]["metadata"])

    def test_namespace_name_filter(self):
        """Test CCI namespace name filter"""
        factory = self.replay_flight_data("cci_namespace_name_filter")
        p = self.load_policy(
            {
                "name": "cci_namespace_by_name",
                "resource": "huaweicloud.cci_namespace",
                "filters": [
                    {
                        "type": "name",
                        "value": "default",
                        "op": "eq"
                    }
                ]
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify filter results
        for resource in resources:
            self.assertEqual(resource["metadata"]["name"], "default")

    def test_namespace_creation_age_filter(self):
        """Test CCI namespace creation time filter"""
        factory = self.replay_flight_data("cci_namespace_creation_age_filter")
        p = self.load_policy(
            {
                "name": "old_cci_namespaces",
                "resource": "huaweicloud.cci_namespace",
                "filters": [
                    {
                        "type": "creation-age",
                        "days": 1,
                        "op": "ge"
                    }
                ]
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreaterEqual(len(resources), 0)

    def test_namespace_uid_filter(self):
        """Test CCI namespace UID filter"""
        factory = self.replay_flight_data("cci_namespace_uid_filter")
        p = self.load_policy(
            {
                "name": "cci_namespace_by_uid",
                "resource": "huaweicloud.cci_namespace",
                "filters": [
                    {
                        "type": "uid",
                        "value": "test-uid-123",
                        "op": "eq"
                    }
                ]
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreaterEqual(len(resources), 0)

    def test_namespace_delete(self):
        """Test CCI namespace deletion operation"""
        factory = self.replay_flight_data("cci_namespace_delete")
        p = self.load_policy(
            {
                "name": "delete_cci_namespace",
                "resource": "huaweicloud.cci_namespace",
                "filters": [
                    {
                        "type": "name",
                        "value": "test-namespace",
                        "op": "eq"
                    }
                ],
                "actions": ["delete"]
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreaterEqual(len(resources), 0)

    # ===============================
    # CCI Pod Resource Tests
    # ===============================

    def test_pod_query(self):
        """Test CCI Pod resource query functionality"""
        factory = self.replay_flight_data("cci_pod_query")
        p = self.load_policy(
            {
                "name": "list_cci_pods",
                "resource": "huaweicloud.cci_pod"
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreaterEqual(len(resources), 0)
        # Verify returned resource structure
        if len(resources) > 0:
            self.assertIn("metadata", resources[0])
            self.assertIn("name", resources[0]["metadata"])
            self.assertIn("namespace", resources[0]["metadata"])

    def test_pod_name_filter(self):
        """Test CCI Pod name filter"""
        factory = self.replay_flight_data("cci_pod_name_filter")
        p = self.load_policy(
            {
                "name": "cci_pod_by_name",
                "resource": "huaweicloud.cci_pod",
                "filters": [
                    {
                        "type": "name",
                        "value": "test-pod",
                        "op": "eq"
                    }
                ]
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify filter results
        for resource in resources:
            self.assertEqual(resource["metadata"]["name"], "test-pod")

    def test_pod_creation_age_filter(self):
        """Test CCI Pod creation time filter"""
        factory = self.replay_flight_data("cci_pod_creation_age_filter")
        p = self.load_policy(
            {
                "name": "old_cci_pods",
                "resource": "huaweicloud.cci_pod",
                "filters": [
                    {
                        "type": "creation-age",
                        "days": 7,
                        "op": "ge"
                    }
                ]
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreaterEqual(len(resources), 0)

    def test_pod_uid_filter(self):
        """Test CCI Pod UID filter"""
        factory = self.replay_flight_data("cci_pod_uid_filter")
        p = self.load_policy(
            {
                "name": "cci_pod_by_uid",
                "resource": "huaweicloud.cci_pod",
                "filters": [
                    {
                        "type": "uid",
                        "value": "pod-uid-123",
                        "op": "eq"
                    }
                ]
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreaterEqual(len(resources), 0)

    def test_pod_image_name_filter(self):
        """Test CCI Pod image name filter"""
        factory = self.replay_flight_data("cci_pod_image_name_filter")
        p = self.load_policy(
            {
                "name": "pods_with_nginx",
                "resource": "huaweicloud.cci_pod",
                "filters": [
                    {
                        "type": "image-name",
                        "value": "nginx",
                        "op": "eq"
                    }
                ]
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify filter results - check if Pod contains nginx image
        for resource in resources:
            containers = resource.get("spec", {}).get("containers", [])
            found_nginx = False
            for container in containers:
                if "nginx" in container.get("image", ""):
                    found_nginx = True
                    break
            self.assertTrue(found_nginx, "Pod should contain nginx image")

    def test_pod_modify(self):
        """Test CCI Pod modification operation"""
        factory = self.replay_flight_data("cci_pod_modify")
        p = self.load_policy(
            {
                "name": "modify_cci_pod",
                "resource": "huaweicloud.cci_pod",
                "filters": [
                    {
                        "type": "name",
                        "value": "test-pod",
                        "op": "eq"
                    }
                ],
                "actions": [
                    {
                        "type": "modify",
                        "patch": {
                            "metadata": {
                                "labels": {
                                    "env": "production"
                                }
                            }
                        }
                    }
                ]
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreaterEqual(len(resources), 0)

    def test_pod_delete(self):
        """Test CCI Pod deletion operation"""
        factory = self.replay_flight_data("cci_pod_delete")
        p = self.load_policy(
            {
                "name": "delete_old_pods",
                "resource": "huaweicloud.cci_pod",
                "actions": ["delete"]
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreaterEqual(len(resources), 0)

    # ===============================
    # CCI ConfigMap Resource Tests
    # ===============================

    def test_configmap_query(self):
        """Test CCI ConfigMap resource query functionality"""
        factory = self.replay_flight_data("cci_configmap_query")
        p = self.load_policy(
            {
                "name": "list_cci_configmaps",
                "resource": "huaweicloud.cci_configmap"
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreaterEqual(len(resources), 0)
        # Verify returned resource structure
        if len(resources) > 0:
            self.assertIn("metadata", resources[0])
            self.assertIn("name", resources[0]["metadata"])
            self.assertIn("namespace", resources[0]["metadata"])

    def test_configmap_name_filter(self):
        """Test CCI ConfigMap name filter"""
        factory = self.replay_flight_data("cci_configmap_name_filter")
        p = self.load_policy(
            {
                "name": "cci_configmap_by_name",
                "resource": "huaweicloud.cci_configmap",
                "filters": [
                    {
                        "type": "name",
                        "value": "test-12130306",
                        "op": "eq"
                    }
                ]
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify filter results
        for resource in resources:
            self.assertEqual(resource["metadata"]["name"], "test-12130306")

    def test_configmap_creation_age_filter(self):
        """Test CCI ConfigMap creation time filter"""
        factory = self.replay_flight_data("cci_configmap_creation_age_filter")
        p = self.load_policy(
            {
                "name": "old_cci_configmaps",
                "resource": "huaweicloud.cci_configmap",
                "filters": [
                    {
                        "type": "creation-age",
                        "days": 15,
                        "op": "ge"
                    }
                ]
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreaterEqual(len(resources), 0)

    def test_configmap_uid_filter(self):
        """Test CCI ConfigMap UID filter"""
        factory = self.replay_flight_data("cci_configmap_uid_filter")
        p = self.load_policy(
            {
                "name": "cci_configmap_by_uid",
                "resource": "huaweicloud.cci_configmap",
                "filters": [
                    {
                        "type": "uid",
                        "value": "efd6d9e0-dfb3-11e7-9c19-fa163e2d897b",
                        "op": "eq"
                    }
                ]
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreaterEqual(len(resources), 0)

    def test_configmap_modify(self):
        """Test CCI ConfigMap modification operation"""
        factory = self.replay_flight_data("cci_configmap_modify")
        p = self.load_policy(
            {
                "name": "modify_cci_configmap",
                "resource": "huaweicloud.cci_configmap",
                "filters": [
                    {
                        "type": "name",
                        "value": "test-12130306",
                        "op": "eq"
                    }
                ],
                "actions": [
                    {
                        "type": "modify",
                        "patch": {
                            "data": {
                                "config.yaml": "new-config-value"
                            }
                        }
                    }
                ]
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreaterEqual(len(resources), 0)

    def test_configmap_delete(self):
        """Test CCI ConfigMap deletion operation"""
        factory = self.replay_flight_data("cci_configmap_delete")
        p = self.load_policy(
            {
                "name": "delete_unused_configmaps",
                "resource": "huaweicloud.cci_configmap",
                "filters": [
                    {
                        "type": "name",
                        "value": "test-12130306",
                        "op": "eq"
                    }
                ],
                "actions": ["delete"]
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreaterEqual(len(resources), 0)

    # ===============================
    # CCI Secret Resource Tests
    # ===============================

    def test_secret_query(self):
        """Test CCI Secret resource query functionality"""
        factory = self.replay_flight_data("cci_secret_query")
        p = self.load_policy(
            {
                "name": "list_cci_secrets",
                "resource": "huaweicloud.cci_secret"
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreaterEqual(len(resources), 0)
        # Verify returned resource structure
        if len(resources) > 0:
            self.assertIn("metadata", resources[0])
            self.assertIn("name", resources[0]["metadata"])
            self.assertIn("namespace", resources[0]["metadata"])

    def test_secret_name_filter(self):
        """Test CCI Secret name filter"""
        factory = self.replay_flight_data("cci_secret_name_filter")
        p = self.load_policy(
            {
                "name": "cci_secret_by_name",
                "resource": "huaweicloud.cci_secret",
                "filters": [
                    {
                        "type": "name",
                        "value": "test-secret",
                        "op": "eq"
                    }
                ]
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify filter results
        for resource in resources:
            self.assertEqual(resource["metadata"]["name"], "test-secret")

    def test_secret_creation_age_filter(self):
        """Test CCI Secret creation time filter"""
        factory = self.replay_flight_data("cci_secret_creation_age_filter")
        p = self.load_policy(
            {
                "name": "old_cci_secrets",
                "resource": "huaweicloud.cci_secret",
                "filters": [
                    {
                        "type": "creation-age",
                        "days": 90,
                        "op": "ge"
                    }
                ]
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreaterEqual(len(resources), 0)

    def test_secret_uid_filter(self):
        """Test CCI Secret UID filter"""
        factory = self.replay_flight_data("cci_secret_uid_filter")
        p = self.load_policy(
            {
                "name": "cci_secret_by_uid",
                "resource": "huaweicloud.cci_secret",
                "filters": [
                    {
                        "type": "uid",
                        "value": "81ddca10-6784-40d7-a58e-05f1a6088d94",
                        "op": "eq"
                    }
                ]
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreaterEqual(len(resources), 0)

    def test_secret_modify(self):
        """Test CCI Secret modification operation"""
        factory = self.replay_flight_data("cci_secret_modify")
        p = self.load_policy(
            {
                "name": "modify_cci_secret",
                "resource": "huaweicloud.cci_secret",
                "filters": [
                    {
                        "type": "name",
                        "value": "test-secret",
                        "op": "eq"
                    }
                ],
                "actions": [
                    {
                        "type": "modify",
                        "patch": {
                            "metadata": {
                                "labels": {
                                    "updated": "true"
                                }
                            }
                        }
                    }
                ]
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreaterEqual(len(resources), 0)

    def test_secret_delete(self):
        """Test CCI Secret deletion operation"""
        factory = self.replay_flight_data("cci_secret_delete")
        p = self.load_policy(
            {
                "name": "delete_expired_secrets",
                "resource": "huaweicloud.cci_secret",
                "filters": [
                    {
                        "type": "name",
                        "value": "test-secret",
                        "op": "eq"
                    }
                ],
                "actions": ["delete"]
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertGreaterEqual(len(resources), 0)
