# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkeip.v2 import DeletePublicipRequest
from huaweicloudsdkeip.v3 import DisassociatePublicipsRequest

from c7n.utils import type_schema, local_session
from c7n.filters import Filter
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

log = logging.getLogger("custodian.huaweicloud.resources.eip")


@resources.register("eip")
class EIP(QueryResourceManager):
    """华为云弹性公网IP资源

    :example:

    .. code-block:: yaml

        policies:
          - name: eip-unattached
            resource: huaweicloud.eip
            filters:
              - type: value
                key: status
                value: DOWN
    """

    class resource_type(TypeInfo):
        service = "eip"
        enum_spec = ("list_publicips", "publicips", "marker")
        id = "id"
        tag_resource_type = "eip"


@EIP.filter_registry.register("associate-instance-type")
class AssociateInstanceTypeFilter(Filter):
    """EIP关联的实例类型过滤器

    过滤基于关联的实例类型（例如PORT、NATGW、ELB、ELBV1、VPN等）的EIP

    :example:

    .. code-block:: yaml

        policies:
          - name: eip-associated-with-elb
            resource: huaweicloud.eip
            filters:
              - type: associate-instance-type
                instance_type: ELB
    """
    schema = type_schema(
        "associate-instance-type",
        instance_type={"type": "string", "enum": ["PORT", "NATGW", "ELB", "ELBV1", "VPN", "NONE"]},
        required=["instance_type"]
    )

    def process(self, resources, event=None):
        instance_type = self.data.get("instance_type")
        results = []

        for resource in resources:
            # 检查associate_instance_type是否为空（未关联任何实例）
            resource_instance_type = resource.get("associate_instance_type", "")

            if not resource_instance_type:
                # 未关联任何实例
                if instance_type == "NONE":
                    results.append(resource)
                continue

            # 直接根据API返回的associate_instance_type进行匹配
            if resource_instance_type == instance_type:
                results.append(resource)

        return results


@EIP.action_registry.register("delete")
class EIPDelete(HuaweiCloudBaseAction):
    """删除弹性公网IP

    :example:

    .. code-block:: yaml

        policies:
          - name: delete-unassociated-eips
            resource: huaweicloud.eip
            filters:
              - type: value
                key: status
                value: DOWN
            actions:
              - delete
    """
    schema = type_schema("delete")

    def process(self, resources):
        session = local_session(self.manager.session_factory)
        # 使用eip_v2客户端
        client = session.client('eip_v2')
        for resource in resources:
            try:
                # 使用v2版本的DeletePublicipRequest
                request = DeletePublicipRequest(publicip_id=resource["id"])
                client.delete_publicip(request)
                self.log.info(f"删除弹性公网IP {resource['id']} 成功")
            except exceptions.ClientRequestException as e:
                self.log.error(
                    f"删除弹性公网IP {resource['id']} 失败，"
                    f"请求ID: {e.request_id}, 错误码: {e.error_code}, 错误消息: {e.error_msg}"
                )
                self.handle_exception(resource, resources)
        return self.process_result(resources)

    def perform_action(self, resource):
        # 由于我们在process方法中已经处理了每个资源，所以这里不需要额外的操作
        pass


@EIP.action_registry.register("disassociate")
class EIPDisassociate(HuaweiCloudBaseAction):
    """解绑弹性公网IP

    从已绑定的实例上解绑弹性公网IP

    :example:

    .. code-block:: yaml

        policies:
          - name: disassociate-eips-from-instances
            resource: huaweicloud.eip
            filters:
              - type: value
                key: status
                value: ACTIVE
            actions:
              - disassociate
    """
    schema = type_schema("disassociate")

    def process(self, resources):
        client = self.manager.get_client()
        # 筛选状态为ACTIVE（已绑定）的EIP
        active_resources = [r for r in resources if r.get("status") == "ACTIVE"]

        for resource in active_resources:
            try:
                request = DisassociatePublicipsRequest()
                request.publicip_id = resource["id"]
                client.disassociate_publicips(request)
                self.log.info(f"解绑弹性公网IP {resource['id']} 成功")
            except exceptions.ClientRequestException as e:
                self.log.error(
                    f"解绑弹性公网IP {resource['id']} 失败，"
                    f"请求ID: {e.request_id}, 错误码: {e.error_code}, 错误消息: {e.error_msg}"
                )
                self.handle_exception(resource, active_resources)
        return self.process_result(active_resources)

    def perform_action(self, resource):
        # 由于我们在process方法中已经处理了每个资源，所以这里不需要额外的操作
        pass
