# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.filters.vpc import SecurityGroupFilter
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from dateutil.parser import parse
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkrocketmq.v2.model import (
    DeleteInstanceRequest,
    BatchCreateOrDeleteRocketmqTagRequest,
    BatchCreateOrDeleteTagReq,
)
from huaweicloudsdkrocketmq.v2.model import TagEntity as SDKTagEntity

from c7n.filters import Filter, ValueFilter, OPERATORS
from c7n.filters.core import ListItemFilter, ListItemResourceManager
from c7n.utils import type_schema, local_session

log = logging.getLogger("custodian.huaweicloud.resources.rocketmq")


@resources.register('reliabilitys')
class RocketMQ(QueryResourceManager):
    """HuaweiCloud RocketMQ Instance Resource Manager.

    Responsible for discovering, filtering, and managing RocketMQ instance resources on HuaweiCloud.
    Inherits from QueryResourceManager to utilize its capabilities for querying and processing resource lists.

    :example:
    Define a simple policy to get all RocketMQ instances:

    .. code-block:: yaml

        policies:
          - name: rocketmq-instances-discovery  # Policy name
            resource: huaweicloud.reliabilitys  # Specify resource type as HuaweiCloud RocketMQ
    """

    class resource_type(TypeInfo):
        """Define RocketMQ resource metadata and type information"""
        service = 'reliabilitys'  # Specify the corresponding HuaweiCloud service name
        # Specify API operations, result list key, and pagination parameters for enumerating resources
        # 'list_instances' is the API method name
        # 'instances' is the field name in the response that contains the instance list
        # 'offset' is the pagination parameter name
        enum_spec = ('list_instances', 'instances',
                     'offset', 10)
        id = 'instance_id'  # Specify the field name for the resource's unique identifier
        name = 'name'  # Specify the field name for the resource's name
        date = 'created_at'  # Specify the field name for the resource's creation time
        tag = True  # Indicate that this resource supports tags
        tag_resource_type = 'rocketmq'  # Specify the resource type for querying tags

    def augment(self, resources):
        """
        Enhance the raw resource data obtained from the API.

        Primarily used to convert the tag list format returned by HuaweiCloud API
        (usually a list of dictionaries with 'key' and 'value' fields)
        to AWS-compatible format used internally by Cloud Custodian 
        (a list of dictionaries with 'Key' and 'Value' fields).
        This improves consistency of cross-cloud provider policies.

        :param resources: List of raw resource dictionaries from the API
        :return: Enhanced resource dictionary list with tags converted to AWS-compatible format under the 'Tags' key
        """
        for r in resources:
            # Check if 'tags' key exists in the original resource dictionary
            if 'tags' not in r:
                continue  # Skip this resource if it has no tags
            tags = []
            # Iterate through the original tag list
            for tag_entity in r['tags']:
                # Convert each tag to {'Key': ..., 'Value': ...} format
                tags.append({'Key': tag_entity.get('key'),
                            'Value': tag_entity.get('value')})
            # Add the converted tag list to the resource dictionary with the key 'Tags'
            r['Tags'] = tags
        return resources

    def query(self, **params):
        """
        Override query method to add better error handling and debugging.

        :param params: Parameters to pass to the API client
        :return: List of resources
        """
        client = self.get_client()
        resources = []

        enum_op, enum_path, pagination_key, pagination_batch = self.get_enum_op_config()

        try:
            # Check how many total resources we have to establish expected count
            log.info(
                f"Querying RocketMQ resources with config: op={enum_op}, path={enum_path}")

            # Perform API call with initial parameters
            params_copy = params.copy()
            if pagination_key:
                params_copy[pagination_key] = 0  # Start at offset 0

            page = 1
            total_items = 0
            while True:
                try:
                    log.debug(f"API call {enum_op} with params: {params_copy}")
                    response = getattr(client, enum_op)(**params_copy)

                    if response is None:
                        log.warning(f"API call {enum_op} returned None")
                        break

                    # Extract data from the response
                    data = response
                    if hasattr(response, 'to_dict'):
                        data = response.to_dict()

                    # Navigate to the correct response path
                    path_parts = enum_path.split('.')
                    for part in path_parts:
                        if part and data:
                            data = data.get(part, [])

                    if not data:
                        log.debug(
                            f"No data found at path {enum_path} in response")
                        break

                    # Add resources from this page
                    item_count = len(data)
                    resources.extend(data)
                    total_items += item_count
                    log.debug(
                        f"Retrieved page {page} with {item_count} resources, total now: {total_items}")

                    # Check if we need to paginate
                    if pagination_key and item_count >= pagination_batch:
                        # Move to next page
                        params_copy[pagination_key] = params_copy.get(
                            pagination_key, 0) + pagination_batch
                        page += 1
                    else:
                        # No more pages
                        break

                except Exception as e:
                    log.error(
                        f"Error during API call {enum_op} (page {page}): {e}")
                    break

            log.info(f"Total RocketMQ resources retrieved: {len(resources)}")

        except Exception as e:
            log.error(f"Failed to query RocketMQ resources: {e}")

        return resources


@RocketMQ.filter_registry.register('security-group')
class RocketMQSecurityGroupFilter(SecurityGroupFilter):
    """
    Filter RocketMQ instances based on associated security groups.

    Allows users to filter instances based on properties of the security groups (such as name, ID)
    used by the RocketMQ instance.
    Inherits from the generic `SecurityGroupFilter`.

    :example:
    Find RocketMQ instances using a security_group_id '0e3310ef-6477-4830-b802-12ee99e4fc70':

    .. code-block:: yaml

        policies:
          - name: rocketmq-with-public-sg
            resource: huaweicloud.reliabilitys
            filters:
              - type: value       
                key: security_group_id                  
                value: 0e3310ef-6477-4830-b802-12ee99e4fc70       
    """
    # Specify the field name in the RocketMQ resource dictionary that contains the security group ID
    RelatedIdsExpression = "security_group_id"


@RocketMQ.action_registry.register('delete')
class DeleteRocketMQ(HuaweiCloudBaseAction):
    """
    Delete the specified RocketMQ instance.

    **Warning:** This is a destructive operation that will permanently delete the RocketMQ instance
    and its data. Use with caution.

    :example:
    Delete RocketMQ instances created more than 90 days ago and marked for deletion:

    .. code-block:: yaml

        policies:
          - name: delete-old-marked-rocketmq
            resource: huaweicloud.reliabilitys
            filters:
              - type: marked-for-op
                op: delete
                tag: custodian_cleanup # Assuming this tag is used for marking
              - type: age
                days: 90
                op: gt
            actions:
              - type: delete             # Action type
    """
    # Define the input schema for this action
    schema = type_schema(
        'delete',  # Action type name
        # If API supports force delete, could add parameters like
        # force={'type': 'boolean', 'default': False}
    )

    # Define IAM permissions required to execute this action
    permissions = ('rocketmq:deleteInstance',)

    def perform_action(self, resource):
        """
        Perform delete operation on a single resource.

        :param resource: RocketMQ instance resource dictionary to delete
        :return: API call response (may contain task ID etc.) or None (if failed)
        """
        instance_id = resource.get('instance_id')
        instance_name = resource.get('name', 'unknown name')
        if not instance_id:
            log.error(
                f"Cannot delete RocketMQ resource missing 'instance_id': {instance_name}")
            return None

        # Get HuaweiCloud RocketMQ client
        client = self.manager.get_client()

        try:
            # Construct delete instance request
            request = DeleteInstanceRequest(instance_id=instance_id)
            # Call API to perform delete operation
            response = client.delete_instance(request)
            log.info(
                f"Started delete operation for RocketMQ instance {instance_name} ({instance_id}). "
                f"Response: {response}")
            return response  # Return API response
        except exceptions.ClientRequestException as e:
            log.error(
                f"Unable to delete RocketMQ instance {instance_name} ({instance_id}): "
                f"{e.error_msg} (status code: {e.status_code})")
            return None  # If delete fails, return None
        except Exception as e:
            log.error(
                f"Unable to delete RocketMQ instance {instance_name} ({instance_id}): {str(e)}")
            return None
