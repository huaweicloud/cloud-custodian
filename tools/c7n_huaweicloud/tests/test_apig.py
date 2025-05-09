# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from huaweicloud_common import BaseTest


class ApiResourceTest(BaseTest):
    """测试API网关API资源，过滤器和操作"""

    def test_api_query(self):
        """测试API资源查询和增强"""
        factory = self.replay_flight_data("apig_api_query")
        p = self.load_policy(
            {
                "name": "apig-api-query",
                "resource": "huaweicloud.rest-api",
            },
            session_factory=factory,
        )
        resources = p.run()
        # 验证VCR: apig_api_query应包含1个API
        self.assertEqual(len(resources), 1)
        # 验证VCR: 值应与apig_api_query中的'name'匹配
        self.assertEqual(resources[0]["name"], "test-api")
        # 验证VCR: 值应与apig_api_query中的'req_method'匹配
        self.assertEqual(resources[0]["req_method"], "GET")
        self.assertTrue("backend_type" in resources[0])  # 验证增强添加了信息

    def test_api_filter_age_match(self):
        """测试API年龄过滤器 - 匹配"""
        factory = self.replay_flight_data("apig_api_filter_age")
        p = self.load_policy(
            {
                "name": "apig-api-filter-age-match",
                "resource": "huaweicloud.rest-api",
                # 验证VCR: 'test-old-api'的创建时间在apig_api_filter_age中
                # 应该 >= 90天
                "filters": [{"type": "age", "days": 90, "op": "ge"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_api_filter_age_no_match(self):
        """测试API年龄过滤器 - 不匹配"""
        factory = self.replay_flight_data("apig_api_filter_age")  # 重用cassette
        p = self.load_policy(
            {
                "name": "apig-api-filter-age-no-match",
                "resource": "huaweicloud.rest-api",
                # 验证VCR: 'test-old-api'的创建时间在apig_api_filter_age中
                # 不应该 < 1天
                "filters": [{"type": "age", "days": 1, "op": "lt"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 0)

    def test_api_action_delete(self):
        """测试删除API操作"""
        factory = self.replay_flight_data("apig_api_action_delete")
        # 从apig_api_action_delete获取要删除的API ID和名称
        # 验证VCR: 匹配apig_api_action_delete中的'id'
        api_id_to_delete = "2c9eb1538a138432018a13uuuuu00001"
        # 验证VCR: 匹配apig_api_action_delete中的'name'
        api_name_to_delete = "api-to-delete"
        p = self.load_policy(
            {
                "name": "apig-api-action-delete",
                "resource": "huaweicloud.rest-api",
                # 使用值过滤器以提高清晰度
                "filters": [{"type": "value", "key": "id", "value": api_id_to_delete}],
                "actions": ["delete"],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # 断言主要验证策略是否正确过滤目标资源
        self.assertEqual(resources[0]['id'], api_id_to_delete)
        self.assertEqual(resources[0]['name'], api_name_to_delete)
        # 验证操作成功: 手动检查VCR cassette
        # apig_api_action_delete以确认
        # DELETE /v2/{project_id}/apigw/instances/{instance_id}/apis/{api_id}被调用


class StageResourceTest(BaseTest):
    """测试API网关环境资源，过滤器和操作"""

    def test_stage_query(self):
        """测试环境资源查询和增强"""
        factory = self.replay_flight_data("apig_stage_query")
        p = self.load_policy(
            {
                "name": "apig-stage-query",
                "resource": "huaweicloud.rest-stage",
            },
            session_factory=factory,
        )
        resources = p.run()
        # 验证VCR: apig_stage_query应包含1个环境
        self.assertEqual(len(resources), 1)
        # 验证VCR: 值应与apig_stage_query中的'name'匹配
        self.assertEqual(resources[0]["name"], "TEST")

    def test_stage_action_update(self):
        """测试更新环境操作"""
        factory = self.replay_flight_data("apig_stage_action_update")
        # 从apig_stage_action_update获取要更新的环境ID
        # 验证VCR: 匹配apig_stage_action_update中的'id'
        stage_id_to_update = "2c9eb1538a138432018a13zzzzz00001"
        new_name = "updated-test-env"
        new_description = "Updated by Cloud Custodian"  # 更新后的描述
        p = self.load_policy(
            {
                "name": "apig-stage-action-update",
                "resource": "huaweicloud.rest-stage",
                "filters": [{"type": "value", "key": "id", "value": stage_id_to_update}],
                "actions": [{
                    "type": "update",
                    "name": new_name,
                    "reamrk": new_description,
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # 断言主要验证策略是否正确过滤目标资源
        self.assertEqual(resources[0]['id'], stage_id_to_update)

    def test_stage_action_delete(self):
        """测试删除环境操作"""
        factory = self.replay_flight_data("apig_stage_action_delete")
        # 从apig_stage_action_delete获取要删除的环境ID
        # 验证VCR: 匹配apig_stage_action_delete中的'id'
        stage_id_to_delete = "2c9eb1538a138432018a13xxxxx00001"
        p = self.load_policy(
            {
                "name": "apig-stage-action-delete",
                "resource": "huaweicloud.rest-stage",
                "filters": [{"type": "value", "key": "id", "value": stage_id_to_delete}],
                "actions": ["delete"],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # 断言主要验证策略是否正确过滤目标资源
        self.assertEqual(resources[0]['id'], stage_id_to_delete)
        # 验证操作成功: 手动检查VCR cassette
        # apig_stage_action_delete以确认
        # DELETE /v2/{project_id}/apigw/instances/{instance_id}/envs/{env_id}被调用


class DomainNameResourceTest(BaseTest):
    """测试API网关域名资源，过滤器和操作"""

    def test_domain_name_query(self):
        """测试域名资源查询和增强"""
        factory = self.replay_flight_data("apig_domain_name_query")
        p = self.load_policy(
            {
                "name": "apig-domain-name-query",
                "resource": "huaweicloud.apigw-domain-name",
            },
            session_factory=factory,
        )
        resources = p.run()
        # 验证VCR: apig_domain_name_query应包含1个域名
        self.assertEqual(len(resources), 1)
        # 验证VCR: 值应与apig_domain_name_query中的'name'匹配
        self.assertEqual(resources[0]["name"], "example.com")
        self.assertTrue("url_domain" in resources[0])  # 验证增强添加了信息

   


class ApiGroupResourceTest(BaseTest):
    """测试API网关分组资源，过滤器和操作"""

    def test_api_group_query(self):
        """测试API分组资源查询和增强"""
        factory = self.replay_flight_data("apig_group_query")
        p = self.load_policy(
            {
                "name": "apig-group-query",
                "resource": "huaweicloud.api-groups",
            },
            session_factory=factory,
        )
        resources = p.run()
        # 验证VCR: apig_group_query应包含API分组
        self.assertEqual(len(resources), 1)
        # 验证VCR: 值应与apig_group_query中的'name'匹配
        self.assertEqual(resources[0]["name"], "api_group_001")
        self.assertTrue("status" in resources[0])  # 验证增强添加了信息

    def test_api_group_action_update_security(self):
        """测试更新域名安全策略操作"""
        factory = self.replay_flight_data("apig_group_action_update_security")
        # 从apig_group_action_update_security获取分组ID和域名ID
        # 验证VCR: 匹配apig_group_action_update_security中的分组'id'
        group_id_to_update = "c77f5e81d9cb4424bf704ef2b0ac7600"
        # 验证VCR: 匹配apig_group_action_update_security中的域名'id'
        domain_id_to_update = "2c9eb1538a138432018a13ccccc00001"
        # 验证VCR: 匹配apig_group_action_update_security中的初始'min_ssl_version'
        original_min_ssl_version = "TLSv1.1"
        new_min_ssl_version = "TLSv1.2"  # 更新后的TLS版本
        p = self.load_policy(
            {
                "name": "apig-group-action-update-security",
                "resource": "huaweicloud.api-groups",
                "filters": [{"type": "value", "key": "id", "value": group_id_to_update}],
                "actions": [{
                    "type": "update-security",
                    "min_ssl_version": new_min_ssl_version,
                    "domain_id": domain_id_to_update
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # 断言主要验证策略是否正确过滤目标资源
        self.assertEqual(resources[0]['id'], group_id_to_update)
        # 验证域名数据是否正确
        url_domains = resources[0].get('url_domains', [])
        self.assertTrue(len(url_domains) > 0)
        domain_found = False
        for domain in url_domains:
            if domain['id'] == domain_id_to_update:
                domain_found = True
                self.assertEqual(domain['min_ssl_version'], original_min_ssl_version)
                break
        self.assertTrue(domain_found, "未在分组中找到指定域名")
        # 验证操作成功: 手动检查VCR cassette
        # apig_group_action_update_security以确认
        # PUT /v2/{project_id}/apigw/instances/{instance_id}/api-groups/{group_id}/domains/{domain_id}被调用，
        # 并包含正确的body(min_ssl_version)



# =========================
# 可复用功能测试（使用API资源作为示例）
# =========================

class ReusableFeaturesTest(BaseTest):
    """测试在API网关资源上可复用的过滤器和操作"""

    def test_filter_value_match(self):
        """测试值过滤器 - 匹配"""
        factory = self.replay_flight_data("apig_api_filter_value_method")
        # 从apig_api_filter_value_method获取方法值
        # 验证VCR: 匹配'method-get.example.com'的方法在apig_api_filter_value_method中
        target_method = "GET"
        p = self.load_policy(
            {
                "name": "apig-filter-value-method-match",
                "resource": "huaweicloud.rest-api",
                "filters": [{"type": "value", "key": "req_method", "value": target_method}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # 验证VCR: 只有一个API在apig_api_filter_value_method匹配此方法
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['req_method'], target_method)

    def test_filter_value_no_match(self):
        """测试值过滤器 - 不匹配"""
        factory = self.replay_flight_data("apig_api_filter_value_method")  # 重用
        wrong_method = "DELETE"
        p = self.load_policy(
            {
                "name": "apig-filter-value-method-no-match",
                "resource": "huaweicloud.rest-api",
                "filters": [{"type": "value", "key": "req_method", "value": wrong_method}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # 验证VCR: 没有API在apig_api_filter_value_method匹配此方法
        self.assertEqual(len(resources), 0)

    def test_filter_tag_count_match(self):
        """测试标签计数过滤器 - 匹配"""
        # 验证VCR: API 'api-two-tags.example.com'在apig_api_filter_tag_count应有2个标签
        factory = self.replay_flight_data("apig_api_filter_tag_count")
        # 验证VCR: 匹配'api-two-tags.example.com'的标签计数在apig_api_filter_tag_count中
        expected_tag_count = 2
        p = self.load_policy(
            {
                "name": "apig-filter-tag-count-match",
                "resource": "huaweicloud.rest-api",
                "filters": [{"type": "tag-count", "count": expected_tag_count}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # 验证VCR: 只有一个API在apig_api_filter_tag_count具有恰好2个标签
        self.assertEqual(len(resources), 1)

    def test_action_tag_and_remove_tag(self):
        """测试标签添加和删除操作"""
        factory = self.replay_flight_data("apig_api_action_tag")
        # 从apig_api_action_tag获取API ID
        # 验证VCR: 匹配apig_api_action_tag中的'id'
        api_id_to_tag = "2c9eb1538a138432018a13ddddd00001"
        tag_key = "environment"
        tag_value = "test"
        
        # 添加标签策略
        p = self.load_policy(
            {
                "name": "apig-api-tag",
                "resource": "huaweicloud.rest-api",
                "filters": [{"type": "value", "key": "id", "value": api_id_to_tag}],
                "actions": [{
                    "type": "tag",
                    "key": tag_key,
                    "value": tag_value
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        
        # 移除标签策略
        p = self.load_policy(
            {
                "name": "apig-api-remove-tag",
                "resource": "huaweicloud.rest-api",
                "filters": [{"type": "value", "key": "id", "value": api_id_to_tag}],
                "actions": [{
                    "type": "remove-tag",
                    "tags": [tag_key]
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        
        # 验证操作成功: 手动检查VCR cassette
        # apig_api_action_tag以确认标签API调用

    def test_action_mark_for_op(self):
        """测试标记操作"""
        factory = self.replay_flight_data("apig_api_action_mark_for_op")
        # 从apig_api_action_mark_for_op获取API ID
        # 验证VCR: 匹配apig_api_action_mark_for_op中的'id'
        api_id_to_mark = "2c9eb1538a138432018a13eeeee00001"
        
        p = self.load_policy(
            {
                "name": "apig-api-mark-for-delete",
                "resource": "huaweicloud.rest-api",
                "filters": [{"type": "value", "key": "id", "value": api_id_to_mark}],
                "actions": [{
                    "type": "mark-for-op",
                    "op": "delete",
                    "days": 7
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        
        # 验证操作成功: 手动检查VCR cassette
        # apig_api_action_mark_for_op以确认标签API调用

