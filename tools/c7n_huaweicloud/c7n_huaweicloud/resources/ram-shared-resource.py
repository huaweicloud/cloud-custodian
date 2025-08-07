# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

log = logging.getLogger("custodian.huaweicloud.resources.ram-shared-resource")


@resources.register('ram-shared-resource')
class RAMSharedResources(QueryResourceManager):
    """ram-shared-resource.

    :Example:

    Returns all external shared principals

    .. code-block::yaml

        policies:
          - name: search-shared-resource
            resource:huaweicloud.RAMSharedResources
            filters:
            - type: value
              key: external
              vaule: true
    """
    class resource_type(TypeInfo):
        service = 'ram-shared-resource'
        enum_spec = ("search_shared_resources", 'shared_resources', 'marker')
        id = 'resource_share_id'
