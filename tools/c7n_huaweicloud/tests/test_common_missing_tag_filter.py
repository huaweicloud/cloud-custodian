# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class MissingTagFilterTest(BaseTest):

    def test_missing_tag_filter_workspace_desktop_by_tags(self):
        factory = self.replay_flight_data('common_missing_tag_filter')
        p = self.load_policy({
            "name": "missing-tag-filter-workspace-desktop-tag",
            "resource": "huaweicloud.workspace-desktop",
            "filters": [{
                "type": "missing-tag-filter",
                "tags": [
                    {
                        "key": "k3",
                        "value": "^test.*$"
                    },
                    {
                        "key": "k4",
                        "value": "huaweicloud.com"
                    }
                ],
                "match": "missing-all"
            }]
        }, session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 0)
