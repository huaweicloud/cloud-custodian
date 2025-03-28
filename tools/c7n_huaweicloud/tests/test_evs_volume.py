# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class VolumeTest(BaseTest):

    def test_volume_query(self):
        factory = self.replay_flight_data('evs_volume_query')
        p = self.load_policy({
             'name': 'all-volumes',
             'resource': 'huaweicloud.evs-volume'},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['name'], "custodian-volume")
        self.assertEqual(resources[0]['volume_type'], "GPSSD")

    def test_volume_not_protected_by_backup_filter(self):
        factory = self.replay_flight_data('evs_volume_not_protected_by_backup')
        p = self.load_policy({
            'name': 'evs_volume_not_protected_by_backup',
            'resource': 'huaweicloud.evs-volume',
            'filters': ['not-protected-by-backup']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['name'], "volume-not-protected-by-backup")
        self.assertEqual(resources[0]['volume_type'], "GPSSD")

    def test_last_backup_create_exceed_safe_time_volumes_filter(self):
        factory = self.replay_flight_data('evs_last_backup_exceed_safe_time_interval')
        p = self.load_policy({
            'name': 'last-backup-exceed-safe-time-interval',
            'resource': 'huaweicloud.evs-volume',
            'filters': [{'type': 'last-backup-exceed-safe-time-interval',
                         'interval': 1, 'reference_time': '2025-03-21T10:12:52.866374'}]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 2)
        self.assertEqual(resources[0]['name'], "volume-backup-exceed-time")
        self.assertEqual(resources[0]['volume_type'], "GPSSD")
        self.assertEqual(resources[1]['name'], "volume-has-no-backup")
        self.assertEqual(resources[1]['volume_type'], "GPSSD")

    def test_volume_age_filter(self):
        factory = self.replay_flight_data('evs_volume_query')
        p = self.load_policy({
            'name': 'volume-age',
            'resource': 'huaweicloud.evs-volume',
            'filters': [{'type': 'volume-age', 'days': 1, 'op': 'ge'}]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['name'], "custodian-volume")
        self.assertEqual(resources[0]['volume_type'], "GPSSD")

    def test_volume_delete_action(self):
        factory = self.replay_flight_data('evs_volume_delete')
        p = self.load_policy({
            'name': 'evs_volume_delete',
            'resource': 'huaweicloud.evs-volume',
            'actions': ['delete']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['name'], "custodian-volume")
        self.assertEqual(resources[0]['volume_type'], "GPSSD")

    def test_volume_detach_action(self):
        factory = self.replay_flight_data('evs_volume_detach')
        p = self.load_policy({
            'name': 'evs_volume_detach',
            'resource': 'huaweicloud.evs-volume',
            'actions': ['detach']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['name'], "custodian-volume")
        self.assertEqual(resources[0]['volume_type'], "GPSSD")

    def test_volume_extend_action(self):
        factory = self.replay_flight_data('evs_volume_extend')
        p = self.load_policy({
            'name': 'evs_volume_extend',
            'resource': 'huaweicloud.evs-volume',
            'actions': [{'type': 'extend', 'size': 20}]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['name'], "custodian-volume")
        self.assertEqual(resources[0]['volume_type'], "GPSSD")

    def test_volume_create_snapshot_action(self):
        factory = self.replay_flight_data('evs_volume_snapshot_create')
        p = self.load_policy({
            'name': 'evs_volume_snapshot_create',
            'resource': 'huaweicloud.evs-volume',
            'actions': [{'type': 'snapshot', 'force': True}]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['name'], "custodian-volume")
        self.assertEqual(resources[0]['volume_type'], "GPSSD")

    def test_volume_add_to_cbr_vault_action(self):
        factory = self.replay_flight_data('evs_volume_add_to_cbr_vault')
        p = self.load_policy({
            'name': 'evs_volume_add_to_cbr_vault',
            'resource': 'huaweicloud.evs-volume',
            'actions': [{'type': 'add-volume-to-vault', 'vault_id': 'mock_vault_id'}]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['name'], "custodian-volume")
        self.assertEqual(resources[0]['volume_type'], "GPSSD")

    def test_volume_vault_associate_to_policy_action(self):
        factory = self.replay_flight_data('evs_volume_vault_associate_to_policy')
        p = self.load_policy({
            'name': 'evs_volume_vault_associate_to_policy',
            'resource': 'huaweicloud.evs-volume',
            'actions': [{'type': 'associate-volume-vault-to-policy',
                         'policy_id': 'mock_vault_policy_id'}]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['name'], "custodian-volume")
        self.assertEqual(resources[0]['volume_type'], "GPSSD")

    def test_encrypt_instance_data_volumes_action(self):
        factory = self.replay_flight_data('evs_encrypt_instance_data_volumes')
        p = self.load_policy({
            'name': 'encrypt-instance-data-volumes',
            'resource': 'huaweicloud.evs-volume',
            'actions': [{'type': 'encrypt-instance-data-volumes', 'key': 'mock_cmkid'}]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 3)

    def test_volume_create_backup_action(self):
        factory = self.replay_flight_data('evs_volume_backup_create')
        p = self.load_policy({
            'name': 'backup-volumes',
            'resource': 'huaweicloud.evs-volume',
            'actions': ['backup']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
