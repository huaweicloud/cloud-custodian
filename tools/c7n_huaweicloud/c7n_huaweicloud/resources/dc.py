# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.filters.tms import register_tms_filters
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkdc.v3 import (
    ShowDirectConnectRequest,
    CreateResourceTagRequest,
    DeleteResourceTagRequest
)

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
        enum_spec = ('list_direct_connects', 'direct_connects', None)
        id = 'id'
        name = 'name'
        tag_resource_type = 'direct-connect'

    def augment(self, resources):
        """Enhance resource information

        Get more detailed information for each direct connect resource and process tag formats
        """
        client = self.get_client()
        for r in resources:
            try:
                request = ShowDirectConnectRequest(direct_connect_id=r['id'])
                response = client.show_direct_connect(request)
                detail = response.to_dict()
                if 'direct_connect' in detail:
                    r.update(detail['direct_connect'])

                # Process tag format, convert to AWS compatible format
                if 'tags' in r and isinstance(r['tags'], list):
                    tags = []
                    for tag in r['tags']:
                        if isinstance(tag, dict) and 'key' in tag and 'value' in tag:
                            tags.append({'Key': tag['key'], 'Value': tag['value']})
                    r['Tags'] = tags
            except exceptions.ClientRequestException as e:
                log.warning(
                    f"Unable to get details for direct connect {r['id']}: {e.error_msg}"
                )
        return resources


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


@DC.action_registry.register('tag')
class DCTag(HuaweiCloudBaseAction):
    """
    Add or update tags for direct connect resources

    This operation allows users to add specified tags to direct connect resources.
    If the tag already exists, it will update the tag value.

    :example:
    Add 'Environment=Production' tag to all direct connect resources:

    .. code-block:: yaml

        policies:
          - name: tag-dc-production
            resource: huaweicloud.dc
            actions:
              - type: tag                   # Action type
                key: Environment            # Tag key to add/update
                value: Production           # Tag value to set
    """
    # Define the input schema for this operation
    schema = type_schema(
        'tag',  # Action type name
        key={'type': 'string'},  # Tag key
        value={'type': 'string'},  # Tag value
        # Declare 'key' and 'value' parameters are required
        required=['key', 'value']
    )

    def perform_action(self, resource):
        """
        Perform add/update tag operation on a single resource

        :param resource: Direct connect resource dictionary to add tags to
        :return: None
        """
        key = self.data.get('key')
        value = self.data.get('value')

        # Get resource ID and name
        resource_id = resource.get('id')
        resource_name = resource.get('name', 'Unknown name')

        if not resource_id:
            log.error(
                f"Cannot add tag to direct connect resource missing 'id': {resource_name}"
            )
            return None

        # Get Huawei Cloud DC service client
        client = self.manager.get_client()
        project_id = client._credentials.project_id

        try:
            # Build create tag request
            request = CreateResourceTagRequest()
            request.direct_connect_id = resource_id
            request.project_id = project_id
            # Direct connect physical connection resource type
            request.resource_type = "dc-directconnect"
            request.resource_id = resource_id
            # Set request body, including tag key-value pair
            request.body = {"tag": {"key": key, "value": value}}

            # Call API to execute operation
            client.create_resource_tag(request)
            log.info(
                f"Added/updated tag for direct connect "
                f"{resource_name} ({resource_id}): {key}={value}"
            )
        except exceptions.ClientRequestException as e:
            # Handle API request exceptions
            log.error(
                f"Unable to add/update tag {key} for direct connect "
                f"{resource_name} ({resource_id}): "
                f"{e.error_msg} (status code: {e.status_code})"
            )
        except Exception as e:
            # Handle other potential exceptions
            log.error(
                f"Unable to add/update tag {key} for direct connect "
                f"{resource_name} ({resource_id}): {str(e)}"
            )

        return None


@DC.action_registry.register('remove-tag')
class DCRemoveTag(HuaweiCloudBaseAction):
    """
    Remove one or more specified tags from direct connect resources

    Allows users to remove tags from direct connect resources based on tag keys

    :example:
    Remove 'Temporary' tag from all direct connect resources:

    .. code-block:: yaml

        policies:
          - name: remove-temp-dc-tags
            resource: huaweicloud.dc
            # Can add filters to ensure only resources with this tag are processed
            filters:
              - "tag:Temporary": present
            actions:
              - type: remove-tag            # Action type
                key: Temporary              # Tag key to remove (required)
              # Can specify multiple keys to remove multiple tags at once
              # - type: remove-tag
              #   keys: ["Temp1", "Temp2"]
    """
    # Define the input schema for this operation
    schema = type_schema(
        'remove-tag',  # Action type name
        # Can specify either a single key or a list of keys
        key={'type': 'string'},  # Single tag key to remove
        keys={'type': 'array', 'items': {'type': 'string'}},  # List of tag keys to remove
    )

    def perform_action(self, resource):
        """
        Perform remove tag operation on a single resource

        :param resource: Direct connect resource dictionary to remove tags from
        :return: None
        """
        # Get the list of tag keys to remove
        tags_to_remove = self.data.get('keys', [])
        single_key = self.data.get('key')
        if single_key and single_key not in tags_to_remove:
            tags_to_remove.append(single_key)

        if not tags_to_remove:
            log.warning("Remove tag operation did not specify tag keys (key or keys)")
            return None

        # Get resource ID and name
        resource_id = resource.get('id')
        resource_name = resource.get('name', 'Unknown name')

        if not resource_id:
            log.error(
                f"Cannot remove tags from direct connect resource missing 'id': {resource_name}"
            )
            return None

        # Check tags that actually exist on the resource, avoid trying to delete non-existent tags
        current_tags = set()

        # Process normalized AWS format tags
        if 'Tags' in resource:
            current_tags = {t.get('Key') for t in resource.get('Tags', [])}
        # Process original format tags
        elif 'tags' in resource:
            tags = resource.get('tags', [])
            if isinstance(tags, list):
                for tag in tags:
                    if isinstance(tag, dict) and 'key' in tag:
                        current_tags.add(tag.get('key'))

        keys_that_exist = [k for k in tags_to_remove if k in current_tags]

        if not keys_that_exist:
            log.debug(
                f"Direct connect {resource_name} ({resource_id}) "
                f"does not have tags to remove: {tags_to_remove}"
            )
            return None

        # Get Huawei Cloud DC service client
        client = self.manager.get_client()
        # Get project ID
        project_id = client._credentials.project_id

        # Call API for each tag key to delete
        for key in keys_that_exist:
            try:
                # Build delete tag request
                request = DeleteResourceTagRequest()
                # Set path parameters according to API documentation
                request.project_id = project_id
                # Direct connect physical connection resource type
                request.resource_type = "dc-directconnect"
                request.resource_id = resource_id
                request.key = key

                # Call API to execute deletion
                client.delete_resource_tag(request)
                log.info(
                    f"Removed tag from direct connect {resource_name} "
                    f"({resource_id}): {key}"
                )
            except exceptions.ClientRequestException as e:
                # Handle API request exceptions
                log.error(
                    f"Unable to remove tag {key} from direct connect "
                    f"{resource_name} ({resource_id}): "
                    f"{e.error_msg} (status code: {e.status_code})"
                )
            except Exception as e:
                # Handle other potential exceptions
                log.error(
                    f"Unable to remove tag {key} from direct connect "
                    f"{resource_name} ({resource_id}): {str(e)}"
                )

        return None


# Register TMS tag related filters
register_tms_filters(DC.filter_registry)
