# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import os
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdktms.v1 import (
    ShowResourceTagRequest
)

from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n.utils import local_session

log = logging.getLogger('custodian.huaweicloud.eg')


@resources.register('eg-subscription')
class Subscription(QueryResourceManager):
    """Huawei Cloud EventGrid subscription Resource Manager.

    :example:

    .. code-block:: yaml

        policies:
          - name: event-subscription-resource
            resource: huaweicloud.eg-subscription
    """

    class resource_type(TypeInfo):
        service = 'eg'
        enum_spec = ('list_subscriptions', 'items', 'offset')
        id = 'id'
        name = 'name'
        filter_name = 'name'
        filter_type = 'scalar'
        taggable = True
        tag_resource_type = 'SUBSCRIPTION'

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
            # Add tags to resource properties
            for resource in resources:
                try:
                    request = ShowResourceTagRequest()
                    request.resource_id = resource['id']
                    request.resource_type = self.resource_type.tag_resource_type
                    current_tenant = os.getenv('HUAWEI_PROJECT_ID')
                    request.project_id = current_tenant
                    response = client.show_resource_tag(request)
                    tags = []
                    if hasattr(response, 'tags'):
                        tags_raw = response.tags if response.tags is not None else []
                        for tag in tags_raw:
                            if hasattr(tag, 'key') and hasattr(tag, 'value'):
                                tags.append({'key': tag.key, 'value': tag.value})
                    else:
                        self.log.warning("Unexpected response structure: 'tags' attribute missing.")
                    resource['tags'] = tags
                except exceptions.ClientRequestException as e:
                    self.log.warning(
                        f"Failed to retrieve tags for Subscription {resource['id']}: "
                        f"{e.error_code} - {e.error_msg}")
                    # Do not modify the resource or set empty tags on client exception
        except Exception as e:
            self.log.error(f"Error during tag augmentation: {str(e)}")
            # Return original resources if any error occurs during the process
        return resources
