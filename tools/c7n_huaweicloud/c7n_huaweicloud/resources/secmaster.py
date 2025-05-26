# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import time
from datetime import datetime, timedelta
from dateutil.tz import tzutc
from dateutil.parser import parse

from c7n.utils import type_schema, local_session
from c7n.filters import AgeFilter, ValueFilter
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

from huaweicloudsdksecmaster.v2 import (
    ListWorkspacesRequest,
    ListWorkspacesResponse,
    ListAlertsRequest,
    ListAlertsResponse, 
    ListPlaybooksRequest,
    ListPlaybooksResponse,
    ListPlaybookVersionsRequest,
    ListPlaybookVersionsResponse,
    UpdatePlaybookRequest,
    ModifyPlaybookInfo,
    DataobjectSearch,
)

log = logging.getLogger("custodian.huaweicloud.resources.secmaster")


# 业务需求1：SecMaster实例资源
@resources.register("secmaster")
class SecMaster(QueryResourceManager):
    """华为云SecMaster安全云脑实例资源管理器。
    
    用于管理SecMaster专业版实例，确保安全运营账号覆盖所有业务账号。
    """
    
    class resource_type(TypeInfo):
        service = "secmaster"
        # TODO: 查询SecMaster实例的API暂不满足，需要后续补充
        enum_spec = ("list_instances", "instances", "offset")  
        id = "id"
        name = "name"
        tag_resource_type = ""

    # TODO: 实现获取SecMaster实例列表的逻辑
    def _fetch_resources(self, query):
        """获取SecMaster实例资源列表。
        
        注意：由于查询安全账号是否购买专业版安全云脑实例的API暂不满足，
        此处实现暂时列为TODO。
        """
        log.warning("SecMaster实例查询API暂不满足，返回空列表")
        return []


@SecMaster.action_registry.register("send-msg")
class SecMasterSendMsg(HuaweiCloudBaseAction):
    """SecMaster实例发送消息通知动作。
    
    用于在SecMaster覆盖检查中发送邮件通知。
    
    :example:
    
    .. code-block:: yaml
    
        policies:
          - name: secmaster-coverage-check
            resource: huaweicloud.secmaster
            actions:
              - type: send-msg
                message: "SecMaster实例覆盖检查结果"
                subject: "安全云脑覆盖检查"
    """
    
    schema = type_schema(
        "send-msg",
        message={"type": "string"},
        subject={"type": "string"},
        required=("message",)
    )

    def perform_action(self, resource):
        """执行发送消息动作。
        
        TODO: 邮件通知功能暂不满足，需要后续实现。
        """
        message = self.data.get("message", "SecMaster通知")
        subject = self.data.get("subject", "SecMaster通知")
        
        log.info(f"TODO: 发送SecMaster通知 - 主题: {subject}, 消息: {message}")
        log.info(f"资源ID: {resource.get('id', 'unknown')}")
        
        # TODO: 实现邮件通知逻辑
        return {"status": "TODO", "message": "邮件通知功能待实现"}


# 业务需求2：工作空间资源（已存在，需要完善）
@resources.register("secmaster-workspace")
class SecMasterWorkspace(QueryResourceManager):
    """华为云SecMaster工作空间资源管理器。
    
    用于管理SecMaster工作空间，确保启用基于安全基线的持续资源监控。
    
    重要提示：
    工作空间查询结果中包含 `is_view` 字段，表示是否为工作空间视图。
    通常情况下，建议过滤 `is_view` 为 `false` 的工作空间，
    因为只有真正的工作空间（非视图）才能进行实际的安全操作。
    
    :example:
    
    过滤真正的工作空间（非视图）：
    
    .. code-block:: yaml
    
        policies:
          - name: secmaster-real-workspaces
            resource: huaweicloud.secmaster-workspace
            filters:
              - type: value
                key: is_view
                value: false
            actions:
              - type: send-msg
                message: "发现真正的工作空间"
                subject: "SecMaster工作空间检查"
    """
    
    class resource_type(TypeInfo):
        service = "secmaster"
        enum_spec = ("list_workspaces", "workspaces", "offset", 500)
        id = "id"
        name = "name"
        date = "create_time"
        tag_resource_type = ""


@SecMasterWorkspace.action_registry.register("send-msg") 
class WorkspaceSendMsg(HuaweiCloudBaseAction):
    """工作空间发送消息通知动作。
    
    用于在工作空间检查中发送邮件通知。
    支持在没有工作空间时也发送警告通知。
    
    :example:
    
    .. code-block:: yaml
    
        policies:
          - name: secmaster-workspace-check
            resource: huaweicloud.secmaster-workspace
            actions:
              - type: send-msg
                message: "工作空间状态检查结果"
                subject: "SecMaster工作空间检查"
                
          - name: secmaster-no-workspace-alert
            resource: huaweicloud.secmaster-workspace
            actions:
              - type: send-msg
                message: "警告：未发现任何SecMaster工作空间"
                subject: "SecMaster工作空间缺失警告"
                send_when_empty: true
    """
    
    schema = type_schema(
        "send-msg", 
        message={"type": "string"},
        subject={"type": "string"},
        send_when_empty={"type": "boolean"},
        required=("message",)
    )

    def process(self, resources):
        """处理资源列表，支持在没有资源时发送通知。
        
        如果设置了 send_when_empty=true，则在没有工作空间时也会发送通知。
        """
        # 检查是否需要在没有资源时发送通知
        send_when_empty = self.data.get("send_when_empty", False)
        
        if not resources and send_when_empty:
            # 没有工作空间且需要发送空资源通知
            log.info("未发现任何SecMaster工作空间，发送警告通知")
            
            # 执行空资源通知逻辑
            message = self.data.get("message", "工作空间通知")
            subject = self.data.get("subject", "SecMaster工作空间通知")
            
            log.info(f"TODO: 发送工作空间缺失警告 - 主题: {subject}, 消息: {message}")
            log.info("当前账号未发现任何SecMaster工作空间")
            
            # TODO: 实现邮件通知逻辑
            # 这里可以调用实际的邮件发送逻辑
            
            # 返回空列表，不创建虚拟资源
            return []
        elif not resources:
            # 没有工作空间且不需要发送通知
            log.info("未发现任何SecMaster工作空间")
            return []
        else:
            # 有工作空间，正常处理
            return super().process(resources)

    def perform_action(self, resource):
        """执行发送消息动作。"""
        message = self.data.get("message", "工作空间通知")
        subject = self.data.get("subject", "SecMaster工作空间通知")
        
        log.info(f"TODO: 发送工作空间通知 - 主题: {subject}, 消息: {message}")
        log.info(f"工作空间: {resource.get('name', 'unknown')} (ID: {resource.get('id', 'unknown')})")
        
        # TODO: 实现邮件通知逻辑
        return {"status": "TODO", "message": "邮件通知功能待实现"}


# 业务需求2：告警资源
@resources.register("secmaster-alert")
class SecMasterAlert(QueryResourceManager):
    """华为云SecMaster告警资源管理器。
    
    用于管理SecMaster告警，确保设置日志记录和警报。
    """
    
    class resource_type(TypeInfo):
        service = "secmaster"
        enum_spec = ("list_alerts", "data", "offset") 
        id = "id"
        name = "title"
        date = "create_time"
        tag_resource_type = ""

    def _fetch_resources(self, query):
        """获取告警资源列表。
        
        需要指定workspace_id参数来查询特定工作空间的告警。
        """
        client = self.get_client()
        resources = []
        
        # 获取工作空间列表来查询每个工作空间的告警
        workspace_manager = self.get_resource_manager("huaweicloud.secmaster-workspace")
        workspaces = workspace_manager.resources()
        
        for workspace in workspaces:
            workspace_id = workspace.get("id")
            if not workspace_id:
                continue
                
            offset = 0
            limit = 500
            
            while True:
                try:
                    # 创建搜索请求体
                    search_body = DataobjectSearch(
                        limit=limit,
                        offset=offset
                    )
                    
                    request = ListAlertsRequest(
                        workspace_id=workspace_id,
                        body=search_body
                    )
                    response = client.list_alerts(request)
                    
                    if not response.data:
                        break
                        
                    # 转换响应数据为字典格式
                    for alert in response.data:
                        if hasattr(alert, 'to_dict'):
                            alert_dict = alert.to_dict()
                        else:
                            alert_dict = alert
                        
                        # 保留原始的层级结构，不平铺data_object
                        # 添加工作空间信息到顶层
                        alert_dict['workspace_name'] = workspace.get('name')
                        resources.append(alert_dict)
                    
                    # 检查是否还有更多数据
                    if len(response.data) < limit:
                        break
                        
                    offset += limit
                    
                except Exception as e:
                    error_msg = str(e).lower()
                    # 区分不同类型的错误
                    if any(x in error_msg for x in ['unauthorized', '401', 'authentication', 'credential']):
                        log.error(f"SecMaster告警查询认证失败(工作空间: {workspace_id}): {e}")
                        raise  # 重新抛出认证错误
                    elif any(x in error_msg for x in ['not found', '404', 'resource not exist']):
                        log.info(f"工作空间 {workspace_id} 无告警资源，跳过: {e}")
                        break  # 无告警是正常情况
                    elif any(x in error_msg for x in ['forbidden', '403', 'permission']):
                        log.error(f"SecMaster告警查询权限不足(工作空间: {workspace_id}): {e}")
                        raise  # 重新抛出权限错误
                    else:
                        log.error(f"获取工作空间 {workspace_id} 的告警列表失败: {e}")
                        raise  # 其他未知错误也重新抛出
                
        return resources


@SecMasterAlert.filter_registry.register("age")
class AlertAgeFilter(AgeFilter):
    """SecMaster告警年龄过滤器。
    
    根据告警创建时间筛选N天/时/分内的告警。
    
    :example:
    
    .. code-block:: yaml
    
        policies:
          - name: secmaster-recent-alerts
            resource: huaweicloud.secmaster-alert
            filters:
              - type: age
                days: 7
                op: lt  # 筛选7天内的告警
    """
    
    date_attribute = "create_time"  # 告警创建时间在data_object中
    
    schema = type_schema(
        "age",
        op={"$ref": "#/definitions/filters_common/comparison_operators"},
        days={"type": "number"},
        hours={"type": "number"}, 
        minutes={"type": "number"}
    )


@SecMasterAlert.action_registry.register("send-msg")
class AlertSendMsg(HuaweiCloudBaseAction):
    """告警发送消息通知动作。
    
    用于在告警检查中发送邮件通知，无论是否有告警都会发送。
    
    :example:
    
    .. code-block:: yaml
    
        policies:
          - name: secmaster-alert-notification
            resource: huaweicloud.secmaster-alert
            filters:
              - type: age
                days: 1
                op: lt
            actions:
              - type: send-msg
                message: "发现最近24小时的告警"
                subject: "SecMaster告警通知"
    """
    
    schema = type_schema(
        "send-msg",
        message={"type": "string"},
        subject={"type": "string"},
        required=("message",)
    )

    def perform_action(self, resource):
        """执行发送消息动作。"""
        message = self.data.get("message", "告警通知") 
        subject = self.data.get("subject", "SecMaster告警通知")
        
        # 从嵌套结构中获取告警数据
        data_object = resource.get('data_object', {})
        
        log.info(f"TODO: 发送告警通知 - 主题: {subject}, 消息: {message}")
        log.info(f"工作空间: {resource.get('workspace_name', 'unknown')}")
        
        # TODO: 实现邮件通知逻辑
        return {"status": "TODO", "message": "邮件通知功能待实现"}


# 业务需求3：剧本资源  
@resources.register("secmaster-playbook")
class SecMasterPlaybook(QueryResourceManager):
    """华为云SecMaster剧本资源管理器。
    
    用于管理SecMaster剧本，确保所有高危操作都能上报SecMaster。
    """
    
    class resource_type(TypeInfo):
        service = "secmaster"
        enum_spec = ("list_playbooks", "data", "offset")
        id = "id"
        name = "name"
        date = "create_time"
        tag_resource_type = ""

    def _fetch_resources(self, query):
        """获取剧本资源列表。
        
        需要指定workspace_id参数来查询特定工作空间的剧本。
        """
        client = self.get_client()
        resources = []
        
        # 获取工作空间列表来查询每个工作空间的剧本
        workspace_manager = self.get_resource_manager("huaweicloud.secmaster-workspace")
        workspaces = workspace_manager.resources()
        
        for workspace in workspaces:
            workspace_id = workspace.get("id")
            if not workspace_id:
                continue
                
            offset = 0
            limit = 500
            
            while True:
                try:
                    request = ListPlaybooksRequest(
                        workspace_id=workspace_id,
                        offset=offset,
                        limit=limit
                    )
                    response = client.list_playbooks(request)
                    
                    if not response.data:
                        break
                        
                    # 转换响应数据为字典格式
                    for playbook in response.data:
                        if hasattr(playbook, 'to_dict'):
                            playbook_dict = playbook.to_dict()
                        else:
                            playbook_dict = playbook
                        # 添加工作空间信息
                        playbook_dict['workspace_id'] = workspace_id
                        playbook_dict['workspace_name'] = workspace.get('name')
                        resources.append(playbook_dict)
                    
                    # 检查是否还有更多数据
                    if len(response.data) < limit:
                        break
                        
                    offset += limit
                    
                except Exception as e:
                    error_msg = str(e).lower()
                    # 区分不同类型的错误
                    if any(x in error_msg for x in ['unauthorized', '401', 'authentication', 'credential']):
                        log.error(f"SecMaster剧本查询认证失败(工作空间: {workspace_id}): {e}")
                        raise  # 重新抛出认证错误
                    elif any(x in error_msg for x in ['not found', '404', 'resource not exist']):
                        log.info(f"工作空间 {workspace_id} 无剧本资源，跳过: {e}")
                        break  # 无剧本是正常情况
                    elif any(x in error_msg for x in ['forbidden', '403', 'permission']):
                        log.error(f"SecMaster剧本查询权限不足(工作空间: {workspace_id}): {e}")
                        raise  # 重新抛出权限错误
                    else:
                        log.error(f"获取工作空间 {workspace_id} 的剧本列表失败: {e}")
                        raise  # 其他未知错误也重新抛出
                
        return resources


@SecMasterPlaybook.action_registry.register("enable-playbook")
class EnablePlaybook(HuaweiCloudBaseAction):
    """开启剧本动作。
    
    用于开启指定的SecMaster剧本，确保高危操作能够上报。
    
    :example:
    
    .. code-block:: yaml
    
        policies:
          - name: enable-security-playbooks
            resource: huaweicloud.secmaster-playbook
            filters:
              - type: value
                key: name
                value: "高危操作监控剧本"
              - type: value  
                key: enabled
                value: false
            actions:
              - type: enable-playbook
    """
    
    schema = type_schema("enable-playbook")

    def perform_action(self, resource):
        """执行开启剧本动作。"""
        client = self.manager.get_client()
        workspace_id = resource.get("workspace_id")
        playbook_id = resource.get("id")
        playbook_name = resource.get("name")
        
        if not workspace_id or not playbook_id:
            log.error(f"工作空间ID或剧本ID缺失: workspace_id={workspace_id}, playbook_id={playbook_id}")
            return {"status": "error", "message": "工作空间ID或剧本ID缺失"}
        
        try:
            # 首先查询剧本版本列表，找到最新版本
            log.info(f"查询剧本 {playbook_name} 的版本列表...")
            
            offset = 0
            limit = 500
            latest_version = None
            latest_update_time = None
            
            while True:
                version_request = ListPlaybookVersionsRequest(
                    workspace_id=workspace_id,
                    playbook_id=playbook_id,
                    offset=offset,
                    limit=limit
                )
                
                version_response = client.list_playbook_versions(version_request)
                
                if not version_response.data:
                    break
                
                # 遍历版本列表，找到 update_time 最新的版本
                for version in version_response.data:
                    if hasattr(version, 'to_dict'):
                        version_dict = version.to_dict()
                    else:
                        version_dict = version
                    
                    update_time_str = version_dict.get('update_time')
                    if update_time_str:
                        try:
                            # 解析时间字符串
                            from dateutil.parser import parse
                            update_time = parse(update_time_str)
                            
                            if latest_update_time is None or update_time > latest_update_time:
                                latest_update_time = update_time
                                latest_version = version_dict
                        except Exception as e:
                            log.warning(f"解析版本更新时间失败: {update_time_str}, 错误: {e}")
                            continue
                
                # 检查是否还有更多数据
                if len(version_response.data) < limit:
                    break
                    
                offset += limit
            
            if not latest_version:
                log.error(f"未找到剧本 {playbook_name} 的任何版本")
                return {"status": "error", "message": "未找到剧本版本"}
            
            active_version_id = latest_version.get('id')
            log.info(f"找到最新版本: {latest_version.get('version')} (ID: {active_version_id})")
            
            # 构建修改剧本信息，开启剧本
            modify_info = ModifyPlaybookInfo(
                name=playbook_name,  # 设置剧本名称
                enabled=True,  # 开启剧本
                active_version_id=active_version_id,  # 设置启用的版本ID
                description=resource.get("description", "") + " [已通过策略自动开启]"
            )
            
            request = UpdatePlaybookRequest(
                workspace_id=workspace_id,
                playbook_id=playbook_id,
                body=modify_info
            )
            
            response = client.update_playbook(request)
            
            log.info(f"成功开启剧本: {playbook_name} (ID: {playbook_id}), 启用版本: {latest_version.get('version')}")
            return {
                "status": "success", 
                "message": f"剧本 {playbook_name} 已开启，启用版本: {latest_version.get('version')}",
                "playbook_id": playbook_id,
                "active_version_id": active_version_id,
                "active_version": latest_version.get('version')
            }
            
        except Exception as e:
            log.error(f"开启剧本失败: {e}")
            return {"status": "error", "message": str(e)}


@SecMasterPlaybook.action_registry.register("send-msg")
class PlaybookSendMsg(HuaweiCloudBaseAction):
    """剧本发送消息通知动作。
    
    用于在剧本状态变更时发送邮件通知。
    
    :example:
    
    .. code-block:: yaml
    
        policies:
          - name: secmaster-playbook-notification
            resource: huaweicloud.secmaster-playbook
            filters:
              - type: value
                key: enabled
                value: true
            actions:
              - type: send-msg
                message: "剧本已开启并生效"
                subject: "SecMaster剧本状态通知"
    """
    
    schema = type_schema(
        "send-msg",
        message={"type": "string"},
        subject={"type": "string"},
        required=("message",)
    )

    def perform_action(self, resource):
        """执行发送消息动作。"""
        message = self.data.get("message", "剧本通知")
        subject = self.data.get("subject", "SecMaster剧本通知")
        
        log.info(f"TODO: 发送剧本通知 - 主题: {subject}, 消息: {message}")
        log.info(f"剧本: {resource.get('name', 'unknown')} (ID: {resource.get('id', 'unknown')})")
        log.info(f"工作空间: {resource.get('workspace_name', 'unknown')}")
        log.info(f"剧本状态: {'已开启' if resource.get('enabled') else '未开启'}")
        
        # TODO: 实现邮件通知逻辑
        return {"status": "TODO", "message": "邮件通知功能待实现"}