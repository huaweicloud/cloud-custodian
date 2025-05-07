# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from datetime import datetime, timedelta
from dateutil.parser import parse
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkccm.v1 import (
    ListCertTagsRequest,
    # 证书管理相关
    DeleteCertificateRequest,
)

from c7n.utils import type_schema
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
# 导入TMS相关的过滤器和动作
from c7n_huaweicloud.filters.tms import TagCountFilter, TagActionFilter
from c7n_huaweicloud.actions.autotag import AutoTagUser

log = logging.getLogger('custodian.huaweicloud.ccm')


@resources.register('certificate')
class Certificate(QueryResourceManager):
    """华为云SSL证书管理器

    :示例:

    .. code-block:: yaml

        policies:
          - name: certificate-expiring-soon
            resource: huaweicloud.certificate
            filters:
              - type: value
                key: status
                value: ISSUED
    """

    class resource_type(TypeInfo):
        service = 'ccm'
        enum_spec = ('list_certificates', 'certificates', None)
        id = 'id'
        name = 'name'
        filter_name = 'name'
        filter_type = 'scalar'
        taggable = True
        # 设置标签资源类型，用于TMS操作
        tag_resource_type = 'scm_cert'

    def __init__(self, ctx, data):
        super(Certificate, self).__init__(ctx, data)
        # 注册TMS相关过滤器
        self.filter_registry.register('tag-count', TagCountFilter)
        self.filter_registry.register('marked-for-op', TagActionFilter)
        # 注册自动标记用户操作
        self.action_registry.register('auto-tag-user', AutoTagUser)

    def augment(self, resources):
        """增加资源信息，添加标签等。"""
        client = self.get_client()
        
        for r in resources:
            try:
                # 获取证书标签
                request = ListCertTagsRequest(certificate_id=r['id'])
                response = client.list_cert_tags(request)
                if response.tags:
                    # 注意：这里将SDK返回的标签对象转换为字典，以便与TMS过滤器兼容
                    tag_dict = {}
                    for tag in response.tags:
                        tag_dict[tag.key] = tag.value
                    r['tags'] = tag_dict
            except exceptions.ClientRequestException as e:
                log.warning(
                    f"获取证书标签失败 ({r.get('name', r.get('id', '未知'))})："
                    f"RequestId: {e.request_id}, Error: {e.error_msg}"
                )
                
        return resources



@Certificate.action_registry.register('delete')
class DeleteCertificateAction(HuaweiCloudBaseAction):
    """删除证书操作

    :示例:

    .. code-block:: yaml

        policies:
          - name: delete-expired-certificates
            resource: huaweicloud.certificate
            filters:
              - type: value
                key: status
                value: EXPIRED
            actions:
              - delete
    """

    schema = type_schema('delete')

    def perform_action(self, resource):
        client = self.manager.get_client()
        certificate_id = resource['id']
        
        try:
            request = DeleteCertificateRequest(certificate_id=certificate_id)
            client.delete_certificate(request)
            self.log.info(
                f"成功删除证书: {resource.get('name')} (ID: {certificate_id})"
            )
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"删除证书失败 {resource.get('name')} (ID: {certificate_id}): "
                f"RequestId: {e.request_id}, Error: {e.error_msg}"
            )
            raise
