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
