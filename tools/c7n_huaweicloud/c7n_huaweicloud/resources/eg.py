# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdktms.v1 import (
    ShowResourceTagRequest
)

from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n.filters.core import AgeFilter
from c7n.utils import local_session, type_schema

log = logging.getLogger('custodian.huaweicloud.eg')

@resources.register('eventstreaming')
class EventStreaming(QueryResourceManager):
    """Huawei Cloud EventGrid EventStreaming Resource Manager.

    :example:

    .. code-block:: yaml

        policies:
          - name: event-streaming-policy
            resource: huaweicloud.eventstreaming
            # EventGrid service is only available in cn-east-2, cn-east-3, cn-north-4
            region: cn-north-4 
    """
    
    class resource_type(TypeInfo):
        service = 'eg'
        enum_spec = ('list_event_streaming', 'items', 'offset')
        id = 'id'
        name = 'name'
        filter_name = 'name'
        filter_type = 'scalar'
        taggable = True
        tag_resource_type = 'EGS_EVENTSTREAMING'

    def augment(self, resources):
        """Augment resources with tag information.

        :param resources: List of EventStreaming resource dictionaries.
        :return: Augmented list of resources.
        """
        if not resources:
            return resources
            
        # Attempt to create TMS client to query tags
        try:
            session = local_session(self.session_factory)
            client = session.client('tms')
            
            for resource in resources:
                try:
                    request = ShowResourceTagRequest()
                    request.resource_id = resource['id']
                    request.resource_type = self.resource_type.tag_resource_type
                    
                    response = client.show_resource_tag(request)
                    
                    # Format tags into the expected structure
                    if hasattr(response, 'tags') and response.tags is not None:
                        tags = []
                        for tag in response.tags:
                            tags.append({
                                'key': tag.key,
                                'value': tag.value
                            })
                        resource['tags'] = tags
                    else:
                        resource['tags'] = []
                except exceptions.ClientRequestException as e:
                    self.log.warning(
                        f"Failed to retrieve tags for EventStreaming {resource['id']}: "
                        f"{e.error_code} - {e.error_msg}")
                    # Do not modify the resource or set empty tags on client exception
        except Exception as e:
            self.log.error(f"Error during tag augmentation: {str(e)}")
            # Return original resources if any error occurs during the process
            
        return resources


@EventStreaming.filter_registry.register('age')
class EventStreamingAgeFilter(AgeFilter):
    """Filters EventStreaming resources based on their creation time.
    
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
