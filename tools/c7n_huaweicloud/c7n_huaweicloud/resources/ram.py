# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from huaweicloudsdkram.v1 import DisassociateResourceShareRequest, ResourceShareAssociationReqBody

from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

log = logging.getLogger("custodian.huaweicloud.resources.ram")


@resources.register('ram-shared-principals')
class RAMSharedPrincipals(QueryResourceManager):
    """RAM Shared Principals.

    :Example:

    Returns all external shared principals

    .. code-block::yaml

        policies:
          - name: search-external-shared-principals
            resource:huaweicloud.RAMSharedPrincipals
            filters:
            - type: value
              key: external
              vaule: true
    """
    class resource_type(TypeInfo):
        service = 'ram'
        enum_spec = ("search_resource_share_associations", 'resource_share_associations', 'marker')
        id = 'resource_share_id'


@RAMSharedPrincipals.action_registry.register("disassociate")
class DisassociatedExternalPrincipals(HuaweiCloudBaseAction):
    """Disasssociate External Shared Principals.

    :Example:

    .. code-block::yaml

        policies:
           - name: disassociate-external-shared-principals
             resource:huaweicloud.RAMSharedPrincipals
             filters:
               - type: value
                 key: external
                 vaule: true
             actions:
               - disassociate
    """

    schema = type_schema("disassociate")

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = DisassociateResourceShareRequest(resource_share_id=resource["resource_share_id"])
        principalList = [resource["associated_entity"]]
        request.body = ResourceShareAssociationReqBody(principals=principalList)
        response = client.disassociate_resource_share(request)
        log.info(f"response:{response}")
        response = None
        return response
