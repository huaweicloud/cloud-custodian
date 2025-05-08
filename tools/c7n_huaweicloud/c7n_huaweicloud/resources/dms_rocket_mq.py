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
                tags.append({'Key': tag_entity.get('key'), 'Value': tag_entity.get('value')})
            # Add the converted tag list to the resource dictionary with the key 'Tags'
            r['Tags'] = tags
        return resources


@RocketMQ.filter_registry.register('security-group')
class RocketMQSecurityGroupFilter(SecurityGroupFilter):
    """
    Filter RocketMQ instances based on associated security groups.
    
    Allows users to filter instances based on properties of the security groups (such as name, ID)
    used by the RocketMQ instance.
    Inherits from the generic `SecurityGroupFilter`.
    
    :example:
    Find RocketMQ instances using a security group named 'allow-public':
    
    .. code-block:: yaml

        policies:
          - name: rocketmq-with-public-sg
            resource: huaweicloud.reliabilitys
            filters:
              - type: security-group        # Filter type
                key: name                   # Security group property to match (e.g., name, Id)
                value: allow-public         # Value to match
    """
    # Specify the field name in the RocketMQ resource dictionary that contains the security group ID
    RelatedIdsExpression = "security_group_id"


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
        threshold_date = now - timedelta(days=days, hours=hours, minutes=minutes)
        
        log.debug(f"Age filter: now={now}, threshold_date={threshold_date}, op={op}, days={days}")
        
        # Filter resources
        matched = []
        for resource in resources:
            created_str = resource.get(self.date_attribute)
            if not created_str:
                log.debug(f"Resource {resource.get('instance_id', 'unknown')} has no {self.date_attribute}")
                continue
                
            # Convert creation time
            try:
                # If it's a millisecond timestamp, convert to seconds then create datetime
                if isinstance(created_str, (int, float)) or (isinstance(created_str, str) and created_str.isdigit()):
                    try:
                        # Ensure conversion to integer
                        timestamp_ms = int(float(created_str))
                        timestamp_s = timestamp_ms / 1000.0
                        log.debug(f"Converting timestamp: {created_str} ms -> {timestamp_s} s")
                        # Create datetime object from timestamp (UTC)
                        created_date = datetime.utcfromtimestamp(timestamp_s).replace(tzinfo=tzutc())
                        log.debug(f"Converted to datetime: {created_date}")
                    except (ValueError, TypeError, OverflowError) as e:
                        log.debug(
                            f"Unable to parse value '{created_str}' as millisecond timestamp: {e}")
                        # If parsing fails, continue trying with dateutil.parser
                        created_date = parse(str(created_str))
                else:
                    # If not a pure number or failed to parse millisecond timestamp, try using dateutil.parser to parse generic time string
                    created_date = parse(str(created_str))
                
                # Ensure datetime has timezone information
                if not created_date.tzinfo:
                    created_date = created_date.replace(tzinfo=tzutc())
                
                log.debug(f"Resource {resource.get('instance_id', 'unknown')} created_date={created_date}")
                    
                # Compare dates
                result = operator(created_date, threshold_date)
                log.debug(f"Compare: {created_date} {op} {threshold_date} = {result}")
                
                if result:
                    matched.append(resource)
            except Exception as e:
                log.warning(
                    f"Unable to parse creation time '{created_str}' for RocketMQ instance "
                    f"{resource.get('instance_id', 'unknown ID')}: {e}")
                
        return matched


@RocketMQ.filter_registry.register('list-item')
class RocketMQListItemFilter(ListItemFilter):
    """
    Filter items in resource attributes lists.
    
    This filter allows checking values in a key of the resource dictionary (which must be a list)
    and filtering based on the items in that list.
    For example, it can check if an instance is deployed in a specific availability zone,
    or if it contains a specific tag.
    Inherits from core `ListItemFilter`.
    
    :example:
    Find RocketMQ instances deployed in 'cn-north-4a' or 'cn-north-4b' availability zones:
    
    .. code-block:: yaml

        policies:
          - name: rocketmq-multi-az
            resource: huaweicloud.reliabilitys
            filters:
              - type: list-item             # Filter type
                key: available_zones        # Resource property key name (value should be a list)
                # key_path: "[].name"       # (Optional) JMESPath expression to extract value
                                            # If list items are simple types, key_path is not needed
                op: in                      # Comparison operator (in, not-in, contains, eq, ...)
                value: ["cn-north-4a", "cn-north-4b"] # Value or values to compare against

    Examples of list properties that can be filtered (depending on fields returned by the API):
    - `available_zones`: list of availability zones (usually a list of strings)
    - `tags`: list of tags (usually a list of dictionaries, requires using `key_path`, e.g.,
      `[?key=='Environment'].value | [0]`, or using `Tags` after `augment`)
    """
    # Define the input schema for this filter
    schema = type_schema(
        'list-item',  # Filter type name
        # --- The following parameters are inherited from ListItemFilter ---
        # count: number of matching items
        count={'type': 'integer', 'minimum': 0},
        # count_op: comparison operator for count (eq, ne, gt, ge, lt, le)
        count_op={'enum': list(OPERATORS.keys())},
        # op: comparison operator for list item values
        op={'enum': list(OPERATORS.keys())},
        # value: value to compare against, can be a single value or a list
        value={'oneOf': [
            {'type': 'array'},
            {'type': 'string'},
            {'type': 'boolean'},
            {'type': 'number'},
            {'type': 'object'}
        ]},
        # key: resource property key name to check, value must be a list
        key={'oneOf': [
            {'type': 'string'},
            {'type': 'integer', 'minimum': 0},  # Key can also be an integer (if resource dictionary key is an integer)
            {'type': 'array', 'items': {'type': 'string'}}  # Or list of path
        ]},
        # key_path: (Optional) JMESPath expression to extract comparison value from list items
        key_path={'type': 'string'},
        # Declare 'key' parameter as required
        required=['key']
    )
    
    def process(self, resources, event=None):
        """
        Override list item filtering method to handle string list items
        
        :param resources: List of resources to filter
        :param event: Optional event context
        :return: Filtered resource list
        """
        result = []
        # If no attrs attribute (sub-filters) is defined, use simple check
        if not self.data.get('attrs', []):
            # For simple cases, use value/op to compare directly
            if 'value' in self.data and 'op' in self.data:
                op = OPERATORS[self.data.get('op', 'eq')]
                value = self.data.get('value')
                
                for r in resources:
                    list_values = self.get_item_values(r)
                    if not list_values:
                        if self.check_count(0):
                            result.append(r)
                        continue
                    
                    if not isinstance(list_values, list):
                        item_type = type(list_values)
                        raise ValueError(
                            f"list-item filter value {self.data['key']} is {item_type}, not a list")
                    
                    # Check each item in the list
                    matches = []
                    for item in list_values:
                        if op(item, value):
                            matches.append(item)
                    
                    # Decide whether to keep the resource based on count check or existence of matches
                    if 'count' in self.data:
                        if self.check_count(len(matches)):
                            result.append(r)
                    elif matches:
                        result.append(r)
                return result
                
        # Use original parent class method for complex cases
        frm = ListItemResourceManager(
            self.manager.ctx, data={'filters': self.data.get('attrs', [])})
        
        for r in resources:
            list_values = self.get_item_values(r)
            if not list_values:
                if self.check_count(0):
                    result.append(r)
                continue
                
            if not isinstance(list_values, list):
                item_type = type(list_values)
                raise ValueError(
                    f"list-item filter value {self.data['key']} is {item_type}, not a list")
            
            # Handle string and other simple type list items
            wrapped_values = []
            for idx, val in enumerate(list_values):
                if isinstance(val, (str, int, float, bool)):
                    # Wrap simple types in a dictionary
                    wrapped_values.append({'value': val, 'c7n:_id': idx})
                else:
                    # If it's a dictionary type, add ID
                    val_copy = val.copy() if hasattr(val, 'copy') else val
                    if isinstance(val_copy, dict):
                        val_copy['c7n:_id'] = idx
                        wrapped_values.append(val_copy)
                    else:
                        # Other types also wrapped as dictionary
                        wrapped_values.append({'value': val, 'c7n:_id': idx})
            
            # Process wrapped values with sub-filters
            list_resources = frm.filter_resources(wrapped_values, event)
            
            # Extract matched indices
            matched_indices = []
            for matched in list_resources:
                if 'c7n:_id' in matched:
                    matched_indices.append(matched['c7n:_id'])
            
            # Process results
            if 'count' in self.data:
                if self.check_count(len(list_resources)):
                    result.append(r)
            elif list_resources:
                annotations = [
                    f'{self.data.get("key", self.type)}[{str(i)}]'
                    for i in matched_indices
                ]
                if self.annotate_items:
                    r.setdefault(self.item_annotation_key, [])
                    r[self.item_annotation_key].extend(annotations)
                result.append(r)
                
        return result


@RocketMQ.filter_registry.register('marked-for-op')
class RocketMQMarkedForOpFilter(Filter):
    """
    Filter RocketMQ instances based on specific "marked-for-operation" tags.
    
    This filter is used to find instances that have been marked by a `mark-for-op` action
    to execute a specific operation (like delete, stop) at a future time.
    It checks the specified tag key (`tag`), parses the operation type and scheduled
    execution time from the tag value, and compares it with the current time.
    
    :example:
    Find all RocketMQ instances marked for deletion with the tag key 'custodian_cleanup':
    
    .. code-block:: yaml

        policies:
          - name: find-rocketmq-marked-for-deletion
            resource: huaweicloud.reliabilitys
            filters:
              - type: marked-for-op          # Filter type
                op: delete                  # Operation type to find ('delete', 'stop', 'restart')
                tag: custodian_cleanup      # Tag key used for marking operations
                # skew: 1                   # (Optional) Time offset in days
                # skew_hours: 2             # (Optional) Time offset in hours
    """
    # Define the input schema for this filter
    schema = type_schema(
        'marked-for-op',  # Filter type name
        # Operation type to find
        op={'type': 'string', 'enum': ['delete', 'stop', 'restart']},
        # Tag key used for marking operations, default is 'mark-for-op-custodian'
        tag={'type': 'string', 'default': 'mark-for-op-custodian'},
        # (Optional) Time offset in days, allows matching N days early, default is 0
        skew={'type': 'number', 'default': 0},
        # (Optional) Time offset in hours, allows matching N hours early, default is 0
        skew_hours={'type': 'number', 'default': 0},
        # Timezone, default is 'utc'
        tz={'type': 'string', 'default': 'utc'},
    )
    schema_alias = True
    DEFAULT_TAG = "mark-for-op-custodian"

    def __init__(self, data, manager=None):
        super(RocketMQMarkedForOpFilter, self).__init__(data, manager)
        self.tag = self.data.get('tag', self.DEFAULT_TAG)
        self.op = self.data.get('op')
        self.skew = self.data.get('skew', 0)
        self.skew_hours = self.data.get('skew_hours', 0)
        from dateutil import tz as tzutil
        from c7n.filters.offhours import Time
        self.tz = tzutil.gettz(Time.TZ_ALIASES.get(self.data.get('tz', 'utc')))

    def process(self, resources, event=None):
        results = []
        for resource in resources:
            tags = self._get_tags_from_resource(resource)
            if not tags:
                continue

            tag_value = tags.get(self.tag)
            if not tag_value:
                continue

            if self._process_tag_value(tag_value):
                results.append(resource)

        return results

    def _process_tag_value(self, tag_value):
        """Process tag value to determine if it meets the filter conditions"""
        if not tag_value:
            return False

        # Process RocketMQMarkForOpAction created value format "operation@timestamp"
        if '@' in tag_value:
            action, action_date_str = tag_value.strip().split('@', 1)
        # Compatible with old format "operation_timestamp"
        elif '_' in tag_value:
            action, action_date_str = tag_value.strip().split('_', 1)
        else:
            return False
        if action != self.op:
            return False

        try:
            # Try to directly parse the standard timestamp format generated by RocketMQMarkForOpAction
            # '%Y/%m/%d %H:%M:%S UTC'
            from dateutil.parser import parse
            action_date = parse(action_date_str)
        except Exception:
            # If standard parsing fails, try using old format conversion logic
            try:
                # Old time format conversion logic
                modified_date_str = self._replace_nth_regex(action_date_str, "-", " ", 3)
                modified_date_str = self._replace_nth_regex(modified_date_str, "-", ":", 3)
                modified_date_str = self._replace_nth_regex(modified_date_str, "-", " ", 3)

                action_date = parse(modified_date_str)
            except Exception as nested_e:
                self.log.warning(f"Unable to parse tag value: {tag_value}, error: {str(nested_e)}")
                return False

        from datetime import datetime, timedelta
        if action_date.tzinfo:
            # If action_date has timezone, convert to specified timezone
            action_date = action_date.astimezone(self.tz)
            current_date = datetime.now(tz=self.tz)
        else:
            current_date = datetime.now()
        return current_date >= (
                action_date - timedelta(days=self.skew, hours=self.skew_hours))

    def _replace_nth_regex(self, s, old, new, n):
        """Replace the nth occurrence of old with new in string s"""
        import re
        pattern = re.compile(re.escape(old))
        matches = list(pattern.finditer(s))
        if len(matches) < n:
            return s
        match = matches[n - 1]
        return s[:match.start()] + new + s[match.end():]

    def _get_tags_from_resource(self, resource):
        """Get tag dictionary from resource"""
        try:
            tags = {}
            # Process original Tags list, convert to dictionary form
            if 'Tags' in resource:
                for tag in resource.get('Tags', []):
                    if isinstance(tag, dict) and 'Key' in tag and 'Value' in tag:
                        tags[tag['Key']] = tag['Value']
            # Process original tags list, various possible formats
            elif 'tags' in resource:
                raw_tags = resource['tags']
                if isinstance(raw_tags, dict):
                    tags = raw_tags
                elif isinstance(raw_tags, list):
                    if all(isinstance(item, dict) and 'key' in item and 'value' in item
                           for item in raw_tags):
                        # Compatible with HuaweiCloud specific [{key: k1, value: v1}] format
                        for item in raw_tags:
                            tags[item['key']] = item['value']
                    elif all(isinstance(item, dict) and len(item) == 1 for item in raw_tags):
                        # Compatible with [{k1: v1}, {k2: v2}] format
                        for item in raw_tags:
                            key, value = list(item.items())[0]
                            tags[key] = value
            return tags
        except Exception as e:
            self.log.error(f"Failed to parse resource tags: {str(e)}")
            return {}


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
        mode={'type': 'string', 'enum': ['resource', 'account'], 'default': 'resource'},
        # If mode is 'resource', specify the resource dictionary key to get the username
        user_key={'type': 'string', 'default': 'creator'},
        # Changed to 'creator' which might be more general
        # Whether to update existing tags, default is True
        update={'type': 'boolean', 'default': True},
        required=[]  # No required parameters (since all parameters have default values)
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
            log.error(f"Cannot tag RocketMQ resource missing 'instance_id': {instance_name}")
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
            log.warning("'account' mode in RocketMQAutoTagUser not fully implemented.")
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
        keys={'type': 'array', 'items': {'type': 'string'}},  # List of tag keys to remove
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
            log.warning("No tag keys specified (key or keys) in remove-tag operation.")
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
            log.error(f"Cannot delete RocketMQ resource missing 'instance_id': {instance_name}")
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
            log.error(f"Unable to delete RocketMQ instance {instance_name} ({instance_id}): {str(e)}")
            return None
