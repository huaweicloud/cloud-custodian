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
                    "log_group_id": "cfddae22-6465-4b2f-8b19-123466021f88",
                    "log_stream_id": "b831798c-1798-4a9e-80c4-371402a97f30"
                }
            }]
        },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)

