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
)

from c7n.filters import Filter, OPERATORS
from c7n.utils import type_schema


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


@RocketMQ.filter_registry.register('age')
class RocketMQAgeFilter(Filter):
    """
    Filter RocketMQ instances based on creation time (age).

    Allows users to filter instances created earlier or later than a specified time.

    :example:
    Find RocketMQ instances created more than 30 days ago:

    .. code-block:: yaml

        policies:
          - name: rocketmq-older-than-30-days
            resource: huaweicloud.reliabilitys
            filters:
              - type: age                   # Filter type
                days: 30                    # Specify days
                op: gt                      # Operation, gt means "greater than" (older than)
                                            # Other available operators: lt (younger than), ge, le
    """
    # Define the input schema for this filter
    schema = type_schema(
        'age',  # Filter type name
        # Define comparison operation, reference common filter definitions
        op={'$ref': '#/definitions/filters_common/comparison_operators'},
        # Define time unit parameters
        days={'type': 'number'},  # Days
        hours={'type': 'number'},  # Hours
        minutes={'type': 'number'}  # Minutes
    )
    schema_alias = True

    # Specify the field name in the resource dictionary representing creation time
    date_attribute = "created_at"

    def validate(self):
        return self

    def process(self, resources, event=None):
        """
        Filter resources based on age.

        :param resources: List of resources to filter
        :param event: Optional event context
        :return: Filtered resource list
        """
        # Get operator and time
        op = self.data.get('op', 'greater-than')
        if op not in OPERATORS:
            raise ValueError(f"Invalid operator: {op}")
        operator = OPERATORS[op]

        # Calculate comparison date
        from datetime import datetime, timedelta
        from dateutil.tz import tzutc

        days = self.data.get('days', 0)
        hours = self.data.get('hours', 0)
        minutes = self.data.get('minutes', 0)

        now = datetime.now(tz=tzutc())
        threshold_date = now - \
            timedelta(days=days, hours=hours, minutes=minutes)

        log.info(
            f"Age filter: filtering resources created {op} {days} days, {hours} hours, {minutes} minutes ago")
        log.info(f"Age filter: now={now}, threshold_date={threshold_date}")
        log.info(f"Total resources before age filtering: {len(resources)}")

        # Filter resources
        matched = []
        for resource in resources:
            instance_id = resource.get('instance_id', 'unknown')
            name = resource.get('name', 'unknown')
            created_str = resource.get(self.date_attribute)

            if not created_str:
                log.debug(
                    f"Resource {instance_id} ({name}) has no {self.date_attribute}")
                continue

            # Convert creation time
            try:
                created_date = None
                # If it's a millisecond timestamp, convert to seconds then create datetime
                if isinstance(created_str, (int, float)) or (isinstance(created_str, str) and created_str.isdigit()):
                    try:
                        # Ensure conversion to integer
                        timestamp_ms = int(float(created_str))
                        # Check if timestamp is in milliseconds (13 digits) or seconds (10 digits)
                        if len(str(timestamp_ms)) >= 13:
                            timestamp_s = timestamp_ms / 1000.0
                        else:
                            timestamp_s = timestamp_ms
                        log.debug(
                            f"Resource {instance_id}: Converting timestamp: {created_str} -> {timestamp_s} s")
                        # Create datetime object from timestamp (UTC)
                        created_date = datetime.utcfromtimestamp(
                            timestamp_s).replace(tzinfo=tzutc())
                    except (ValueError, TypeError, OverflowError) as e:
                        log.debug(
                            f"Resource {instance_id}: Unable to parse value '{created_str}' as timestamp: {e}")
                        # If parsing fails, continue trying with dateutil.parser
                        created_date = parse(str(created_str))
                else:
                    # If not a pure number, try using dateutil.parser to parse generic time string
                    created_date = parse(str(created_str))

                # Ensure datetime has timezone information
                if not created_date.tzinfo:
                    created_date = created_date.replace(tzinfo=tzutc())

                # Calculate age in days
                age_timedelta = now - created_date
                age_days = age_timedelta.total_seconds() / 86400

                log.debug(
                    f"Resource {instance_id} ({name}) created_date={created_date}, age={age_days:.2f} days")

                # Handle the 'gt' (greater than) case specifically to ensure correctness
                if op == 'greater-than' or op == 'gt':
                    # A resource is older than N days if its creation date is earlier than (now - N days)
                    result = created_date < threshold_date
                    log.debug(
                        f"GT comparison: is {created_date} < {threshold_date}? {result}")
                else:
                    # For other operators, use the standard operator
                    result = operator(created_date, threshold_date)
                    log.debug(
                        f"Standard comparison: {created_date} {op} {threshold_date} = {result}")

                # If operation is 'gt', we only want resources older than threshold
                # If creation date is earlier than threshold, resource is older
                if result:
                    matched.append(resource)
                    log.debug(
                        f"Resource {instance_id} ({name}) matched age filter")
                else:
                    log.debug(
                        f"Resource {instance_id} ({name}) did not match age filter")
            except Exception as e:
                log.warning(
                    f"Unable to parse creation time '{created_str}' for RocketMQ instance "
                    f"{instance_id} ({name}): {e}")

        log.info(
            f"Resources after age filtering: {len(matched)} (matched) / {len(resources)} (total)")
        return matched
