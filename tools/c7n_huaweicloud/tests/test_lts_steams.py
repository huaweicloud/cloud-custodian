# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from huaweicloud_common import BaseTest


class LogStreamTest(BaseTest):
    """
    测试华为云LTS日志流资源的各种操作
    """

    def test_logstream_query(self):
        """
        测试基本的日志流查询功能
        确保可以正确列出所有日志流资源
        """
        factory = self.replay_flight_data('lts_logstream_query')
        p = self.load_policy({
            'name': 'all-logstreams',
            'resource': 'huaweicloud.lts-logstream'},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['log_group_id'], "b6b9332b-091f-4b22-b810-264318d2d664")
        self.assertEqual(resources[0]['log_group_name'], "lts-group-01nh")

    def test_logstream_filter_by_loggroup(self):
        """
        测试通过日志组过滤日志流的功能
        使用LogGroupFilter进行筛选
        """
        factory = self.replay_flight_data('lts_logstream_filter_by_loggroup')
        p = self.load_policy({
            'name': 'logstreams-by-group',
            'resource': 'huaweicloud.lts-logstream',
            'filters': [{
                'type': 'loggroup',
                'key': 'log_group_id',
                'value': 'b6b9332b-091f-4b22-b810-264318d2d664'
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['log_group_id'], "b6b9332b-091f-4b22-b810-264318d2d664")

    def test_logstream_filter_by_name(self):
        """
        测试通过名称过滤日志流
        使用标准值过滤器
        """
        factory = self.replay_flight_data('lts_logstream_filter_by_name')
        p = self.load_policy({
            'name': 'logstreams-by-name',
            'resource': 'huaweicloud.lts-logstream',
            'filters': [{
                'type': 'value',
                'key': 'log_group_name',
                'value': 'lts-group-01nh',
                'op': 'eq'
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['log_group_name'], "lts-group-01nh")
