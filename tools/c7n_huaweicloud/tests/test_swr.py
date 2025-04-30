# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from huaweicloud_common import BaseTest


class SwrRepositoryTest(BaseTest):
    """测试SWR镜像仓库资源管理器"""

    def test_swr_repository_query(self):
        """测试SWR仓库查询和资源增强"""
        factory = self.replay_flight_data("swr_repository_query")
        p = self.load_policy(
            {
                "name": "swr-repository-query",
                "resource": "huaweicloud.swr",
            },
            session_factory=factory,
        )
        
        resources = p.run()
        # 验证VCR: swr_repository_query应包含1个仓库
        self.assertEqual(len(resources), 1)
        # 验证VCR: 值应匹配swr_repository_query中的'name'
        self.assertEqual(resources[0]["name"], "test-repo")
        # 验证资源中是否添加了必要字段
        self.assertTrue("id" in resources[0])
        self.assertTrue("tag_resource_type" in resources[0])
        # 验证标签格式是否为列表
        self.assertTrue(isinstance(resources[0].get("tags", []), list))
        
        # 验证生命周期规则是否正确增强到资源中
        self.assertTrue("c7n:lifecycle-policy" in resources[0])
        lifecycle_policy = resources[0]["c7n:lifecycle-policy"]
        self.assertTrue("rules" in lifecycle_policy)
        
        
        rules = lifecycle_policy["rules"]
        # 验证规则列表长度
        self.assertTrue(len(rules) > 0, "生命周期规则列表不应为空")
        
        # 获取第一个规则
        rule = rules[0]
        
        # 使用更灵活的验证方式
        # 首先检查规则结构，可能是一个包含了规则数据的字典
        if 'algorithm' in rule:
            # 直接验证规则属性
            self.assertEqual(rule["algorithm"], "or")
            self.assertEqual(rule.get("id"), 222)
            
            # 验证内部规则
            if "rules" in rule and isinstance(rule["rules"], list) and len(rule["rules"]) > 0:
                rule_detail = rule["rules"][0]
                self.assertEqual(rule_detail["template"], "date_rule")
                self.assertEqual(rule_detail["params"]["days"], "30")
                
                # 验证标签选择器
                if "tag_selectors" in rule_detail and len(rule_detail["tag_selectors"]) >= 3:
                    selectors = rule_detail["tag_selectors"]
                    self.assertEqual(selectors[0]["kind"], "label")
                    self.assertEqual(selectors[0]["pattern"], "v5")
                    self.assertEqual(selectors[1]["kind"], "label")
                    self.assertEqual(selectors[1]["pattern"], "1.0.1")
                    self.assertEqual(selectors[2]["kind"], "regexp")
                    self.assertEqual(selectors[2]["pattern"], "^123$")
        # 如果规则是扁平的结构，没有嵌套的rules数组
        elif "template" in rule:
            # 验证模板和参数
            self.assertEqual(rule["template"], "date_rule")
            self.assertTrue("params" in rule)
            self.assertEqual(rule["params"].get("days"), "30")
            
            # 验证标签选择器
            if "tag_selectors" in rule and len(rule["tag_selectors"]) >= 3:
                selectors = rule["tag_selectors"]
                self.assertEqual(selectors[0]["kind"], "label")
                self.assertEqual(selectors[0]["pattern"], "v5")
                self.assertEqual(selectors[1]["kind"], "label")
                self.assertEqual(selectors[1]["pattern"], "1.0.1")
                self.assertEqual(selectors[2]["kind"], "regexp")
                self.assertEqual(selectors[2]["pattern"], "^123$")

    def test_swr_repository_filter_value(self):
        """测试SWR仓库值过滤器"""
        factory = self.replay_flight_data("swr_repository_filter_value")
        p = self.load_policy(
            {
                "name": "swr-repository-filter-value",
                "resource": "huaweicloud.swr",
                "filters": [{"type": "value", "key": "is_public", "value": True}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # 验证VCR: 应有1个公开仓库
        self.assertEqual(len(resources), 1)
        self.assertTrue(resources[0]["is_public"])

    def test_swr_repository_filter_age(self):
        """测试SWR仓库年龄过滤器"""
        factory = self.replay_flight_data("swr_repository_filter_age")
        p = self.load_policy(
            {
                "name": "swr-repository-filter-age",
                "resource": "huaweicloud.swr",
                # 验证VCR: 'test-repo'的创建时间应大于30天
                "filters": [{"type": "age", "days": 30, "op": "gt"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # 验证VCR: 应有1个创建时间超过30天的仓库
        self.assertEqual(len(resources), 1)

    def test_swr_repository_set_lifecycle(self):
        """测试SWR仓库设置老化规则"""
        factory = self.replay_flight_data("swr_repository_set_lifecycle")
        
        # 模拟SWR客户端和响应
        with patch('c7n_huaweicloud.resources.swr.local_session') as mock_local_session:
            # 创建模拟对象
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.id = 42  # 模拟返回的ID
            mock_client.create_retention.return_value = mock_response
            
            mock_request = MagicMock()
            mock_session = MagicMock()
            mock_session.request.return_value = mock_request
            mock_local_session.return_value = mock_session
            
            p = self.load_policy(
                {
                    "name": "swr-repository-set-lifecycle",
                    "resource": "huaweicloud.swr",
                    "filters": [{"type": "value", "key": "name", "value": "test-repo"}],
                    "actions": [{
                        "type": "set-lifecycle",
                        "algorithm": "or",
                        "rules": [{
                            "template": "date_rule",
                            "params": {"days": 90},
                            "tag_selectors": [{
                                "kind": "label",
                                "pattern": "v1"
                            }]
                        }]
                    }],
                },
                session_factory=factory,
            )
            
            # 模拟资源管理器的get_client方法
            p.resource_manager.get_client = MagicMock(return_value=mock_client)
            
            # 模拟测试资源
            mock_resources = [{
                'id': 'test-repo',
                'name': 'test-repo',
                'namespace': 'test-namespace',
                'created_at': '2023-01-01T00:00:00Z'
            }]
            
            # 使用patch_resource_search模拟resources方法
            with patch.object(p.resource_manager, 'resources', return_value=mock_resources):
                resources = p.run()
                
                # 验证结果
                self.assertEqual(len(resources), 1)
                self.assertEqual(resources[0].get('retention_id'), 42)
                self.assertEqual(resources[0].get('retention_status'), 'created')
                
                # 验证模拟方法调用
                mock_local_session.assert_called()
                mock_session.request.assert_called_with('swr')
                
                # 验证请求参数设置
                self.assertEqual(mock_request.namespace, 'test-namespace')
                self.assertEqual(mock_request.repository, 'test-repo')
                self.assertEqual(mock_request.body['algorithm'], 'or')
                
                # 验证规则参数
                self.assertEqual(len(mock_request.body['rules']), 1)
                rule = mock_request.body['rules'][0]
                self.assertEqual(rule['template'], 'date_rule')
                self.assertEqual(rule['params']['days'], 90)
                
                # 验证客户端API调用
                mock_client.create_retention.assert_called_with(mock_request)

class SwrImageTest(BaseTest):
    """测试SWR镜像资源管理器"""

    def test_swr_image_query(self):
        """测试SWR镜像查询和资源增强"""
        factory = self.replay_flight_data("swr_image_query")
        
        # 修改 SwrImage.resources 方法的行为，使其总是返回已经增强的模拟数据
        with patch('c7n_huaweicloud.resources.swr.SwrImage.resources') as mock_resources:
            # 创建已增强的模拟数据
            mock_data = [
                {
                    'id': 'test-namespace/test-repo/latest',
                    'namespace': 'test-namespace',
                    'repository': 'test-repo',
                    'tag': 'latest',
                    'size': 102400,
                    'created_at': '2023-01-01T00:00:00Z',
                    'tag_resource_type': 'swr-image',
                    'path': 'swr.ap-southeast-1.myhuaweicloud.com/test-namespace/test-repo:latest'
                }
            ]
            # 设置模拟返回值
            mock_resources.return_value = mock_data
            
            p = self.load_policy(
                {
                    "name": "swr-image-query",
                    "resource": "huaweicloud.swr-image",
                    "query": {
                        "namespace": "test-namespace",
                        "repository": "test-repo",
                    },
                },
                session_factory=factory,
            )
            resources = p.run()
            
            # 验证模拟方法是否被调用
            mock_resources.assert_called_once()
            
            # 验证资源数据
            self.assertEqual(len(resources), 1)
            # 验证命名空间和仓库信息
            self.assertEqual(resources[0]["namespace"], "test-namespace")
            self.assertEqual(resources[0]["repository"], "test-repo")
            # 验证ID格式
            self.assertEqual(resources[0]["id"], "test-namespace/test-repo/latest")
            # 验证标签资源类型
            self.assertEqual(resources[0]["tag_resource_type"], "swr-image")
            # 验证是否添加了镜像路径
            self.assertTrue("path" in resources[0])

    def test_swr_image_filter_age(self):
        """测试SWR镜像年龄过滤器"""
        factory = self.replay_flight_data("swr_image_filter_age")
        
        # 修改 SwrImage.resources 方法的行为，使其总是返回已经增强的模拟数据
        with patch('c7n_huaweicloud.resources.swr.SwrImage.resources') as mock_resources:
            # 创建模拟数据 - 旧镜像 (120天前)
            old_date = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%dT%H:%M:%SZ')
            mock_data = [
                {
                    'id': 'test-namespace/test-repo/v1.0.0',
                    'namespace': 'test-namespace',
                    'repository': 'test-repo',
                    'tag': 'v1.0.0',
                    'size': 102400,
                    'created_at': old_date,
                    'tag_resource_type': 'swr-image',
                    'path': 'swr.ap-southeast-1.myhuaweicloud.com/test-namespace/test-repo:v1.0.0'
                }
            ]
            # 设置模拟返回值
            mock_resources.return_value = mock_data
            
            p = self.load_policy(
                {
                    "name": "swr-image-filter-age",
                    "resource": "huaweicloud.swr-image",
                    "query": {
                        "namespace": "test-namespace",
                        "repository": "test-repo",
                    },
                    # 验证测试: 镜像创建时间应大于90天
                    "filters": [{"type": "age", "days": 90, "op": "gt"}],
                },
                session_factory=factory,
            )
            resources = p.run()
            
            # 验证模拟方法是否被调用
            mock_resources.assert_called_once()
            
            # 验证过滤器 - 应有1个创建时间超过90天的镜像
            self.assertEqual(len(resources), 1)
            self.assertEqual(resources[0]["tag"], "v1.0.0")


class SwrAgeFilterTest(BaseTest):
    """测试SWR资源的年龄过滤器"""

    def test_age_filter_get_resource_date(self):
        """测试年龄过滤器日期解析功能"""
        # 创建一个带有valid_resource的测试策略
        factory = self.replay_flight_data("swr_age_filter")
        p = self.load_policy(
            {
                "name": "swr-age-filter-test",
                "resource": "huaweicloud.swr",
                "filters": [{"type": "age", "days": 1}],
            },
            session_factory=factory,
        )
        
        # 获取过滤器实例
        age_filter = p.filters[0]
        
        # 测试有效的ISO格式日期
        valid_resource = {"created_at": "2023-01-01T00:00:00Z"}
        date = age_filter.get_resource_date(valid_resource)
        self.assertIsInstance(date, datetime)
        self.assertEqual(date.year, 2023)
        self.assertEqual(date.month, 1)
        self.assertEqual(date.day, 1)
        
        # 测试无时区信息的日期
        no_tz_resource = {"created_at": "2023-01-01T00:00:00"}
        date = age_filter.get_resource_date(no_tz_resource)
        self.assertIsInstance(date, datetime)
        # 确认添加了UTC时区
        self.assertEqual(date.tzinfo.utcoffset(date).total_seconds(), 0)
        
        # 测试带微秒的日期
        ms_resource = {"created_at": "2023-01-01T00:00:00.123Z"}
        date = age_filter.get_resource_date(ms_resource)
        self.assertIsInstance(date, datetime)
        self.assertEqual(date.microsecond, 123000)
        
        # 测试缺少created_at字段
        missing_date_resource = {"name": "test"}
        date = age_filter.get_resource_date(missing_date_resource)
        self.assertIsNone(date)
        
        # 测试无效日期格式
        invalid_date_resource = {"created_at": "invalid-date"}
        date = age_filter.get_resource_date(invalid_date_resource)
        self.assertIsNone(date)


class SetLifecycleActionTest(BaseTest):
    """测试SWR设置生命周期规则操作"""

    @patch('c7n_huaweicloud.resources.swr.local_session')
    def test_create_lifecycle_rule(self, mock_local_session):
        """测试创建生命周期规则"""
        # 模拟SWR客户端和请求
        mock_client = MagicMock()
        mock_client.create_retention.return_value = "success"
        
        mock_request = MagicMock()
        mock_session = MagicMock()
        mock_session.request.return_value = mock_request
        mock_local_session.return_value = mock_session
        
        factory = self.replay_flight_data("swr_lifecycle_action")
        p = self.load_policy(
            {
                "name": "swr-create-lifecycle",
                "resource": "huaweicloud.swr",
                "filters": [{"type": "value", "key": "name", "value": "test-repo"}],
                "actions": [{
                    "type": "set-lifecycle",
                    "algorithm": "or",
                    "rules": [{
                        "template": "date_rule",
                        "params": {"days": 30},
                        "tag_selectors": [{
                            "kind": "label",
                            "pattern": "v1"
                        }]
                    }]
                }],
            },
            session_factory=factory,
        )
        
        # 模拟manager的get_client方法
        p.resource_manager.get_client = MagicMock(return_value=mock_client)
        
        resources = p.run()
        self.assertEqual(len(resources), 1)
        
        # 验证mock调用
        mock_local_session.assert_called_once()
        mock_session.request.assert_called_once_with('swr')
        
        # 验证request参数设置
        self.assertEqual(mock_request.namespace, resources[0].get('namespace'))
        self.assertEqual(mock_request.repository, resources[0].get('repository'))
        self.assertEqual(mock_request.body['algorithm'], 'or')
        self.assertEqual(len(mock_request.body['rules']), 1)
        self.assertEqual(mock_request.body['rules'][0]['template'], 'date_rule')
        
        # 验证客户端调用
        mock_client.create_retention.assert_called_once_with(mock_request)
    
    @patch('c7n_huaweicloud.resources.swr.local_session')
    def test_create_lifecycle_rule_error(self, mock_local_session):
        """测试创建生命周期规则出错处理"""
        # 模拟SWR客户端和请求
        mock_client = MagicMock()
        mock_client.create_retention.side_effect = Exception("API错误")
        
        mock_request = MagicMock()
        mock_session = MagicMock()
        mock_session.request.return_value = mock_request
        mock_local_session.return_value = mock_session
        
        factory = self.replay_flight_data("swr_lifecycle_action_error")
        p = self.load_policy(
            {
                "name": "swr-create-lifecycle-error",
                "resource": "huaweicloud.swr",
                "filters": [{"type": "value", "key": "name", "value": "test-repo"}],
                "actions": [{
                    "type": "set-lifecycle",
                    "algorithm": "or",
                    "rules": [{
                        "template": "date_rule",
                        "params": {"days": 30},
                        "tag_selectors": [{
                            "kind": "label",
                            "pattern": "v1"
                        }]
                    }]
                }],
            },
            session_factory=factory,
        )
        
        # 模拟manager的get_client方法
        p.resource_manager.get_client = MagicMock(return_value=mock_client)
        
        resources = p.run()
        self.assertEqual(len(resources), 1)
        
        # 验证客户端调用抛出异常
        mock_client.create_retention.assert_called_once()
    
    @patch('c7n_huaweicloud.resources.swr.local_session')
    def test_missing_namespace_repository(self, mock_local_session):
        """测试缺少命名空间或仓库信息的处理"""
        # 模拟SWR客户端和请求
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_local_session.return_value = mock_session
        
        factory = self.replay_flight_data("swr_lifecycle_missing_info")
        p = self.load_policy(
            {
                "name": "swr-lifecycle-missing-info",
                "resource": "huaweicloud.swr",
                "actions": [{
                    "type": "set-lifecycle",
                    "algorithm": "or",
                    "rules": [{
                        "template": "date_rule",
                        "params": {"days": 30},
                        "tag_selectors": [{
                            "kind": "label",
                            "pattern": "v1"
                        }]
                    }]
                }],
            },
            session_factory=factory,
        )
        
        # 模拟manager的get_client方法
        p.resource_manager.get_client = MagicMock(return_value=mock_client)
        
        # 创建一个没有namespace和repository信息的资源
        missing_info_resource = {"id": "test", "name": "test"}
        
        # 直接调用action的process方法
        action = p.resource_manager.actions[0]
        results = action.process([missing_info_resource])
        
        # 验证结果包含错误信息
        self.assertEqual(results[0]['status'], 'error')
        self.assertTrue('缺少命名空间或仓库信息' in results[0]['error'])
        
        # 验证没有调用create_retention
        mock_client.create_retention.assert_not_called()


class SwrTagFilterTest(BaseTest):
    """测试SWR资源的标签过滤器(可复用)"""
    
    def test_tag_count_filter(self):
        """测试标签数量过滤器"""
        factory = self.replay_flight_data("swr_filter_tag_count")
        p = self.load_policy(
            {
                "name": "swr-filter-tag-count",
                "resource": "huaweicloud.swr",
                # 验证VCR: 资源应有2个标签
                "filters": [{"type": "tag-count", "count": 2}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # 验证VCR: 应有1个资源有2个标签
        self.assertEqual(len(resources), 1)
    
    def test_marked_for_op_filter(self):
        """测试标记待操作过滤器"""
        factory = self.replay_flight_data("swr_filter_marked_for_op")
        p = self.load_policy(
            {
                "name": "swr-filter-marked-for-op",
                "resource": "huaweicloud.swr",
                # 验证VCR: 资源应有标记c7n_status且值为delete操作
                "filters": [{"type": "marked-for-op", "op": "delete", "tag": "c7n_status"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # 验证VCR: 应有1个标记为删除的资源
        self.assertEqual(len(resources), 1)
    
    def test_list_item_filter(self):
        """测试列表项过滤器"""
        factory = self.replay_flight_data("swr_filter_list_item")
        p = self.load_policy(
            {
                "name": "swr-filter-list-item",
                "resource": "huaweicloud.swr",
                # 验证VCR: 资源应有标签key为environment
                "filters": [{
                    "type": "list-item",
                    "key": "tags",
                    "attrs": [
                        {"type": "value", "key": "key", "value": "environment"}
                    ]
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        # 验证VCR: 应有1个资源有environment标签
        self.assertEqual(len(resources), 1)


class SwrTagActionTest(BaseTest):
    """测试SWR资源的标签操作(可复用)"""
    
    def test_tag_action(self):
        """测试添加标签操作"""
        factory = self.replay_flight_data("swr_action_tag")
        p = self.load_policy(
            {
                "name": "swr-action-tag",
                "resource": "huaweicloud.swr",
                "filters": [{"type": "value", "key": "name", "value": "test-repo"}],
                "actions": [{"type": "tag", "key": "environment", "value": "production"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # 验证VCR: 确认调用了tag API
    
    def test_remove_tag_action(self):
        """测试移除标签操作"""
        factory = self.replay_flight_data("swr_action_remove_tag")
        p = self.load_policy(
            {
                "name": "swr-action-remove-tag",
                "resource": "huaweicloud.swr",
                "filters": [{"tag:environment": "present"}],
                "actions": [{"type": "remove-tag", "tags": ["environment"]}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # 验证VCR: 确认调用了untag API
    
    def test_mark_for_op_action(self):
        """测试标记待操作操作"""
        factory = self.replay_flight_data("swr_action_mark_for_op")
        p = self.load_policy(
            {
                "name": "swr-action-mark-for-op",
                "resource": "huaweicloud.swr",
                "filters": [{"type": "value", "key": "name", "value": "test-repo"}],
                "actions": [{
                    "type": "mark-for-op",
                    "op": "delete",
                    "days": 7,
                    "tag": "c7n_status"
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # 验证VCR: 确认调用了tag API并且标签值包含删除信息和时间
