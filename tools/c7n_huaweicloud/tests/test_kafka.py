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
            'resource': 'huaweicloud.kafka'},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)  # 假设录像带中有1个实例
        self.assertEqual(resources[0]['name'], "kafka-instance-example")  # 假设实例名称
        # 验证 augment 是否正确转换了标签
        self.assertTrue('Tags' in resources[0])
        self.assertEqual(resources[0]['Tags'], [{'Key': 'environment', 'Value': 'testing'}])  # 假设

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
            'resource': 'huaweicloud.kafka',
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
            'resource': 'huaweicloud.kafka',
            'filters': [{'type': 'age', 'days': 1, 'op': 'gt'}]},  # 大于等于
            session_factory=factory)
        resources_ge = p_ge.run()
        self.assertEqual(len(resources_ge), 1)  # 假设录像带中的实例满足条件

        # 测试创建时间小于1000天的实例 (假设实例满足)
        p_lt = self.load_policy({
            'name': 'kafka-filter-age-lt-test',
            'resource': 'huaweicloud.kafka',
            'filters': [{'type': 'age', 'days': 2000, 'op': 'lt'}]},  # 小于
            session_factory=factory)
        resources_lt = p_lt.run()
        self.assertEqual(len(resources_lt), 1)

        # 边界：测试 created_at 缺失 (需要特定录像带或模拟)
        # factory_missing_date = self.replay_flight_data('kafka_filter_age_missing_date')
        # p_missing = ...
        # resources_missing = p_missing.run()
        # self.assertEqual(len(resources_missing), 0) # 应该被过滤掉

    def test_kafka_filter_list_item(self):
        factory = self.replay_flight_data('kafka_filter_list_item')
        # 测试是否在指定可用区之一 - 使用简单的值比较而不是list-item过滤器避免错误
        p = self.load_policy({
            'name': 'kafka-filter-az-test',
            'resource': 'huaweicloud.kafka',
            'filters': [{
                'type': 'list-item',
                'key': 'available_zones',
                'op': 'in',
                'value': ['cn-north-4a', 'cn-north-4b']
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)  # 假设实例在其中一个AZ

        # # 测试标签列表 - 使用简单的值测试而不是list-item
        # p_tags = self.load_policy({
        #     'name': 'kafka-filter-tags-test',
        #     'resource': 'huaweicloud.kafka',
        #     'filters': [{
        #         'type': 'list-item',
        #         'key': 'tags[0].key',
        #         'value': 'environment'
        #     }]},
        #     session_factory=factory)
        # resources_tags = p_tags.run()
        # self.assertEqual(len(resources_tags), 1)

    def test_kafka_filter_config_compliance(self):
        factory = self.replay_flight_data('kafka_filter_config')
        # 测试配置项等于期望值 (假设 auto.create.topics.enable 为 true)
        p_eq_true = self.load_policy({
            'name': 'kafka-filter-config-eq-true-test',
            'resource': 'huaweicloud.kafka',
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
            'resource': 'huaweicloud.kafka',
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
            'resource': 'huaweicloud.kafka',
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

    def test_kafka_filter_marked_for_op(self):
        # 需要一个带有 'mark-for-op-custodian' 或自定义标签的实例录像带
        factory = self.replay_flight_data('kafka_filter_marked_for_op')
        # 假设实例被标记为 'delete@YYYY/MM/DD HH:MM:SS UTC' 且已到期
        p = self.load_policy({
            'name': 'kafka-filter-marked-delete-test',
            'resource': 'huaweicloud.kafka',
            'filters': [{
                'type': 'marked-for-op',
                'op': 'delete',
                'tag': 'custodian_cleanup'  # 与标记动作的tag一致
                # 'skew': 1 # 可选：测试提前匹配
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)  # 假设有1个匹配实例

        # 边界：测试标签值格式错误 (需要特定录像带)
        # factory_bad_tag = self.replay_flight_data('kafka_filter_marked_bad_tag')
        # p_bad = ...
        # resources_bad = p_bad.run()
        # self.assertEqual(len(resources_bad), 0)

        # 边界：测试操作类型不匹配
        p_wrong_op = self.load_policy({
            'name': 'kafka-filter-marked-wrong-op-test',
            'resource': 'huaweicloud.kafka',
            'filters': [{'type': 'marked-for-op', 'op': 'stop'}]},  # 查找 stop
            session_factory=factory)  # 使用相同的录像带 (假设标记的是 delete)
        resources_wrong_op = p_wrong_op.run()
        self.assertEqual(len(resources_wrong_op), 0)

    # =========================
    # Action Tests
    # =========================
    def test_kafka_action_mark_for_op(self):
        factory = self.replay_flight_data('kafka_action_mark')
        p = self.load_policy({
            'name': 'kafka-action-mark-test',
            'resource': 'huaweicloud.kafka',
            'actions': [{
                'type': 'mark-for-op',
                'op': 'delete',
                'tag': 'custodian_cleanup',
                'days': 7
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)  # 假设对1个实例执行了操作
        # 验证：需要检查 VCR 录像带，确认调用了 batch_create_or_delete_kafka_tag
        # 并且请求体包含了正确的 tag key 和 value (带时间戳)

    def test_kafka_action_auto_tag_user(self):
        # 需要一个资源字典中包含 'creator' 或 'user_name' 的录像带
        factory = self.replay_flight_data('kafka_action_autotag')
        p = self.load_policy({
            'name': 'kafka-action-autotag-test',
            'resource': 'huaweicloud.kafka',
            'filters': [{'tag:CreatorName': 'absent'}],  # 只对没有 CreatorName 标签的实例操作
            'actions': [{
                'type': 'auto-tag-user',
                'tag': 'CreatorName',
                'user_key': 'creator',  # 假设资源中有 'creator' 字段
                'update': False
            }]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)  # 假设对1个实例执行了操作
        # 验证：检查 VCR 录像带，确认调用了 batch_create_or_delete_kafka_tag
        # 并且请求体包含了 'CreatorName' 和从资源中获取的用户名 (或 'unknown')

        # 边界：测试 update=False 且标签已存在 (需要特定录像带)
        # factory_tag_exists = self.replay_flight_data('kafka_action_autotag_exists')
        # p_exists = ... # 设置 update=False
        # resources_exists = p_exists.run()
        # # 验证：检查 VCR 录像带，确认没有调用 batch_create_or_delete_kafka_tag

    def test_kafka_action_tag(self):
        factory = self.replay_flight_data('kafka_action_tag')
        p = self.load_policy({
            'name': 'kafka-action-tag-test',
            'resource': 'huaweicloud.kafka',
            'actions': [{'type': 'tag', 'key': 'CostCenter', 'value': 'Finance'}]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # 验证：检查 VCR，确认调用了 batch_create_or_delete_kafka_tag (action=create)
        # 且 body.tags 包含 {'key': 'CostCenter', 'value': 'Finance'}

    def test_kafka_action_remove_tag(self):
        factory = self.replay_flight_data('kafka_action_remove_tag')
        p = self.load_policy({
            'name': 'kafka-action-remove-tag-test',
            'resource': 'huaweicloud.kafka',
            'filters': [{'tag:environment': 'present'}],  # 确保标签存在才移除
            'actions': [{'type': 'remove-tag', 'keys': ['environment', 'temp-tag']}]},  # 移除多个
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # 验证：检查 VCR，确认调用了 batch_create_or_delete_kafka_tag (action=delete)
        # 且 body.tags 包含 {'key': 'environment'} 和 {'key': 'temp-tag'} (如果都存在)

        # 边界：测试移除不存在的标签 (应跳过或API调用仍成功但无效果)
        # factory_no_tag = self.replay_flight_data('kafka_action_remove_tag_missing')
        # p_no_tag = ... # 移除一个不存在的 key
        # resources_no_tag = p_no_tag.run()
        # # 验证：检查 VCR，确认没有调用 API 或 API 调用但 body.tags 为空或只包含存在的标签

    def test_kafka_action_rename_tag(self):
        factory = self.replay_flight_data('kafka_action_rename_tag')
        p = self.load_policy({
            'name': 'kafka-action-rename-tag-test',
            'resource': 'huaweicloud.kafka',
            'filters': [{'tag:env': 'present'}],  # 确保旧标签存在
            'actions': [{'type': 'rename-tag', 'old_key': 'env', 'new_key': 'Environment'}]},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # 验证：检查 VCR，确认调用了两次 batch_create_or_delete_kafka_tag
        # 第一次：action=create, tag={'key': 'Environment', 'value': 'old_value'}
        # 第二次：action=delete, tag={'key': 'env'}

        # 边界：测试 old_key == new_key (应无操作)
        # factory_same_key = self.replay_flight_data('kafka_action_rename_tag_same')
        # p_same = ... # old_key 和 new_key 相同
        # resources_same = p_same.run()
        # # 验证：检查 VCR，确认没有调用 API

        # 边界：测试 old_key 不存在 (应无操作)
        # factory_old_missing = self.replay_flight_data('kafka_action_rename_tag_old_missing')
        # p_old_missing = ... # old_key 不存在
        # resources_old_missing = p_old_missing.run()
        # # 验证：检查 VCR，确认没有调用 API

    def test_kafka_action_delete(self):
        factory = self.replay_flight_data('kafka_action_delete')
        p = self.load_policy({
            'name': 'kafka-action-delete-test',
            'resource': 'huaweicloud.kafka',
            # 通常会结合 marked-for-op 或 age 过滤器
            'filters': [{'tag:totest': 'delete'}],
            'actions': ['delete']},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # 验证：检查 VCR，确认调用了 delete_instance API

    def test_kafka_action_set_config(self):
        factory = self.replay_flight_data('kafka_action_set_config')
        p = self.load_policy({
            'name': 'kafka-action-set-config-test',
            'resource': 'huaweicloud.kafka',
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
        # 验证：检查 VCR，确认调用了 modify_instance_configs API
        # 且请求体包含正确的 kafka_configs 列表，值应为字符串 ("true", "168")

        # 边界：测试空的 config (应无操作或报错)
        # p_empty_config = ... # config: {}
        # resources_empty = p_empty_config.run()
        # # 验证：检查 VCR，确认没有调用 API
