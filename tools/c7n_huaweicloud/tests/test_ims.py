# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class ImsTest(BaseTest):

    def test_ims_query(self):
        factory = self.replay_flight_data("ims_image_query")
        p = self.load_policy(
            {"name": "ims_query", "resource": "huaweicloud.ims"},
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_ims_deregister(self):
        factory = self.replay_flight_data("ims_image_query")
        p = self.load_policy(
            {
                "name": "deregister",
                "resource": "huaweicloud.ims",
                "filters": [{"type": "value", "key": "id", "value": "image_id"}],
                "actions": ["deregister"],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_ims_image_age_success(self):
        factory = self.replay_flight_data("ims_image_query")
        p = self.load_policy(
            {
                "name": "image-age",
                "resource": "huaweicloud.ims",
                "filters": [{"type": "image-age", "days": 1}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_ims_image_age_fail(self):
        factory = self.replay_flight_data("ims_image_query")
        p = self.load_policy(
            {
                "name": "image-age",
                "resource": "huaweicloud.ims",
                "filters": [{"type": "image-age", "days": 100000}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 0)

    def test_ims_image_attribute_success(self):
        factory = self.replay_flight_data("ims_image_query")
        p = self.load_policy(
            {
                "name": "image-attribute",
                "resource": "huaweicloud.ims",
                "filters": [
                    {
                        "type": "image-attribute",
                        "attribute": "__os_type",
                        "key": "Value",
                        "value": "Windows",
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_ims_image_attribute_fail(self):
        factory = self.replay_flight_data("ims_image_query")
        p = self.load_policy(
            {
                "name": "image-attribute",
                "resource": "huaweicloud.ims",
                "filters": [
                    {
                        "type": "image-attribute",
                        "attribute": "__os_type",
                        "key": "Value",
                        "value": "Linux",
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 0)

    def test_ims_set_permissions(self):
        factory = self.replay_flight_data("ims_image_query")
        p = self.load_policy(
            {
                "name": "set-permissions",
                "resource": "huaweicloud.ims",
                "filters": [{"type": "value", "key": "id", "value": "image_id"}],
                "actions": [
                    {"type": "set-permissions", "op": "add", "projects": ["proiect_id"]}
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_ims_cancel_launch_permission(self):
        factory = self.replay_flight_data("ims_image_query")
        p = self.load_policy(
            {
                "name": "cancel-launch-permission",
                "resource": "huaweicloud.ims",
                "filters": [{"type": "value", "key": "id", "value": "image_id"}],
                "actions": [
                    {
                        "type": "cancel-launch-permission",
                        "status": "accepted",
                        "project_id": "proiect_id",
                        "image_ids": ["image_id"]
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_ims_copy(self):
        factory = self.replay_flight_data("ims_image_query")
        p = self.load_policy(
            {
                "name": "copy",
                "resource": "huaweicloud.ims",
                "filters": [{"type": "value", "key": "id", "value": "image_id"}],
                "actions": [{"type": "copy", "name": "test", "description": "123"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
