# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class SfsTurboTest(BaseTest):

    def test_sfsturbo_query(self):
        factory = self.replay_flight_data('sfsturbo_query')
        p = self.load_policy({
            'name': 'all-sfsturbo',
            'resource': 'huaweicloud.sfsturbo'},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 4)
        self.assertEqual(resources[0]['name'], "sfs-turbo-zy")

    def test_sfsturbo_not_protected_by_backup(self):
        factory = self.replay_flight_data('sfsturbo_not_protected_by_backup')
        p = self.load_policy({
            'name': 'sfsturbo_not_protected_by_backup',
            'resource': 'huaweicloud.sfsturbo',
            'filters': ['not-protected-by-backup']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 3)
        self.assertEqual(resources[0]['name'], "hongkong-az3-1-evs-consistent")
        self.assertEqual(resources[0]['id'], "c5f8d19c-f158-4a1a-867e-df44f6c4d068")

    def test_last_backup_create_exceed_safe_time_sfsturbo(self):
        factory = self.replay_flight_data('sfsturbo_last_backup_exceed_safe_time_interval')
        p = self.load_policy({
            'name': 'last-backup-exceed-safe-time-interval',
            'resource': 'huaweicloud.sfsturbo',
            'filters': [{'type': 'last-backup-exceed-safe-time-interval', 'interval': 1,
                         'reference_time': '2025-03-22T05:12:52.866374'}]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 3)
        self.assertEqual(resources[0]['name'], "hongkong-az3-1-evs-consistent")
        self.assertEqual(resources[0]['id'], "c5f8d19c-f158-4a1a-867e-df44f6c4d068")
        self.assertEqual(resources[1]['name'], "hongkong-az2-1-evs-consistent")
        self.assertEqual(resources[1]['id'], "33a9d16c-ea90-41ee-8dc0-01884204cf95")
        self.assertEqual(resources[2]['name'], "hongkong-az1-1-evs-consistent")
        self.assertEqual(resources[2]['id'], "67c60dbb-d4fa-47aa-ae1d-cf8c8c75584e")

    def test_delete_unencrypted_sfsturbo(self):
        factory = self.replay_flight_data('sfsturbo_query')
        p = self.load_policy({
            'name': 'sfsturbo-encrypted-check',
            'resource': 'huaweicloud.sfsturbo',
            'filters': [{"crypt_key_id": "empty"}],
            'actions': ['delete']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['name'], "sfs-turbo-zy")
