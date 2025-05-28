# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class CbrVaultTest(BaseTest):

    def test_vault_list(self):
        factory = self.replay_flight_data('cbr_vault_list')
        p = self.load_policy(
            {
             'name': 'cbr_vault_list',
             'resource': 'huaweicloud.cbr-vault',
        },
        session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 4)
        self.assertEqual(resources[0]['id'], '06e844ba-d4bf-40be-b07f-c60d3c2ce679')
        self.assertEqual(resources[1]['id'], '42da2015-a512-481a-9c86-f02c08cffc10')
        self.assertEqual(resources[2]['id'], 'f52b25cd-b7af-46cc-9c04-3a5b21e23209')
        self.assertEqual(resources[3]['id'], '78fe6b2b-15e1-4fce-9cd9-4cbb5021fe92')

    def test_vault_untagged_filter(self):
        factory = self.replay_flight_data('cbr_vault_untagged')
        p = self.load_policy(
            {
                'name': 'cbr_vault_untagged',
                'resource': 'huaweicloud.cbr-vault',
                'filters': [{'tags': 'empty'}],
            },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 4)
        self.assertEqual(resources[0]['id'], '06e844ba-d4bf-40be-b07f-c60d3c2ce679')
        self.assertEqual(resources[1]['id'], '42da2015-a512-481a-9c86-f02c08cffc10')
        self.assertEqual(resources[2]['id'], 'f52b25cd-b7af-46cc-9c04-3a5b21e23209')
        self.assertEqual(resources[3]['id'], '78fe6b2b-15e1-4fce-9cd9-4cbb5021fe92')

    def test_vault_unassociated_with_policy(self):
        factory = self.replay_flight_data('cbr_vault_unassociated_with_policy')
        p = self.load_policy(
            {
                'name': 'cbr_vault_unassociated_with_policy',
                'resource': 'huaweicloud.cbr-vault',
                'filters': [{
                    'and': [{'type': 'unassociated'},
                            {'type': 'value',
                             'key': 'billing.protect_type',
                             'value': 'backup'},
                            ]
                }],
            },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 3)
        self.assertEqual(resources[0]['id'], '06e844ba-d4bf-40be-b07f-c60d3c2ce679')
        self.assertEqual(resources[1]['id'], '42da2015-a512-481a-9c86-f02c08cffc10')
        self.assertEqual(resources[2]['id'], '78fe6b2b-15e1-4fce-9cd9-4cbb5021fe92')

    def test_vault_add_tags_action(self):
        factory = self.replay_flight_data('cbr_vault_add_tags')
        p = self.load_policy(
            {
                'name': 'cbr_vault_add_tags',
                'resource': 'huaweicloud.cbr-vault',
                'actions': [{'type': 'add_tags', 'keys': ['1', '2'], 'values': ['1', '2']}],
            },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 4)
        self.assertEqual(resources[0]['id'], '06e844ba-d4bf-40be-b07f-c60d3c2ce679')
        self.assertEqual(resources[1]['id'], '42da2015-a512-481a-9c86-f02c08cffc10')
        self.assertEqual(resources[2]['id'], 'f52b25cd-b7af-46cc-9c04-3a5b21e23209')
        self.assertEqual(resources[3]['id'], '78fe6b2b-15e1-4fce-9cd9-4cbb5021fe92')

    def test_associate_vault_with_policy_action(self):
        factory = self.replay_flight_data('cbr_associate_vault_with_policy')
        p = self.load_policy(
            {
                'name': 'cbr_associate_vault_with_policy',
                'resource': 'huaweicloud.cbr-vault',
                'actions': [{'type': 'associate_vault_policy',
                             'day_backups': 0,
                             'week_backups': 0,
                             'month_backups': 0,
                             'year_backups': 0,
                             'max_backups': -1,
                             'retention_duration_days': 30,
                             'full_backup_interval': -1,
                             'timezone': "UTC+08:00",
                             }],
            },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 3)
        self.assertEqual(resources[0]['id'], '06e844ba-d4bf-40be-b07f-c60d3c2ce679')
        self.assertEqual(resources[1]['id'], '42da2015-a512-481a-9c86-f02c08cffc10')
        self.assertEqual(resources[2]['id'], '78fe6b2b-15e1-4fce-9cd9-4cbb5021fe92')

    def test_filter_without_specific_tags(self):
        factory = self.replay_flight_data('cbr_vault_filter_without_specific_tags')
        p = self.load_policy(
            {
                'name': 'cbr_vault_filter_without_specific_tags',
                'resource': 'huaweicloud.cbr-vault',
                'filters': [{'type': 'without_specific_tags',
                             'keys': ['owner-team-email', 'tech-team-email']}],
            },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 2)
