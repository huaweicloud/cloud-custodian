# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

log = logging.getLogger('custodian.huaweicloud.resources.vpcep')


@resources.register('vpcep-ep')
class VpcEndpoint(QueryResourceManager):
    """Huawei Cloud VPC Endpoint Resource Manager

    :example:

    .. code-block:: yaml

        policies:
          - name: list-vpc-endpoints
            resource: huaweicloud.vpcep-ep
    """
    class resource_type(TypeInfo):
        service = 'vpcep-ep'
        enum_spec = ('list_endpoints', 'endpoints', 'offset')
        id = 'id'
        name = 'endpoint_service_name'
        filter_name = 'endpoint_service_name'
        filter_type = 'scalar'
        taggable = True
        tag_resource_type = 'vpcep-ep'
