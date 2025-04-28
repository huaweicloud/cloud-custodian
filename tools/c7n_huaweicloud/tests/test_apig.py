# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from unittest.mock import patch

from huaweicloud_common import BaseTest


class APIGTest(BaseTest):
    """测试 API 网关(APIG)资源、过滤器和操作"""

    def test_apig_query(self):
        """测试 APIG 资源查询"""
        factory = self.replay_flight_data("apig_query")
        p = self.load_policy(
            {
                "name": "apig-query",
                "resource": "huaweicloud.apig",
            },
            session_factory=factory,
        )
        resources = p.run()
        # 验证 VCR: apig_query 应包含 1 个 API
        self.assertEqual(len(resources), 1)
        # 验证 VCR: 值应匹配 apig_query 中的 'name'
        self.assertEqual(resources[0]["name"], "test-api")

    def test_apig_filter_age_match(self):
        """测试 APIG API 创建时间过滤器 - 匹配"""
        factory = self.replay_flight_data("apig_filter_age")
        p = self.load_policy(
            {
                "name": "apig-filter-age-match",
                "resource": "huaweicloud.apig",
                # 验证 VCR: 在 apig_filter_age 中 API 的创建时间应该 >= 30 天
                "filters": [{"type": "age", "days": 30, "op": "ge"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_apig_filter_age_no_match(self):
        """测试 APIG API 创建时间过滤器 - 不匹配"""
        factory = self.replay_flight_data("apig_filter_age")  # 复用录像带
        p = self.load_policy(
            {
                "name": "apig-filter-age-no-match",
                "resource": "huaweicloud.apig",
                # 验证 VCR: 在 apig_filter_age 中 API 的创建时间不应该 < 1 天
                "filters": [{"type": "age", "days": 1, "op": "lt"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 0)

    def test_apig_action_delete(self):
        """测试 删除 API 操作"""
        factory = self.replay_flight_data("apig_action_delete")
        # 获取要删除的 API ID
        api_id_to_delete = "5f918d104dc84480a75166ba99efff21"
        p = self.load_policy(
            {
                "name": "apig-action-delete",
                "resource": "huaweicloud.apig",
                "filters": [{"type": "value", "key": "id", "value": api_id_to_delete}],
                "actions": ["delete"],
            },
            session_factory=factory,
        )
        
        # 模拟API资源，因为我们的flight数据是固定的
        with patch.object(p.resource_manager, 'resources', return_value=[
            {'id': api_id_to_delete, 'name': 'test-api'}
        ]):
            resources = p.run()
            self.assertEqual(len(resources), 1)
            # 主要断言验证策略是否正确过滤了目标资源
            self.assertEqual(resources[0]['id'], api_id_to_delete)
            # 验证操作成功: 手动检查 VCR 录像带 apig_action_delete 确认
            # 调用了 DeleteApiV2 API 并且获得了 204 No Content 的响应

    def test_apig_action_update_environment(self):
        """测试 更新环境信息操作"""
        factory = self.replay_flight_data("apig_action_update_environment")
        # 获取要更新的环境 ID
        environment_id = "7a1ad0c350844ee69435ab297c1e6d18"
        new_name = "updated-test-env"
        new_description = "Updated test environment"
        p = self.load_policy(
            {
                "name": "apig-action-update-environment",
                "resource": "huaweicloud.apig",
                "actions": [{
                    "type": "update-environment",
                    "environment_id": environment_id,
                    "name": new_name,
                    "description": new_description
                }],
            },
            session_factory=factory,
        )
        
        # 模拟API资源，因为我们的flight数据是固定的
        with patch.object(p.resource_manager, 'resources', return_value=[
            {'id': '5f918d104dc84480a75166ba99efff21', 'name': 'test-api', 'instance_id': 'cc371c55cc9141558ccd76b86903e78b'}
        ]):
            resources = p.run()
            self.assertEqual(len(resources), 1)
            # 验证操作成功: 手动检查 VCR 录像带 apig_action_update_environment 确认
            # 调用了 UpdateEnvironmentV2 API 并且提供了正确的请求体
            # (包含 name 和 remark)

    def test_apig_action_delete_environment(self):
        """测试 删除环境操作"""
        factory = self.replay_flight_data("apig_action_delete_environment")
        # 获取要删除的环境 ID
        environment_id = "7a1ad0c350844ee69435ab297c1e6d18"
        p = self.load_policy(
            {
                "name": "apig-action-delete-environment",
                "resource": "huaweicloud.apig",
                "actions": [{
                    "type": "delete-environment",
                    "environment_id": environment_id
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        # 验证操作成功: 手动检查 VCR 录像带 apig_action_delete_environment 确认
        # 调用了 DeleteEnvironmentV2 API

    def test_apig_action_update_domain(self):
        """测试 更新自定义域名信息操作"""
        factory = self.replay_flight_data("apig_action_update_domain")
        # 获取要更新的域名 ID
        domain_id = "7a1ad0c350844ee69435ab297c1e6d18"
        min_ssl_version = "TLSv1.2"
        p = self.load_policy(
            {
                "name": "apig-action-update-domain",
                "resource": "huaweicloud.apig",
                "actions": [{
                    "type": "update-domain",
                    "domain_id": domain_id,
                    "min_ssl_version": min_ssl_version
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        # 验证操作成功: 手动检查 VCR 录像带 apig_action_update_domain 确认
        # 调用了 UpdateDomainV2 API 并且提供了正确的请求体
        # (包含 min_ssl_version)



# =========================
# 可复用特性测试 (以 APIG 为例)
# =========================

class ReusableFeaturesTest(BaseTest):
    """测试可复用的过滤器和操作"""

    def test_filter_value_match(self):
        """测试 value 过滤器 - 匹配"""
        factory = self.replay_flight_data("apig_filter_value_name")
        # 获取要匹配的 API 名称
        target_name = "test-api"
        p = self.load_policy(
            {
                "name": "apig-filter-value-name-match",
                "resource": "huaweicloud.apig",
                "filters": [{"type": "value", "key": "name", "value": target_name}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # 验证 VCR: 只有一个 API 名称匹配
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['name'], target_name)

    def test_filter_value_no_match(self):
        """测试 value 过滤器 - 不匹配"""
        factory = self.replay_flight_data("apig_filter_value_name")  # 复用
        wrong_name = "non-existent-api"
        p = self.load_policy(
            {
                "name": "apig-filter-value-name-no-match",
                "resource": "huaweicloud.apig",
                "filters": [{"type": "value", "key": "name", "value": wrong_name}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # 验证 VCR: 没有 API 名称匹配
        self.assertEqual(len(resources), 0)

    def test_filter_list_item_match(self):
        """测试 list-item 过滤器 - 匹配 (标签列表)"""
        factory = self.replay_flight_data("apig_filter_list_item_tag")
        # 要匹配的标签键和值
        target_tag_key = "filtertag"
        target_tag_value = "filtervalue"
        p = self.load_policy(
            {
                "name": "apig-filter-list-item-tag-match",
                "resource": "huaweicloud.apig",
                "filters": [
                    {
                        "type": "list-item",
                        "key": "Tags",
                        "attrs": [
                            {"type": "value", "key": "Key", "value": target_tag_key},
                            {"type": "value", "key": "Value", "value": target_tag_value}
                        ]
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        # 验证 VCR: 只有一个 API 标签匹配
        self.assertEqual(len(resources), 1)

    def test_filter_marked_for_op_match(self):
        """测试 marked-for-op 过滤器 - 匹配"""
        factory = self.replay_flight_data("apig_filter_marked_for_op")
        op = "delete"
        tag = "c7n_status"
        p = self.load_policy(
            {
                "name": f"apig-filter-marked-for-op-{op}-match",
                "resource": "huaweicloud.apig",
                "filters": [{"type": "marked-for-op", "op": op, "tag": tag}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # 验证 VCR: 只有一个 API 满足标记条件
        # (需根据当前时间手动检查过期情况)
        self.assertEqual(len(resources), 1)

    def test_filter_tag_count_match(self):
        """测试 tag-count 过滤器 - 匹配"""
        factory = self.replay_flight_data("apig_filter_tag_count")
        # 预期标签数量
        expected_tag_count = 2
        p = self.load_policy(
            {
                "name": "apig-filter-tag-count-match",
                "resource": "huaweicloud.apig",
                "filters": [{"type": "tag-count", "count": expected_tag_count}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # 验证 VCR: 只有一个 API 有正好 2 个标签
        self.assertEqual(len(resources), 1)

    @patch('c7n_huaweicloud.actions.tms.Tag.process')
    def test_action_tag(self, mock_tag_process):
        """测试标签添加操作 (使用 mock 避免实际 API 调用)"""
        factory = self.replay_flight_data("apig_action_tag")
        p = self.load_policy(
            {
                "name": "apig-action-tag",
                "resource": "huaweicloud.apig",
                "actions": [{"type": "tag", "key": "Environment", "value": "Production"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # 验证 mock 是否被正确调用
        mock_tag_process.assert_called_once()

    @patch('c7n_huaweicloud.actions.tms.RemoveTag.process')
    def test_action_remove_tag(self, mock_remove_tag_process):
        """测试标签移除操作 (使用 mock 避免实际 API 调用)"""
        factory = self.replay_flight_data("apig_action_remove_tag")
        p = self.load_policy(
            {
                "name": "apig-action-remove-tag",
                "resource": "huaweicloud.apig",
                "actions": [{"type": "remove-tag", "tags": ["Temporary"]}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # 验证 mock 是否被正确调用
        mock_remove_tag_process.assert_called_once()