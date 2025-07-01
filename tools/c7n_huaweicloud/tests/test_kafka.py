# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import patch  # 导入 patch

from huaweicloud_common import BaseTest


# from unittest.mock import patch # 可选，用于更复杂的模拟场景


class KafkaInstanceTest(BaseTest):

    # =========================
    # Resource Query Test
    # =========================
    def test_kafka_query(self):
        factory = self.replay_flight_data('kafka_query')
        p = self.load_policy({
            'name': 'kafka-query-test',
            'resource': 'huaweicloud.dms-kafka'},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)  # 假设录像带中有1个实例
        self.assertEqual(resources[0]['name'], "kafka-instance-example")  # 假设实例名称

    # =========================
    # Filter Tests
    # =========================
    @patch('c7n_huaweicloud.resources.vpc.SecurityGroup.get_resources')  # 指定要 mock 的目标
    def test_kafka_filter_security_group(self, mock_get_sg_resources):  # 接收 mock 对象
        # 配置 mock 返回值
        # 需要包含与 VCR 中 securityGroupId 匹配的 id
        mock_security_group_data = [{
            'id': 'securityGroupId',
            'name': 'cluster-yhr-test-cce-node-klt95',  # 名称可以来自VCR，确保id匹配即可
            'description': 'Mocked security group data',
            # 可以根据需要添加更多字段，但 'id' 是关键
        }]
        mock_get_sg_resources.return_value = mock_security_group_data

        factory = self.replay_flight_data('kafka_filter_sg')
        p = self.load_policy({
            'name': 'kafka-filter-sg-test',
            'resource': 'huaweicloud.dms-kafka',
            'filters': [{
                'type': 'security-group',
                'key': 'id',  # 或 name
                'value': 'securityGroupId'  # 确保此值与 mock 数据中的 id 匹配
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)  # 假设有1个匹配实例
        # 验证 mock 是否被调用 (可选)
        mock_get_sg_resources.assert_called_once_with(['securityGroupId'])

    def test_kafka_filter_age(self):
        factory = self.replay_flight_data('kafka_filter_age')
        # 测试创建时间大于等于1天的实例
        p_ge = self.load_policy({
            'name': 'kafka-filter-age-ge-test',
            'resource': 'huaweicloud.dms-kafka',
            'filters': [{'type': 'age', 'days': 1, 'op': 'gt'}]},  # 大于等于
            session_factory=factory)
        resources_ge = p_ge.run()
        self.assertEqual(len(resources_ge), 1)  # 假设录像带中的实例满足条件

        # 测试创建时间小于1000天的实例 (假设实例满足)
        p_lt = self.load_policy({
            'name': 'kafka-filter-age-lt-test',
            'resource': 'huaweicloud.dms-kafka',
            'filters': [{'type': 'age', 'days': 2000, 'op': 'lt'}]},  # 小于
            session_factory=factory)
        resources_lt = p_lt.run()
        self.assertEqual(len(resources_lt), 1)

    def test_kafka_filter_config_compliance(self):
        factory = self.replay_flight_data('kafka_filter_config')
        # 测试配置项等于期望值 (假设 auto.create.topics.enable 为 true)
        p_eq_true = self.load_policy({
            'name': 'kafka-filter-config-eq-true-test',
            'resource': 'huaweicloud.dms-kafka',
            'filters': [{
                'type': 'config-compliance',
                'key': 'auto.create.groups.enable',
                'op': 'eq',
                'value': True  # 测试布尔值比较
            }]},
            session_factory=factory)
        resources_eq_true = p_eq_true.run()
        self.assertEqual(len(resources_eq_true), 1)

        p_ne = self.load_policy({
            'name': 'kafka-filter-config-ne-test',
            'resource': 'huaweicloud.dms-kafka',
            'filters': [{
                'type': 'config-compliance',
                'key': 'message.max.bytes',
                'op': 'ne',
                'value': 10485759  # 测试数字比较
            }]},
            session_factory=factory)
        resources_ne = p_ne.run()
        self.assertEqual(len(resources_ne), 1)

        p_ne = self.load_policy({
            'name': 'kafka-filter-config-ne-test',
            'resource': 'huaweicloud.dms-kafka',
            'filters': [{
                'type': 'config-compliance',
                'key': 'message.max.bytes',
                'op': 'ne',
                'value': 10485760  # 测试数字比较
            }]},
            session_factory=factory)
        resources_ne = p_ne.run()
        self.assertEqual(len(resources_ne), 0)

        # 边界：测试配置项不存在 (需要特定录像带)
        # factory_missing_key = self.replay_flight_data('kafka_filter_config_missing')
        # p_missing = ...
        # resources_missing = p_missing.run()
        # self.assertEqual(len(resources_missing), 0) # 应该被过滤掉

        # 边界：测试 API 错误 (需要特定录像带)
        # factory_api_error = self.replay_flight_data('kafka_filter_config_api_error')
        # p_error = ...
        # resources_error = p_error.run() # 应该能处理异常并继续
        # self.assertEqual(len(resources_error), 0)

    # =========================
    # Action Tests
    # =========================

    def test_kafka_action_set_config(self):
        factory = self.replay_flight_data('kafka_action_set_config')
        p = self.load_policy({
            'name': 'kafka-action-set-config-test',
            'resource': 'huaweicloud.dms-kafka',
            'filters': [{  # 假设找到需要修改配置的实例
                'type': 'config-compliance',
                'key': 'enable.log.collection',
                'value': False
            }],
            'actions': [{
                'type': 'set-config',
                'config': {
                    'enable.log.collection': True,  # 修改布尔值
                    'retention.hours': 168  # 修改数字 (会被转为字符串)
                }
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
