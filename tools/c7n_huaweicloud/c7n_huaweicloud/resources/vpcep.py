# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from c7n.utils import type_schema
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


    """Filter VPC endpoints by service name and VPC ID list

    The endpoint_service_name parameter is required.
    The vpc_ids parameter (list type) is optional.
    
    If only endpoint_service_name is provided, returns all endpoints matching the service name.
    If both endpoint_service_name and vpc_ids are provided, returns endpoints that match both
    the service name and all VPC IDs in the list.

    :example:

    .. code-block:: yaml

        policies:
            - name: vpc-endpoints-with-specific-service-in-vpcs
            resource: huaweicloud.vpcep-ep
            filters:
                - type: by-service-name-and-vpcs
                endpoint_service_name: "com.huaweicloud.service.test"
                vpc_ids: 
                    - vpc-12345678
                    - vpc-87654321
    """
    schema = type_schema(
        'by-service-name-and-vpcs', 
        endpoint_service_name={'type': 'string'},
        vpc_ids={'type': 'array', 'items': {'type': 'string'}},
        required=['endpoint_service_name']
    )

    def process(self, resources, event=None):
        endpoint_service_name = self.data.get('endpoint_service_name')
        vpc_ids = self.data.get('vpc_ids', [])
        
        # Validate that endpoint_service_name is valid
        if not endpoint_service_name:
            self.log.error("endpoint_service_name is required and cannot be empty")
            return []
        
        # First filter resources that match endpoint_service_name
        results = []
        for resource in resources:
            if resource.get('endpoint_service_name') == endpoint_service_name:
                # If vpc_ids is not provided or empty, add the resource directly
                if not vpc_ids:
                    results.append(resource)
                # Otherwise, check if the resource's vpc_id is in the vpc_ids list
                elif resource.get('vpc_id') in vpc_ids:
                    results.append(resource)
        
        # If vpc_ids are provided but not all VPC IDs are matched, return empty list
        if vpc_ids and len(results) < len(vpc_ids):
            # Get all matching resource vpc_ids
            found_vpc_ids = {r.get('vpc_id') for r in results}
            # Check if all vpc_ids are found
            if not set(vpc_ids).issubset(found_vpc_ids):
                self.log.info(
                    f"No endpoints found containing all specified VPCs: {', '.join(vpc_ids)}")
                return []
        
        return results