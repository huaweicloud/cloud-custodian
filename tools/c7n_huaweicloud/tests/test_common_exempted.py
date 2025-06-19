# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class ExemptedTest(BaseTest):

    def test_exempted_workspace_desktop_by_tags(self):
        factory = self.replay_flight_data('common_exempted')
        p = self.load_policy({
            "name": "exempted-workspace-desktop-tag",
            "resource": "huaweicloud.workspace-desktop",
            "filters": [{
                "type": "exempted",
                "field": "tags",
                "exempted_values": ["k1", "k2"]
            }]
        }, session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_restricted_workspace_desktop_by_tags(self):
        factory = self.replay_flight_data('common_restricted')
        p = self.load_policy({
            "name": "restricted-workspace-desktop-tag",
            "resource": "huaweicloud.workspace-desktop",
            "filters": [{
                "type": "restricted",
                "field": "tags",
                "restricted_values": ["k1"]
            }]
        }, session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
