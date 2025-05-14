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
        # Get operator and time parameters
        op = self.data.get('op', 'greater-than')
        if op not in OPERATORS:
            raise ValueError(f"Invalid operator: {op}")

        # Calculate comparison date
        from datetime import datetime, timedelta
        from dateutil.tz import tzutc

        days = self.data.get('days', 0)
        hours = self.data.get('hours', 0)
        minutes = self.data.get('minutes', 0)

        now = datetime.now(tz=tzutc())
        log.info(f"Age filter: filtering resources created {op} {days} days, {hours} hours, {minutes} minutes ago")

        # Filter resources
        matched = []
        for resource in resources:
            instance_id = resource.get('instance_id', 'unknown')
            name = resource.get('name', 'unknown')
            created_str = resource.get(self.date_attribute)

            if not created_str:
                log.debug(f"Resource {instance_id} ({name}) has no {self.date_attribute}")
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
                        # Create datetime object from timestamp (UTC)
                        created_date = datetime.utcfromtimestamp(
                            timestamp_s).replace(tzinfo=tzutc())
                    except (ValueError, TypeError, OverflowError) as e:
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

                # Perform age comparison based on operator
                result = False
                if op in ('greater-than', 'gt'):
                    # Age > days
                    result = age_days > days
                elif op in ('less-than', 'lt'):
                    # Age < days
                    result = age_days < days
                elif op in ('equal', 'eq'):
                    # Age ≈ days (within 1 day)
                    result = abs(age_days - days) < 1
                elif op in ('greater-or-equal', 'ge'):
                    # Age >= days
                    result = age_days >= days
                elif op in ('less-or-equal', 'le'):
                    # Age <= days
                    result = age_days <= days

                if result:
                    matched.append(resource)

            except Exception as e:
                log.warning(
                    f"Unable to parse creation time '{created_str}' for RocketMQ instance "
                    f"{instance_id} ({name}): {e}")

        log.info(f"Age filter matched {len(matched)} of {len(resources)} resources")
        return matched

@RocketMQ.action_registry.register('mark-for-op')
class RocketMQMarkForOpAction(HuaweiCloudBaseAction):
    """
    Add a "mark-for-operation" tag to RocketMQ instances.

    This action is used to mark resources so that other policies (using the `marked-for-op` filter)
    can identify and execute at a future time.
    It creates a tag on the resource with a value containing the specified operation (`op`)
    and execution timestamp.

    :example:
    Mark RocketMQ instances created over 90 days ago to be deleted in 7 days:

    .. code-block:: yaml

        policies:
          - name: mark-old-rocketmq-for-deletion
            resource: huaweicloud.reliabilitys
            filters:
              - type: age
                days: 90
                op: gt
            actions:
              - type: mark-for-op          # Action type
                op: delete                  # Operation to mark ('delete', 'stop', 'restart')
                days: 7                     # Delay execution days (from now)
                # hours: 0                  # (Optional) Delay execution hours (from now)
                tag: custodian_cleanup      # Tag key (should match filter's tag)
    """
    # Define the input schema for this action
    schema = type_schema(
        'mark-for-op',  # Action type name
        # Operation type to mark
        op={'enum': ['delete', 'stop', 'restart']},
        # Delay execution days (from current time)
        days={'type': 'number', 'minimum': 0, 'default': 0},
        # Delay execution hours (from current time)
        hours={'type': 'number', 'minimum': 0, 'default': 0},
        # Tag key, default is 'mark-for-op-custodian'
        tag={'type': 'string', 'default': 'mark-for-op-custodian'},
        # Declare 'op' parameter as required
        required=['op']
    )

    def perform_action(self, resource):
        """
        Perform the mark operation on a single resource.

        :param resource: RocketMQ instance resource dictionary to mark
        :return: None or API response (but typically no specific result)
        """
        # Get parameters from policy definition
        op = self.data.get('op')
        tag_key = self.data.get('tag', 'mark-for-op-custodian')
        days = self.data.get('days', 0)
        hours = self.data.get('hours', 0)

        instance_id = resource.get('instance_id')
        if not instance_id:
            log.error(
                f"Cannot mark RocketMQ resource missing 'instance_id': "
                f"{resource.get('name', 'unknown name')}")
            return None

        # Calculate scheduled execution time (UTC)
        from datetime import datetime, timedelta
        try:
            action_time = datetime.utcnow() + timedelta(days=days, hours=hours)
            # Format timestamp string, must be consistent with TagActionFilter parsing format
            action_time_str = action_time.strftime('%Y/%m/%d %H:%M:%S UTC')
        except OverflowError:
            log.error(
                f"Invalid mark operation timestamp calculation, RocketMQ instance {instance_id} "
                f"(days={days}, hours={hours})")
            return None

        # Build tag value, format is "operation_timestamp"
        tag_value = f"{op}@{action_time_str}"  # Use @ as separator, clearer

        # Call internal method to create tag
        self._create_or_update_tag(resource, tag_key, tag_value)

        return None  # Typically mark operations don't return specific results

    def _create_or_update_tag(self, resource, key, value):
        """
        Create or update a tag for the specified resource.

        :param resource: Target resource dictionary
        :param key: Tag key
        :param value: Tag value
        """
        instance_id = resource['instance_id']
        instance_name = resource.get('name', 'unknown name')
        # Get HuaweiCloud RocketMQ client
        client = self.manager.get_client()
        # Construct tag entity (using HuaweiCloud SDK's TagEntity class)
        tag_entity = SDKTagEntity(key=key, value=value)
        try:
            # Construct batch create/delete tag request
            request = BatchCreateOrDeleteRocketmqTagRequest()
            request.instance_id = instance_id
            request.body = BatchCreateOrDeleteTagReq()
            # HuaweiCloud batch interface doesn't have a direct 'update' operation.
            # Current implementation assumes 'create' will overwrite existing tags.
            request.body.action = "create"
            request.body.tags = [tag_entity]
            # Call API to perform operation
            client.batch_create_or_delete_rocketmq_tag(request)
            log.info(
                f"Added or updated tag for RocketMQ instance {instance_name} ({instance_id}): "
                f"{key}={value}")
        except exceptions.ClientRequestException as e:
            # Handle API request exceptions
            log.error(
                f"Unable to add or update tag {key} for RocketMQ instance {instance_name} ({instance_id}): "
                f"{e.error_msg} (status code: {e.status_code})"
            )
        except Exception as e:
            # Handle other potential exceptions
            log.error(
                f"Unable to add or update tag {key} for RocketMQ instance {instance_name} ({instance_id}): "
                f"{str(e)}")


@RocketMQ.action_registry.register('auto-tag-user')
class RocketMQAutoTagUser(HuaweiCloudBaseAction):
    """
    (Conceptual) Automatically add creator user tags to RocketMQ instances.

    **Important Note:** This action depends on creator information being included in the resource data
    (e.g., the 'user_name' field here).
    RocketMQ instance information returned by HuaweiCloud API **typically does not directly include
    the creator IAM username**.
    Therefore, the effectiveness of this action depends on whether the `QueryResourceManager`
    or its `augment` method can obtain and populate the `user_name` field through other means
    (e.g., querying the CTS operation log service). If it cannot be obtained, the tag value will be 'unknown'.

    :example:
    Add a 'Creator' tag with the creator's username (if available) to RocketMQ instances
    missing this tag:

    .. code-block:: yaml

        policies:
          - name: tag-rocketmq-creator-if-missing
            resource: huaweicloud.reliabilitys
            filters:
              - "tag:Creator": absent       # Filter instances without 'Creator' tag
            actions:
              - type: auto-tag-user         # Action type
                tag: Creator                # Tag key to add (default is 'CreatorName')
    """
    # Define the input schema for this action
    schema = type_schema(
        'auto-tag-user',  # Action type name
        # Specify the tag key to add, default is 'CreatorName'
        tag={'type': 'string', 'default': 'CreatorName'},
        # The pattern mode for this operation, default is 'resource'
        # Optional 'account' (may indicate the current account executing the policy, but has no practical meaning)
        mode={'type': 'string', 'enum': [
            'resource', 'account'], 'default': 'resource'},
        # If mode is 'resource', specify the resource dictionary key to get the username
        user_key={'type': 'string', 'default': 'creator'},
        # Changed to 'creator' which might be more general
        # Whether to update existing tags, default is True
        update={'type': 'boolean', 'default': True},
        # No required parameters (since all parameters have default values)
        required=[]
    )

    # Permission declaration (if getting user information requires specific permissions)
    # permissions = ('cts:listOperations',) # For example, if CTS logs need to be checked

    def perform_action(self, resource):
        """
        Perform auto-tag user operation on a single resource.

        :param resource: RocketMQ instance resource dictionary to tag
        :return: None
        """
        tag_key = self.data.get('tag', 'CreatorName')
        mode = self.data.get('mode', 'resource')
        user_key = self.data.get('user_key', 'creator')
        update = self.data.get('update', True)

        instance_id = resource.get('instance_id')
        instance_name = resource.get('name', 'unknown name')
        if not instance_id:
            log.error(
                f"Cannot tag RocketMQ resource missing 'instance_id': {instance_name}")
            return None

        # Check if update is needed and if the tag already exists
        if not update and tag_key in [t.get('Key') for t in resource.get('Tags', [])]:
            log.debug(
                f"RocketMQ instance {instance_name} ({instance_id}) already has tag '{tag_key}' "
                f"and updates are not allowed, skipping.")
            return None

        user_name = 'unknown'  # Default value
        if mode == 'resource':
            # Try to get username from resource dictionary
            user_name = resource.get(user_key, 'unknown')
            if user_name == 'unknown':
                # If default 'creator' key not found, also try original code's 'user_name'
                user_name = resource.get('user_name', 'unknown')

                # If still unknown, can consider adding logic to query CTS logs
                if user_name == 'unknown':
                    log.warning(
                        f"Could not find creator information for RocketMQ instance {instance_name} ({instance_id}) "
                        f"(tried keys: '{user_key}', 'user_name'). "
                        f"Using 'unknown'.")
        elif mode == 'account':
            log.warning(
                "'account' mode in RocketMQAutoTagUser not fully implemented.")
            user_name = 'unknown'

        # Reuse RocketMQMarkForOpAction's helper method
        rocketmq_marker = RocketMQMarkForOpAction(self.data, self.manager)
        rocketmq_marker._create_or_update_tag(resource, tag_key, user_name)

        return None

@RocketMQ.action_registry.register('tag')
class RocketMQTag(HuaweiCloudBaseAction):
    """
    Add or update a specified tag on RocketMQ instances.

    This is a generic tag-adding action that allows users to directly specify tag keys and values.
    If a tag with the same key already exists, it will be overwritten by default.

    :example:
    Add an 'Environment=Production' tag to all RocketMQ instances in the production environment:

    .. code-block:: yaml

        policies:
          - name: tag-rocketmq-production-env
            resource: huaweicloud.reliabilitys
            # May need filters to identify production instances
            # filters:
            #   - ...
            actions:
              - type: tag                   # Action type
                key: Environment            # Tag key to add/update
                value: Production           # Tag value to set
    """
    # Define the input schema for this action
    schema = type_schema(
        'tag',  # Action type name
        key={'type': 'string'},  # Tag key
        value={'type': 'string'},  # Tag value
        # Declare 'key' and 'value' parameters as required
        required=['key', 'value']
    )

    def perform_action(self, resource):
        """
        Perform add/update tag operation on a single resource.

        :param resource: RocketMQ instance resource dictionary to tag
        :return: None
        """
        key = self.data.get('key')
        value = self.data.get('value')

        instance_id = resource.get('instance_id')
        if not instance_id:
            log.error(
                f"Cannot tag RocketMQ resource missing 'instance_id': "
                f"{resource.get('name', 'unknown name')}")
            return None

        # Reuse RocketMQMarkForOpAction's helper method
        rocketmq_marker = RocketMQMarkForOpAction(self.data, self.manager)
        rocketmq_marker._create_or_update_tag(resource, key, value)

        return None


@RocketMQ.action_registry.register('remove-tag')
class RocketMQRemoveTag(HuaweiCloudBaseAction):
    """
    Remove one or more specified tags from RocketMQ instances.

    Allows users to remove tags from instances based on tag keys.

    :example:
    Remove the 'Temporary' tag from all RocketMQ instances:

    .. code-block:: yaml

        policies:
          - name: remove-temp-rocketmq-tags
            resource: huaweicloud.reliabilitys
            # Can add filters to ensure only operating on instances with this tag
            filters:
              - "tag:Temporary": present
            actions:
              - type: remove-tag            # Action type
                key: Temporary              # Tag key to remove (required)
              # Can specify multiple keys to remove multiple tags at once
              # - type: remove-tag
              #   keys: ["Temp1", "Temp2"]
    """
    # Define the input schema for this action
    schema = type_schema(
        'remove-tag',  # Action type name
        # Can specify a single key or a list of keys
        key={'type': 'string'},  # Single tag key to remove
        # List of tag keys to remove
        keys={'type': 'array', 'items': {'type': 'string'}},
        # required=['keys'] # At least need key or keys
        # Better approach would be using oneOf or anyOf, but Custodian's schema might not support
        # Temporarily allow key and keys optional, handle in code
    )

    def perform_action(self, resource):
        """
        Perform remove tag operation on a single resource.

        :param resource: RocketMQ instance resource dictionary to remove tags from
        :return: None
        """
        # Get list of tag keys to remove
        tags_to_remove = self.data.get('keys', [])
        single_key = self.data.get('key')
        if single_key and single_key not in tags_to_remove:
            tags_to_remove.append(single_key)

        if not tags_to_remove:
            log.warning(
                "No tag keys specified (key or keys) in remove-tag operation.")
            return None

        instance_id = resource.get('instance_id')
        instance_name = resource.get('name', 'unknown name')
        if not instance_id:
            log.error(
                f"Cannot remove tags, RocketMQ resource missing 'instance_id': {instance_name}")
            return None

        # Check for tags that actually exist on the instance, avoid trying to delete non-existent tags
        # (API might allow it, but would cause unnecessary calls)
        current_tags = {t.get('Key') for t in resource.get('Tags', [])}
        keys_that_exist = [k for k in tags_to_remove if k in current_tags]

        if not keys_that_exist:
            log.debug(
                f"RocketMQ instance {instance_name} ({instance_id}) has none of the tags to remove: "
                f"{tags_to_remove}")
            return None

        # Call internal method to remove tags
        self._remove_tags_internal(resource, keys_that_exist)

        return None

    def _remove_tags_internal(self, resource, keys_to_delete):
        """
        Internal helper method to call API to remove the specified list of tag keys.

        :param resource: Target resource dictionary
        :param keys_to_delete: List of tag key strings to delete
        """
        instance_id = resource['instance_id']
        instance_name = resource.get('name', 'unknown name')
        client = self.manager.get_client()

        # Create TagEntity for each key to delete (only provide key)
        tag_entities = [SDKTagEntity(key=k) for k in keys_to_delete]

        try:
            # Construct batch delete tags request
            request = BatchCreateOrDeleteRocketmqTagRequest()
            request.instance_id = instance_id
            request.body = BatchCreateOrDeleteTagReq()
            request.body.action = "delete"  # Specify operation as delete
            request.body.tags = tag_entities  # Include tags to delete
            # Call API to perform deletion
            client.batch_create_or_delete_rocketmq_tag(request)
            log.info(
                f"Removed tags from RocketMQ instance {instance_name} ({instance_id}): "
                f"{keys_to_delete}")
        except exceptions.ClientRequestException as e:
            log.error(
                f"Unable to remove tags {keys_to_delete} from RocketMQ instance {instance_name} ({instance_id}): "
                f"{e.error_msg} (status code: {e.status_code})"
            )
        except Exception as e:
            log.error(
                f"Unable to remove tags {keys_to_delete} from RocketMQ instance {instance_name} ({instance_id}): "
                f"{str(e)}")


@RocketMQ.action_registry.register('rename-tag')
class RocketMQRenameTag(HuaweiCloudBaseAction):
    """
    Rename a tag key on RocketMQ instances.

    This operation is actually "copy and delete":
    1. Read the value of the tag with the old key (`old_key`).
    2. Create a new tag with the new key (`new_key`) and the old value.
    3. Delete the tag with the old key (`old_key`).

    :example:
    Rename the 'Env' tag to 'Environment' on all instances:

    .. code-block:: yaml

        policies:
          - name: standardize-env-tag-rocketmq
            resource: huaweicloud.reliabilitys
            filters:
              - "tag:Env": present          # Ensure only operating on instances with 'Env' tag
            actions:
              - type: rename-tag            # Action type
                old_key: Env                # Old tag key
                new_key: Environment        # New tag key
    """
    # Define the input schema for this action
    schema = type_schema(
        'rename-tag',  # Action type name
        old_key={'type': 'string'},  # Old tag key
        new_key={'type': 'string'},  # New tag key
        # Declare 'old_key' and 'new_key' parameters as required
        required=['old_key', 'new_key']
    )

    def perform_action(self, resource):
        """
        Perform rename tag operation on a single resource.

        :param resource: RocketMQ instance resource dictionary to rename tag on
        :return: None
        """
        old_key = self.data.get('old_key')
        new_key = self.data.get('new_key')

        if old_key == new_key:
            log.warning(
                f"Old tag key '{old_key}' and new tag key '{new_key}' "
                f"are the same, no need to rename.")
            return None

        instance_id = resource.get('instance_id')
        instance_name = resource.get('name', 'unknown name')
        if not instance_id:
            log.error(
                f"Cannot rename tag, RocketMQ resource missing 'instance_id': {instance_name}")
            return None

        # Find old tag value
        old_value = None
        if 'Tags' in resource:
            for tag in resource['Tags']:
                if tag.get('Key') == old_key:
                    old_value = tag.get('Value')
                    break

        # If old tag doesn't exist, no operation
        if old_value is None:
            log.info(
                f"Tag '{old_key}' not found on RocketMQ instance {instance_name} ({instance_id}), "
                f"skipping rename.")
            return None

        # Check if new tag already exists
        if 'Tags' in resource:
            for tag in resource['Tags']:
                if tag.get('Key') == new_key:
                    log.warning(
                        f"Target tag key '{new_key}' already exists on "
                        f"RocketMQ instance {instance_name} ({instance_id}). Rename operation will "
                        f"overwrite its existing value (if continued).")
                    break

        # 1. Add new tag (with old value)
        rocketmq_marker = RocketMQMarkForOpAction(self.data, self.manager)
        rocketmq_marker._create_or_update_tag(resource, new_key, old_value)

        # 2. Remove old tag
        remover = RocketMQRemoveTag(self.data, self.manager)
        remover._remove_tags_internal(resource, [old_key])

        log.info(
            f"Renamed tag '{old_key}' to '{new_key}' on RocketMQ instance "
            f"{instance_name} ({instance_id})")

        return None
