# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class CbrProtectableTest(BaseTest):
    def test_protectable_unassociated_filter(self):
        factory = self.replay_flight_data('cbr_protectable_unassociated_with_vault')
        p = self.load_policy(
            {
                'name': 'cbr_protectable_associate_server_with_vault',
                'resource': 'huaweicloud.cbr-protectable',
                'filters': [
                    {
                        "and": [
                            {
                                "type": "value",
                                "op": "contains",
                                "key": "detail.tags",
                                "value": "backup_policy=45Dd"
                            },
                            {
                                "type": "value",
                                "key": "protectable.vault",
                                "value": "empty"
                            }
                        ]
                    }
                ],
        },
        session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['id'], 'bf114c19-b4e6-4a28-b9b5-6ad7fde8f2be')

    def test_associate_server_with_enough_vault(self):
        factory = self.replay_flight_data('cbr_associate_server_with_enough_vault')
        p = self.load_policy(
           {
               "name": "cbr_associate_server_with_enough_vault",
               "resource": "huaweicloud.cbr-protectable",
               "actions": [
                   {
                       "type": "associate_server_with_vault",
                       "backup_policy_id": "bc715c62-f4ed-4fc0-9e78-ce43b9409a39",
                       "consistent_level": "crash_consistent",
                       "object_type": "server",
                       "protect_type": "backup",
                       "size": 100,
                       "charging_mode": "post_paid",
                       "period_type": "year",
                       "period_num": 1,
                       "is_auto_renew": True,
                       "is_auto_pay": True,
                       "name": "new_vault"
                   }
               ]
           },
           session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 0)

    def test_associate_server_with_inadequate_vault(self):
        factory = self.replay_flight_data('cbr_associate_server_with_inadequate_vault')
        p = self.load_policy(
            {
                'name': 'cbr_associate_server_with_inadequate_vault',
                'resource': 'huaweicloud.cbr-protectable',
                'actions': [{'type': 'associate_server_with_vault',
                             'backup_policy_id': "a88a3421-f57e-49a4-b0ab-0ba334313b48",
                             'consistent_level': "crash_consistent",
                             'object_type': "server",
                             'protect_type': "backup",
                             'size': 100,
                             'charging_mode': "post_paid",
                             'period_type': "year",
                             'period_num': 1,
                             'is_auto_renew': True,
                             'is_auto_pay': True,
                             'name': "new_vault",
                             }],
            },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 0)
