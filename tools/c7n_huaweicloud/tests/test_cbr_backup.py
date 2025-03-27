# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class CbrBackupTest(BaseTest):

    def test_backup_list(self):
        factory = self.replay_flight_data('cbr_backup_list')
        p = self.load_policy(
            {
             'name': 'list_backups',
             'resource': 'huaweicloud.cbr-backup',
        },
        session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 3)
        self.assertEqual(resources[0]['id'], '924c9b1f-9056-4a13-8ac2-19c02f27b699')
        self.assertEqual(resources[1]['id'], 'f2aab24a-b8a0-4577-a5d1-6df33f5c7e69')
        self.assertEqual(resources[2]['id'], '79fdfc8b-b7dd-45b0-aa3a-b643b2e22d2f')

    def test_backup_unencrypted_filter(self):
        factory = self.replay_flight_data('cbr_backup_unencrypted')
        p = self.load_policy(
            {
             'name': 'cbr_backup_unencrypted',
             'resource': 'huaweicloud.cbr-backup',
             'filters': [{'and':
                 [{'type': 'value',
                  'key': 'extend_info.encrypted',
                  'value': False},
                 {'type': 'value',
                  'key': 'resource_type',
                  'value': 'OS::Cinder::Volume'},
             ]}],
        },
        session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['id'], 'f2aab24a-b8a0-4577-a5d1-6df33f5c7e69')

    def test_backup_delete_action(self):
        factory = self.replay_flight_data('cbr_backup_delete')
        p = self.load_policy(
            {
                'name': 'cbr_backup_delete',
                'resource': 'huaweicloud.cbr-backup',
                'actions': ['delete'],
            },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['id'], 'f2aab24a-b8a0-4577-a5d1-6df33f5c7e69')
