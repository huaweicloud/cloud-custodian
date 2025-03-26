# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import os

from huaweicloud_common import BaseTest

HUAWEICLOUD_CONFIG_GLOBAL = {
    'HUAWEI_DEFAULT_REGION': 'cn-north-4',
    'HUAWEI_ACCESS_KEY_ID': 'access_key_id',
    'HUAWEI_SECRET_ACCESS_KEY': 'secret_access_key',
    'HUAWEI_PROJECT_ID': 'cn-north-4',
}


def init_huaweicloud_config_global():
    for k, v in HUAWEICLOUD_CONFIG_GLOBAL.items():
        os.environ[k] = v


HUAWEICLOUD_CONFIG = {
    'HUAWEI_DEFAULT_REGION': 'ap-southeast-1',
    'HUAWEI_ACCESS_KEY_ID': 'access_key_id',
    'HUAWEI_SECRET_ACCESS_KEY': 'secret_access_key',
    'HUAWEI_PROJECT_ID': 'ap-southeat-1',
}


def init_huaweicloud_config():
    for k, v in HUAWEICLOUD_CONFIG.items():
        os.environ[k] = v


class TMSTest(BaseTest):
    def test_tms_tag_count(self):
        init_huaweicloud_config_global()
        factory = self.replay_flight_data('tms-test')
        p = self.load_policy({
            'name': 'all-volumes',
            'resource': 'huaweicloud.volume',
            "filters": [{
                "type": "tag-count",
                "count": 3,
                "op": "gte"
            }]
        },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        init_huaweicloud_config()

    def test_tms_tag(self):
        init_huaweicloud_config_global()
        factory = self.replay_flight_data('tms-test')
        p = self.load_policy({
            'name': 'all-volumes',
            'resource': 'huaweicloud.volume',
            'actions': [{
                "type": "tag",
                "tags": {
                    "test-key": "test-value",
                }
            }]
        },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        init_huaweicloud_config()

    def test_tms_untag(self):
        init_huaweicloud_config_global()
        factory = self.replay_flight_data('tms-test')
        p = self.load_policy({
            'name': 'all-volumes',
            'resource': 'huaweicloud.volume',
            'actions': [{
                "type": "untag",
                "tags": [
                    "test-key",
                ]
            }]
        },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        init_huaweicloud_config()

    def test_tms_rename_tag(self):
        init_huaweicloud_config_global()
        factory = self.replay_flight_data('tms-test')
        p = self.load_policy({
            'name': 'all-volumes',
            'resource': 'huaweicloud.volume',
            'actions': [{
                "type": "rename-tag",
                "old_key": "test-key",
                "new_key": "test-key-new"
            }]
        },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        init_huaweicloud_config()

    def test_tms_normalize_tag(self):
        init_huaweicloud_config_global()
        factory = self.replay_flight_data('tms-test')
        p = self.load_policy({
            'name': 'all-volumes',
            'resource': 'huaweicloud.volume',
            'actions': [{
                "type": "normalize-tag",
                "action": "strip",
                "key": "test-key",
                "old_sub_str": "123"
            }]
        },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        init_huaweicloud_config()

    def test_tms_tag_trim(self):
        init_huaweicloud_config_global()
        factory = self.replay_flight_data('tms-test')
        p = self.load_policy({
            'name': 'all-volumes',
            'resource': 'huaweicloud.volume',
            'actions': [{
                "type": "tag-trim",
                "space": 5
            }]
        },
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        init_huaweicloud_config()
