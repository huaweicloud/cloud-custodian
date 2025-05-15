# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

from c7n.filters.core import AgeFilter
from c7n.utils import type_schema

log = logging.getLogger("custodian.huaweicloud.resources.dc")


@resources.register('dc')
class DC(QueryResourceManager):
    """Huawei Cloud Direct Connect Resource Management

    This class manages Huawei Cloud Direct Connect service resources,
    allowing for querying, filtering, and operations on direct connect connections.

    :example:
    Query all Direct Connect resources in the current project:

    .. code-block:: yaml

        policies:
          - name: dc-query
            resource: huaweicloud.dc
    """

    class resource_type(TypeInfo):
        service = 'dc'
        enum_spec = ('list_direct_connects', 'direct_connects', 'marker')
        id = 'id'
        name = 'name'
        tag_resource_type = 'dc-directconnect'


@DC.filter_registry.register('age')
class DCAgeFilter(AgeFilter):
    """Direct Connect resource creation time filter

    Filter based on the creation time of direct connect resources,
    can be used to filter resources earlier or later than a specified time.

    :example:
    Find direct connect resources created more than 90 days ago:

    .. code-block:: yaml

        policies:
          - name: dc-older-than-90-days
            resource: huaweicloud.dc
            filters:
              - type: age                   # Filter type
                days: 90                    # Specified days
                op: gt                      # Operator, gt means 'greater than' (older than)
                                            # Other available operators: lt (younger than), ge, le
    """
    # Define the input schema for this filter
    schema = type_schema(
        'age',  # Filter type name
        # Define comparison operation, reference common filter definition
        op={'$ref': '#/definitions/filters_common/comparison_operators'},
        # Define time unit parameters
        days={'type': 'number'},  # Days
        hours={'type': 'number'},  # Hours
        minutes={'type': 'number'}  # Minutes
    )

    # Specify the field name representing creation time in the resource dictionary
    date_attribute = "create_time"
