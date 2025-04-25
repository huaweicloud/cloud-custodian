# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkeg.v1 import (
    ListEventStreamingRequest,
    ShowEventStreamingRequest
)

from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n.utils import type_schema
from c7n.filters import ValueFilter, Filter
from c7n.filters.core import AgeFilter
from c7n.utils import local_session
from c7n_huaweicloud.filters.tms import TagActionFilter, TagCountFilter

log = logging.getLogger('custodian.huaweicloud.eg')

@resources.register('eventstreaming')
class EventStreaming(QueryResourceManager):
    """华为云EventGrid事件流资源管理器
    
    :example:

    .. code-block:: yaml

        policies:
          - name: event-streaming
            resource: huaweicloud.eventstreaming
            region: cn-north-4  # EventGrid服务仅支持cn-east-2, cn-east-3, cn-north-4区域
    """
    
    class resource_type(TypeInfo):
        service = 'eg'
        enum_spec = ('list_event_streaming', 'items', 'offset')
        id = 'id'
        name = 'name'
        filter_name = 'name'
        filter_type = 'scalar'
        taggable = True
        tag_resource_type = 'eventstreaming'

    def list_resources(self, query=None):
        """查询事件流列表"""
        client = local_session(self.session_factory).client('eg')
        try:
            # 创建请求对象
            request = ListEventStreamingRequest()
            # 设置请求参数
            if query:
                for key, value in query.items():
                    if hasattr(request, key) and value:
                        setattr(request, key, value)
            # 获取响应
            response = client.list_event_streaming(request)
            resources = response.items if response.items else []
            for resource in resources:
                # 确保每个资源都有id字段
                resource['id'] = resource.get('id', '')
                resource['tag_resource_type'] = self.resource_type.tag_resource_type
            return resources
        except exceptions.ClientRequestException as e:
            self.log.error(f"获取事件流列表失败: {e}")
            return []


@EventStreaming.filter_registry.register('age')
class EventStreamingAgeFilter(AgeFilter):
    """事件流创建时间过滤器
    
    :example:

    .. code-block:: yaml

        policies:
          - name: old-event-streaming
            resource: huaweicloud.eventstreaming
            filters:
              - type: age
                days: 30
                op: gt
    """
    schema = type_schema(
        'age',
        op={'$ref': '#/definitions/filters_common/comparison_operators'},
        days={'type': 'number'},
        hours={'type': 'number'},
        minutes={'type': 'number'}
    )
    date_attribute = "created_time"


# 为EventStreaming资源注册标签过滤器
EventStreaming.filter_registry.register('tag', TagCountFilter)
EventStreaming.filter_registry.register('tag-action', TagActionFilter)
