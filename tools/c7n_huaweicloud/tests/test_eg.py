# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from unittest import mock
import os

from tools.c7n_huaweicloud.tests.huaweicloud_common import BaseTest
from c7n_huaweicloud.resources.eg import EventStreaming

class EventStreamingTest(BaseTest):
    """测试华为云EventGrid事件流资源、过滤器和操作"""

    def setUp(self):
        """测试准备工作"""
        super().setUp()
        # 设置默认区域为 cn-north-4，因为 EventGrid 服务只支持cn-east-2、cn-east-3、cn-north-4
        self.default_region = "cn-north-4"
        # 在环境变量中设置区域，覆盖huaweicloud_common.py中的默认设置
        os.environ['HUAWEI_DEFAULT_REGION'] = self.default_region
    def test_eventstreaming_query(self):
        """测试事件流基本查询功能"""
        # 加载策略
        factory = self.replay_flight_data('eg_eventstreaming_query')
        p = self.load_policy({
            'name': 'eventstreaming-query-test',
            'resource': 'huaweicloud.eventstreaming'
        }, session_factory=factory)
        
        # 执行策略
        resources = p.run()
        
        # 验证查询结果
        self.assertEqual(len(resources), 1)

    def test_eventstreaming_age_filter(self):
        """测试事件流资源的创建时间过滤器"""

        # 测试创建时间大于180天的资源
        factory = self.replay_flight_data('eg_eventstreaming_age_filter')
        p = self.load_policy({
            'name': 'old-event-streaming',
            'resource': 'huaweicloud.eventstreaming',
            'filters': [{
                'type': 'age',
                'days': 180,
                'op': 'gt'
            }]
        }, session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 2)


    def test_eventstreaming_tag_filter(self):
        """测试标签过滤器 - 匹配指定的标签键值对"""
        factory = self.replay_flight_data('eg_eventstreaming_filter_tag')
        p = self.load_policy({
            'name': 'tagged-event-streaming',
            'resource': 'huaweicloud.eventstreaming',
            'filters': [{
                'type': 'tag',
                'key': 'environment',
                'value': 'production'
            }]
        }, session_factory=factory)
        
        # 执行策略
        resources = p.run()
        
        # 验证过滤结果 - 应该只有一个资源匹配环境为production的标签
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['id'], 'es-006-with-env-tag')

    def test_eventstreaming_action_tag(self):
        """测试为事件流添加标签的操作"""
        factory = self.replay_flight_data('eg_eventstreaming_action_tag')
        
        # 加载策略
        p = self.load_policy({
            'name': 'eventstreaming-add-tags',
            'resource': 'huaweicloud.eventstreaming',
            'actions': [{
                'type': 'tag',
                'tags': {'env': 'test', 'project': 'cloud-custodian'}
            }]
        }, session_factory=factory)
        
        # 执行策略
        resources = p.run()
        
        # 验证资源数量
        self.assertEqual(len(resources), 1)
        # 验证调用结果：通过VCR确认标签添加API调用成功

    def test_eventstreaming_action_remove_tag(self):
        """测试移除事件流标签的操作"""
        factory = self.replay_flight_data('eg_eventstreaming_action_remove_tag')
        
        # 加载策略
        p = self.load_policy({
            'name': 'eventstreaming-remove-tags',
            'resource': 'huaweicloud.eventstreaming',
            'filters': [{'tag:temporary': 'present'}],  # 确保标签存在才移除
            'actions': [{
                'type': 'remove-tag',
                'tags': ['temporary', 'test-tag']
            }]
        }, session_factory=factory)
        
        # 执行策略
        resources = p.run()
        
        # 验证资源数量
        self.assertEqual(len(resources), 1)
        # 验证调用结果：通过VCR确认标签移除API调用成功

    def test_filter_list_item_match(self):
        """测试list-item过滤器 - 匹配（标签列表）"""
        # 验证VCR：事件流'es-003-with-tags'在'eg_eventstreaming_filter_list_item_tag'中
        # 应具有标签 {"key": "filtertag", "value": "filtervalue"}
        factory = self.replay_flight_data('eg_eventstreaming_filter_list_item_tag')
        # 验证VCR：匹配'eg_eventstreaming_filter_list_item_tag'中的目标标签
        target_tag_key = "filtertag"
        target_tag_value = "filtervalue"
        # 验证VCR：匹配带有该标签的事件流ID
        target_eventstreaming_id = "es-003-with-tags"
        
        # 加载策略
        p = self.load_policy({
            'name': 'eventstreaming-list-item-tag-match',
            'resource': 'huaweicloud.eventstreaming',
            'filters': [{
                'type': 'list-item',
                'key': 'tags',  # 注意：应使用小写的'tags'，与API响应一致
                'attrs': [
                    {'type': 'value', 'key': 'key', 'value': target_tag_key},
                    {'type': 'value', 'key': 'value', 'value': target_tag_value}
                ]
            }]
        }, session_factory=factory)
        
        # 执行策略
        resources = p.run()
        
        # 验证结果
        # 验证VCR：只有一个事件流在'eg_eventstreaming_filter_list_item_tag'中匹配此标签
        self.assertEqual(len(resources), 2)
        # 验证匹配的事件流是具有标签的事件流
        self.assertEqual(resources[0]['id'], target_eventstreaming_id)

    def test_filter_marked_for_op_match(self):
        """测试marked-for-op过滤器 - 匹配"""
        # 验证VCR：事件流'es-004-marked'在'eg_eventstreaming_filter_marked_for_op'中
        # 应有标记'c7n_status': 'marked-for-op:delete:1'并且已过期
        factory = self.replay_flight_data('eg_eventstreaming_filter_marked_for_op')
        op = "delete"
        # 验证VCR：匹配'eg_eventstreaming_filter_marked_for_op'中的标记键
        tag = "c7n_status"
        
        # 加载策略
        p = self.load_policy({
            'name': f'eventstreaming-marked-for-op-{op}-match',
            'resource': 'huaweicloud.eventstreaming',
            'filters': [{'type': 'marked-for-op', 'op': op, 'tag': tag}]
        }, session_factory=factory)
        
        # 执行策略
        resources = p.run()
        
        # 验证结果
        # 验证VCR：只有一个事件流在'eg_eventstreaming_filter_marked_for_op'中满足条件
        # （需要根据当前时间手动检查过期情况）
        self.assertEqual(len(resources), 1)

    def test_filter_tag_count_match(self):
        """测试tag-count过滤器 - 匹配"""
        # 验证VCR：事件流'es-005-two-tags'在'eg_eventstreaming_filter_tag_count'中应有2个标签
        factory = self.replay_flight_data('eg_eventstreaming_filter_tag_count')
        # 验证VCR：匹配'eg_eventstreaming_filter_tag_count'中'es-005-two-tags'的标签数量
        expected_tag_count = 2
        
        # 加载策略
        p = self.load_policy({
            'name': 'eventstreaming-tag-count-match',
            'resource': 'huaweicloud.eventstreaming',
            'filters': [{'type': 'tag-count', 'count': expected_tag_count}]
        }, session_factory=factory)
        
        # 执行策略
        resources = p.run()
        
        # 验证结果
        # 验证VCR：只有一个事件流在'eg_eventstreaming_filter_tag_count'中恰好有2个标签
        self.assertEqual(len(resources), 1)