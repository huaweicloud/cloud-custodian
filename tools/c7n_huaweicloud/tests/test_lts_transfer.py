# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class TransferTest(BaseTest):
    def test_transfer_filter(self):
        factory = self.replay_flight_data('lts_transfer_filter')
        p = self.load_policy({
            'name': 'filter-transfer',
            'resource': 'huaweicloud.lts-transfer',
            'filters': [{
                'type': 'transfer-logGroupStream-id',
                'metadata': {
                    "log_group_id": "123",
                    "log_stream_id": "321"
                }
            }]
        },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_create_transfer(self):
        factory = self.replay_flight_data("lts_transfer_create")
        p = self.load_policy({
            "name": "createTransferForStream",
            'resource': 'huaweicloud.lts-transfer',
            "filters": [{
                "type": "value",
                "key": "log_group_id",
                "value": "123"
            }],
            "actions": [{
                "type": "create-transfer",
                "log_group_id": "8ba9e43f-be60-4d8c-9015-xxxxxxxxxxxx",
                "log_streams": [{"log_stream_id": "c776e1a7-8548-430a-afe5-xxxxxxxxxxxx"}],
                "log_transfer_type": "OBS",
                "log_transfer_mode": "cycle",
                "log_storage_format": "JSON",
                "log_transfer_status": "ENABLE",
                "obs_period": 2,
                "obs_period_unit": "min",
                "obs_bucket_name": "xianggangtest001"
            }]
        },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
