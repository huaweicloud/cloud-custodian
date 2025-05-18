# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from huaweicloud_common import BaseTest


class WorkspaceTest(BaseTest):
    """Test class for Huawei Cloud Workspace resources"""

    # =========================
    # Resource Query Tests
    # =========================
    def test_workspace_query(self):
        """Test basic workspace resource query"""
        factory = self.replay_flight_data('workspace_query')
        p = self.load_policy({
            'name': 'workspace-query-test',
            'resource': 'huaweicloud.workspace-desktop'},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['computer_name'], "test-desktop")
        # Verify tag normalization
        self.assertTrue('Tags' in resources[0])
        self.assertEqual(resources[0]['Tags'], {'environment': 'testing'})

    # =========================
    # Filter Tests
    # =========================
    def test_connection_status_filter(self):
        """Test connection status filter"""
        factory = self.replay_flight_data('workspace_connection_status')
        # Test equal operator
        p_eq = self.load_policy({
            'name': 'workspace-connection-status-eq',
            'resource': 'huaweicloud.workspace-desktop',
            'filters': [{
                'type': 'connection-status',
                'op': 'eq',
                'value': 'UNREGISTER'
            }]},
            session_factory=factory)
        resources_eq = p_eq.run()
        self.assertEqual(len(resources_eq), 1)

        # Test not equal operator
        p_ne = self.load_policy({
            'name': 'workspace-connection-status-ne',
            'resource': 'huaweicloud.workspace-desktop',
            'filters': [{
                'type': 'connection-status',
                'op': 'ne',
                'value': 'REGISTERED'
            }]},
            session_factory=factory)
        resources_ne = p_ne.run()
        self.assertEqual(len(resources_ne), 1)

        # Test in operator
        p_in = self.load_policy({
            'name': 'workspace-connection-status-in',
            'resource': 'huaweicloud.workspace-desktop',
            'filters': [{
                'type': 'connection-status',
                'op': 'in',
                'value': ['UNREGISTER', 'OFFLINE']
            }]},
            session_factory=factory)
        resources_in = p_in.run()
        self.assertEqual(len(resources_in), 1)

        # Test not-in operator
        p_not_in = self.load_policy({
            'name': 'workspace-connection-status-not-in',
            'resource': 'huaweicloud.workspace-desktop',
            'filters': [{
                'type': 'connection-status',
                'op': 'not-in',
                'value': ['REGISTERED', 'ONLINE']
            }]},
            session_factory=factory)
        resources_not_in = p_not_in.run()
        self.assertEqual(len(resources_not_in), 1)

    # =========================
    # Action Tests
    # =========================
    def test_delete_action(self):
        """Test delete action"""
        factory = self.replay_flight_data('workspace_delete')
        p = self.load_policy({
            'name': 'workspace-delete-test',
            'resource': 'huaweicloud.workspace-desktop',
            'filters': [{
                'type': 'connection-status',
                'op': 'eq',
                'value': 'UNREGISTER'
            }],
            'actions': ['delete']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_delete_batch_action(self):
        """Test batch delete action"""
        factory = self.replay_flight_data('workspace_delete_batch')
        p = self.load_policy({
            'name': 'workspace-delete-batch-test',
            'resource': 'huaweicloud.workspace-desktop',
            'filters': [{
                'type': 'connection-status',
                'op': 'eq',
                'value': 'UNREGISTER'
            }],
            'actions': ['delete']},
            session_factory=factory)
        resources = p.run()
        # Testing batch delete 2 desktops
        self.assertEqual(len(resources), 2)
