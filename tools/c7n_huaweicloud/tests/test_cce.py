# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from huaweicloud_common import BaseTest


class CceClusterTest(BaseTest):
    """Test CCE cluster resource query and operations"""

    def test_cluster_query(self):
        """Test CCE cluster resource query"""
        factory = self.replay_flight_data('cce_cluster_query')
        p = self.load_policy({
            'name': 'list-cce-clusters',
            'resource': 'huaweicloud.cce-cluster'},
            session_factory=factory)
        resources = p.run()
        # Verify VCR: cce_cluster_query should contain 1 cluster
        self.assertEqual(len(resources), 1)
        # Verify VCR: value should match 'name' in cce_cluster_query
        self.assertEqual(resources[0]['metadata']['name'], 'test-cluster')
        # Verify resource ID field
        self.assertIn('metadata', resources[0])
        self.assertIn('uid', resources[0]['metadata'])

    def test_cluster_tag_filters(self):
        """Test CCE cluster tag filtering functionality"""
        factory = self.replay_flight_data('cce_cluster_with_tags')
        p = self.load_policy({
            'name': 'cluster-update-tags',
            'resource': 'huaweicloud.cce-cluster',
            'filters': [
                {
                    'type': 'value',
                    'key': 'metadata.name',
                    'value': 'j30028900-1backi'
                },
                {
                    'tag:app1': 'present'
                },
                {
                    'tag:app2': 'present'
                },
                {
                    'tag:app3': 'present'
                }
            ]
        }, session_factory=factory)
        resources = p.run()
        # Verify that resources were found and have the expected structure
        self.assertEqual(len(resources), 1)

    def test_cluster_delete_action(self):
        """Test CCE cluster delete operation"""
        factory = self.replay_flight_data('cce_cluster_delete')
        p = self.load_policy({
            'name': 'delete-cce-cluster',
            'resource': 'huaweicloud.cce-cluster',
            'filters': [{
                'type': 'value',
                'key': 'metadata.name',
                'value': 'test-cluster-to-delete'
            }],
            'actions': [{
                'type': 'delete',
                'delete_evs': True,  # Delete associated EVS disks
                'delete_eni': True,  # Delete associated ENI
                'delete_net': False,  # Keep network resources
                'delete_obs': False  # Keep OBS storage
            }]
        }, session_factory=factory)
        resources = p.run()
        # Verify resources were processed
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['metadata']
                         ['name'], 'test-cluster-to-delete')

    def test_cluster_hibernate_action(self):
        """Test CCE cluster hibernate operation"""
        factory = self.replay_flight_data('cce_cluster_hibernate')
        p = self.load_policy({
            'name': 'hibernate-cce-cluster',
            'resource': 'huaweicloud.cce-cluster',
            'filters': [{
                'type': 'value',
                'key': 'status.phase',
                'value': 'Available'  # Only hibernate clusters in available state
            }],
            'actions': [{
                'type': 'hibernate'
            }]
        }, session_factory=factory)
        resources = p.run()
        # Verify available clusters were hibernated
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['status']['phase'], 'Available')

    def test_cluster_awake_action(self):
        """Test CCE cluster awake operation"""
        factory = self.replay_flight_data('cce_cluster_awake')
        p = self.load_policy({
            'name': 'awake-cce-cluster',
            'resource': 'huaweicloud.cce-cluster',
            'filters': [{
                'type': 'value',
                'key': 'status.phase',
                'value': 'Hibernating'  # Only awake hibernating clusters
            }],
            'actions': [{
                'type': 'awake'
            }]
        }, session_factory=factory)
        resources = p.run()
        # Verify hibernating clusters were awakened
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['status']['phase'], 'Hibernating')

    def test_cluster_update_action(self):
        """Test CCE cluster update operation"""
        factory = self.replay_flight_data('cce_cluster_update')
        p = self.load_policy({
            'name': 'update-cce-cluster',
            'resource': 'huaweicloud.cce-cluster',
            'filters': [{
                'type': 'value',
                'key': 'metadata.name',
                'value': 'test-cluster-to-update'
            }],
            'actions': [{
                'type': 'update',
                'spec': {
                    'description': 'updated_description',  # Update cluster description
                    # Custom SAN
                    'custom_san': ['example.com', 'test.example.com'],
                    'deletion_protection': True  # Enable deletion protection
                },
                'metadata': {
                    'alias': 'updated-cluster-alias'  # Update cluster alias
                }
            }]
        }, session_factory=factory)
        resources = p.run()
        # Verify clusters were updated
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['metadata']
                         ['name'], 'test-cluster-to-update')


class CceNodePoolTest(BaseTest):
    """Test CCE node pool resource query and operations"""

    def test_nodepool_query(self):
        """Test CCE node pool resource query"""
        factory = self.replay_flight_data('cce_nodepool_query')
        p = self.load_policy({
            'name': 'list-cce-nodepools',
            'resource': 'huaweicloud.cce-nodepool'},
            session_factory=factory)
        resources = p.run()
        # Verify VCR: cce_nodepool_query should contain node pools
        self.assertEqual(len(resources), 1)
        # Verify VCR: value should match 'name' in cce_nodepool_query
        self.assertEqual(resources[0]['metadata']['name'], 'test-nodepool')

    def test_nodepool_delete_action(self):
        """Test CCE node pool delete operation"""
        factory = self.replay_flight_data('cce_nodepool_delete')
        p = self.load_policy({
            'name': 'delete-cce-nodepool',
            'resource': 'huaweicloud.cce-nodepool',
            'filters': [{
                'type': 'value',
                'key': 'metadata.uid',
                'value': 'test-nodepool-uid'
            }],
            'actions': [{
                'type': 'delete'
            }]
        }, session_factory=factory)
        resources = p.run()
        # Verify empty node pools were deleted
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['metadata']['uid'], 'test-nodepool-uid')

    def test_nodepool_update_action(self):
        """Test CCE node pool update operation"""
        factory = self.replay_flight_data('cce_nodepool_update')
        p = self.load_policy({
            'name': 'update-cce-nodepool',
            'resource': 'huaweicloud.cce-nodepool',
            'filters': [{
                'type': 'value',
                'key': 'metadata.name',
                'value': 'test-nodepool-to-update'
            }],
            'actions': [{
                'type': 'update',
                'metadata': {
                    'name': 'updated-nodepool-name',
                },
                'spec': {
                    'initial_node_count': 3,
                }
            }]
        }, session_factory=factory)
        resources = p.run()
        # Verify node pools were updated
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['metadata']
                         ['name'], 'test-nodepool-to-update')


class CceNodeTest(BaseTest):
    """Test CCE node resource query and operations"""

    def test_node_query(self):
        """Test CCE node resource query"""
        factory = self.replay_flight_data('cce_node_query')
        p = self.load_policy({
            'name': 'list-cce-nodes',
            'resource': 'huaweicloud.cce-node'},
            session_factory=factory)
        resources = p.run()
        # Verify VCR: cce_node_query should contain nodes
        self.assertEqual(len(resources), 1)
        # Verify VCR: value should match 'name' in cce_node_query
        self.assertEqual(resources[0]['metadata']['name'], 'test-node')

    def test_node_delete_action(self):
        """Test CCE node delete operation"""
        factory = self.replay_flight_data('cce_node_delete')
        p = self.load_policy({
            'name': 'delete-failed-nodes',
            'resource': 'huaweicloud.cce-node',
            'filters': [{
                'type': 'value',
                'key': 'status.phase',
                'value': 'Error'  # Only delete error state nodes
            }],
            'actions': [{
                'type': 'delete'
            }]
        }, session_factory=factory)
        resources = p.run()
        # Verify error nodes were deleted
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['status']['phase'], 'Error')


class CceAddonTemplateTest(BaseTest):
    """Test CCE addon template resource query and operations"""

    def test_addontemplate_query(self):
        """Test CCE addon template resource query"""
        factory = self.replay_flight_data('cce_addontemplate_query')
        p = self.load_policy({
            'name': 'list-cce-addontemplates',
            'resource': 'huaweicloud.cce-addontemplate'},
            session_factory=factory)
        resources = p.run()
        # Verify VCR: cce_addontemplate_query should contain addon templates
        self.assertEqual(len(resources), 1)
        # Verify VCR: value should match 'name' in cce_addontemplate_query
        self.assertEqual(resources[0]['metadata']
                         ['name'], 'test-addon-template')


class CceAddonInstanceTest(BaseTest):
    """Test CCE addon instance resource query and operations"""

    def test_addoninstance_query(self):
        """Test CCE addon instance resource query"""
        factory = self.replay_flight_data('cce_addoninstance_query')
        p = self.load_policy({
            'name': 'list-cce-addoninstances',
            'resource': 'huaweicloud.cce-addoninstance'},
            session_factory=factory)
        resources = p.run()
        # Verify VCR: cce_addoninstance_query should contain addon instances
        self.assertEqual(len(resources), 1)
        # Verify VCR: value should match 'name' in cce_addoninstance_query
        self.assertEqual(resources[0]['metadata']
                         ['name'], 'test-addon-instance')

    def test_addoninstance_delete_action(self):
        """Test CCE addon instance delete operation"""
        factory = self.replay_flight_data('cce_addoninstance_delete')
        p = self.load_policy({
            'name': 'delete-abnormal-addons',
            'resource': 'huaweicloud.cce-addoninstance',
            'filters': [{
                'type': 'value',
                'key': 'metadata.uid',
                'value': 'test-addon'
            }],
            'actions': [{
                'type': 'delete'
            }]
        }, session_factory=factory)
        resources = p.run()
        # Verify abnormal addon instances were deleted
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['metadata']['uid'], 'test-addon')


class CceChartTest(BaseTest):
    """Test CCE chart resource query and operations"""

    def test_chart_query(self):
        """Test CCE chart resource query"""
        factory = self.replay_flight_data('cce_chart_query')
        p = self.load_policy({
            'name': 'list-cce-charts',
            'resource': 'huaweicloud.cce-chart'},
            session_factory=factory)
        resources = p.run()
        # Verify VCR: cce_chart_query should contain charts
        self.assertEqual(len(resources), 1)
        # Verify VCR: value should match 'name' in cce_chart_query
        self.assertEqual(resources[0]['name'], 'test-chart')

    def test_chart_delete_action(self):
        """Test CCE chart delete operation"""
        factory = self.replay_flight_data('cce_chart_delete')
        p = self.load_policy({
            'name': 'delete-unused-charts',
            'resource': 'huaweicloud.cce-chart',
            'filters': [{
                'type': 'value',
                'key': 'name',
                'value': 'unused-chart'
            }],
            'actions': [{
                'type': 'delete'
            }]
        }, session_factory=factory)
        resources = p.run()
        # Verify unused charts were deleted
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['name'], 'unused-chart')


class CceReleaseTest(BaseTest):
    """Test CCE release resource query and operations"""

    def test_release_query(self):
        """Test CCE release resource query"""
        factory = self.replay_flight_data('cce_release_query')
        p = self.load_policy({
            'name': 'list-cce-releases',
            'resource': 'huaweicloud.cce-release'},
            session_factory=factory)
        resources = p.run()
        # Verify VCR: cce_release_query should contain releases
        self.assertEqual(len(resources), 1)
        # Verify VCR: value should match 'name' in cce_release_query
        self.assertEqual(resources[0]['name'], 'test-release')

    def test_release_delete_action(self):
        """Test CCE release delete operation"""
        factory = self.replay_flight_data('cce_release_delete')
        p = self.load_policy({
            'name': 'delete-failed-releases',
            'resource': 'huaweicloud.cce-release',
            'filters': [{
                'type': 'value',
                'key': 'name',
                'value': 'test-release'
            }],
            'actions': [{
                'type': 'delete'
            }]
        }, session_factory=factory)
        resources = p.run()
        # Verify failed releases were deleted
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['name'], 'test-release')
