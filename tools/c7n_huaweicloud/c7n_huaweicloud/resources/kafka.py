# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.filters.vpc import SecurityGroupFilter
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from dateutil.parser import parse
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkkafka.v2.model import (
    DeleteInstanceRequest,
    BatchCreateOrDeleteKafkaTagRequest,
    BatchCreateOrDeleteTagReq,
    ModifyInstanceConfigsRequest,
    ModifyInstanceConfigsReq,
    ShowInstanceConfigsRequest,
)
from huaweicloudsdkkafka.v2.model import TagEntity as SDKTagEntity

from c7n.filters import ValueFilter, AgeFilter, Filter, OPERATORS
from c7n.filters.core import ListItemFilter
from c7n.utils import type_schema, local_session

log = logging.getLogger("custodian.huaweicloud.resources.kafka")


# Define a local TagEntity class to simplify tag operations.
# Note: HuaweiCloud SDK also provides TagEntity, this might be for specific scenarios or
# compatibility.
class TagEntity:
    """Simple tag structure for representing key-value pairs"""

    def __init__(self, key, value=None):
        """
        Initialize tag entity.
        :param key: Tag key (required)
        :param value: Tag value (optional)
        """
        self.key = key
        self.value = value


@resources.register('kafka')
class Kafka(QueryResourceManager):
    """HuaweiCloud distributed message service Kafka (DMS Kafka) instance resource manager.

    This class is responsible for discovering, filtering, and managing Kafka instance resources on
    HuaweiCloud.
    It inherits from QueryResourceManager, utilizing its capabilities to query and process resource
    lists.

    :example:
    Define a simple policy to get all Kafka instances:

    .. code-block:: yaml

        policies:
          - name: kafka-instances-discovery # Policy name
            resource: huaweicloud.kafka      # Specify resource type as HuaweiCloud Kafka
    """

    class resource_type(TypeInfo):
        """Define Kafka resource metadata and type information"""
        service = 'kafka'  # Specify corresponding HuaweiCloud service name
        # Specify API operation, result list key, and pagination parameter(s) for enumerating
        # resources
        # 'list_instances' is the API method name
        # 'instances' is the field name in the response containing the instance list
        # 'offset' is the parameter name for pagination
        enum_spec = ('list_instances', 'instances',
                     'offset', 10)
        id = 'instance_id'  # Specify resource unique identifier field name
        name = 'name'  # Specify resource name field name
        date = 'created_at'  # Specify field name for resource creation time
        tag = True  # Indicate that this resource supports tags
        tag_resource_type = 'kafka'  # Specify resource type for querying tags

    def augment(self, resources):
        """
        Enhance original resource data obtained from API.

        This method is mainly used to convert HuaweiCloud API returned tag list format (usually a
        dictionary list containing 'key' and 'value' fields)
        to AWS compatible format (dictionary list containing 'Key' and 'Value' fields) used by
        Cloud Custodian internally.
        This improves consistency across cloud provider strategies.

        :param resources: Original resource dictionary list obtained from API
        :return: Enhanced resource dictionary list, where tags are converted to AWS compatible
        format under 'Tags' key
        """
        for r in resources:
            # Check if 'tags' key exists in original resource dictionary
            if 'tags' not in r:
                continue  # If no tags, skip this resource
            tags = []
            # Iterate through original tag list
            for tag_entity in r['tags']:
                # Convert each tag to {'Key': ..., 'Value': ...} format
                tags.append({'Key': tag_entity.get('key'), 'Value': tag_entity.get('value')})
            # Add converted tag list to resource dictionary, key named 'Tags'
            r['Tags'] = tags
        return resources


@Kafka.filter_registry.register('security-group')
class KafkaSecurityGroupFilter(SecurityGroupFilter):
    """
    Filter Kafka instances based on associated security groups.

    Allow users to filter instances based on attributes of security groups used by Kafka instances
    (such as name, ID).
    Inherit from generic `SecurityGroupFilter`.

    :example:
    Find Kafka instances using a security group named 'allow-public':

    .. code-block:: yaml

        policies:
          - name: kafka-with-public-sg
            resource: huaweicloud.kafka
            filters:
              - type: security-group        # Filter type
                key: name              # Security group attribute to match (e.g., name, Id)
                value: allow-public         # Value to match
    """
    # Specify Kafka resource dictionary field name containing security group ID
    RelatedIdsExpression = "security_group_id"


@Kafka.filter_registry.register('age')
class KafkaAgeFilter(AgeFilter):
    """
    Filter Kafka instances based on their creation time (age).

    Allow users to filter out instances created earlier or later than specified time.
    Inherit from generic `AgeFilter`.

    :example:
    Find Kafka instances created more than 30 days ago:

    .. code-block:: yaml

        policies:
          - name: kafka-older-than-30-days
            resource: huaweicloud.kafka
            filters:
              - type: age                   # Filter type
                days: 30                    # Specify days
                op: gt                      # Operation, gt means 'greater than' (older than)
                                            # Other available symbols: lt (younger than), ge, le
    """
    # Define this filter's input pattern (schema)
    schema = type_schema(
        'age',  # Filter type name
        # Define comparison operation, referencing generic filter definition
        op={'$ref': '#/definitions/filters_common/comparison_operators'},
        # Define time unit parameter
        days={'type': 'number'},  # Days
        hours={'type': 'number'},  # Hours
        minutes={'type': 'number'}  # Minutes
    )

    # Specify field name in resource dictionary representing creation time
    date_attribute = "created_at"

    def get_resource_date(self, resource):
        """
        Get and parse creation time from resource dictionary.

        :param resource: Single Kafka instance resource dictionary
        :return: Parsed datetime object, return None if unable to get or parse
        """
        from datetime import datetime
        # Check if specified date attribute exists in resource dictionary
        date_value = resource.get(self.date_attribute)
        if not date_value:
            return None

        # Try to parse value as milliseconds timestamp
        if isinstance(date_value, (str, int)) and str(date_value).isdigit():
            try:
                # Assume it's milliseconds timestamp, convert to seconds
                timestamp_ms = int(date_value)
                timestamp_s = timestamp_ms / 1000.0
                # Create datetime object from timestamp (UTC)
                return datetime.utcfromtimestamp(timestamp_s)
            except (ValueError, TypeError, OverflowError) as e:
                log.debug(
                    f"Failed to parse value '{date_value}' "
                    f"as milliseconds timestamp: {e}")
                # If parsing fails, continue to try using dateutil.parser

        # If not pure digits or parsing as milliseconds timestamp fails, try using dateutil.parser
        # for generic time string
        try:
            return parse(str(date_value))  # Ensure input is string
        except Exception as e:
            # If parsing fails, record error and return None
            log.warning(
                f"Failed to parse creation time '{date_value}' for Kafka instance "
                f"{resource.get('instance_id', 'Unknown ID')} : {e}")
            return None


@Kafka.filter_registry.register('list-item')
class KafkaListItemFilter(ListItemFilter):
    """
    Filter list items in resource attributes.

    This filter allows checking value of a key in resource dictionary (must be list) and filtering
    based on items in the list.
    For example, can check if instance is deployed in specific availability zone, or if it contains
    specific tags.
    Inherit from core `ListItemFilter`.

    :example:
    Find Kafka instances deployed in 'cn-north-4a' or 'cn-north-4b' availability zones:

    .. code-block:: yaml

        policies:
          - name: kafka-multi-az
            resource: huaweicloud.kafka
            filters:
              - type: list-item             # Filter type
                key: available_zones        # Resource attribute key name (value should be list)
                # key_path: "[].name"       # (Optional) JMESPath expression for extracting value
                                            # If list item is simple type, key_path is not needed
                op: in                      # Comparison operator (in, not-in, contains, eq, ...)
                value: ["cn-north-4a", "cn-north-4b"] # Values or value list to compare

    List attribute examples for filtering (depends on API returned field):
    - `available_zones`: Availability zone list (usually string list)
    - `tags`: Tag list (usually dictionary list, need `key_path` like
      `[?key=='Environment'].value | [0]` or use `Tags` after `augment`)
    - `ipv6_connect_addresses`: IPv6 connection address list
    """
    # Define this filter's input pattern (schema)
    schema = type_schema(
        'list-item',  # Filter type name
        # --- Following parameters inherit from ListItemFilter ---
        # count: Number of matching items
        count={'type': 'integer', 'minimum': 0},
        # count_op: Comparison operator for count (eq, ne, gt, ge, lt, le)
        count_op={'enum': list(OPERATORS.keys())},
        # op: Comparison operator for list item values
        op={'enum': list(OPERATORS.keys())},
        # value: Value for comparison, can be single value or list
        value={'oneOf': [
            {'type': 'array'},
            {'type': 'string'},
            {'type': 'boolean'},
            {'type': 'number'},
            {'type': 'object'}
        ]},
        # key: Resource attribute key name to check, value must be list
        key={'oneOf': [
            {'type': 'string'},
            {'type': 'integer', 'minimum': 0},
            # Key can also be integer (if resource dictionary key is integer)
            {'type': 'array', 'items': {'type': 'string'}}  # Or path list
        ]},
        # key_path: (Optional) JMESPath expression, used to extract comparison value from list item
        key_path={'type': 'string'},
        # Declare 'key' parameter is required
        required=['key']
    )

    def process(self, resources, event=None):
        """
        Process resource list, filter list type attribute items.

        Override ListItemFilter's process method to handle string list processing issues.

        :param resources: Resource list to filter
        :param event: Optional event context
        :return: Filtered resource list
        """
        # Get parameters from filter configuration
        key = self.data.get('key')
        key_path = self.data.get('key_path')
        count = self.data.get('count')
        count_op = self.data.get('count_op')

        # Get comparison operator and comparison value
        op_name = self.data.get('op', 'in')
        op = OPERATORS.get(op_name)
        value = self.data.get('value')

        # Initialize result list
        results = []

        # Process each resource
        for resource in resources:
            # Get list attribute to check
            if isinstance(key, list):
                list_values = self.get_resource_value_list(resource, key)
            else:
                list_values = resource.get(key, [])

            if not list_values:
                continue

            # Track matching list item count
            matches = 0

            # Iterate through each item in list
            for list_value in list_values:
                # Get value for comparison
                if key_path:
                    import jmespath
                    # If key_path is specified, try to extract from list item
                    if isinstance(list_value, dict):
                        compare_value = jmespath.search(key_path, list_value)
                    else:
                        # If list item is not dictionary and key_path is specified,
                        # it might not be correctly extracted
                        # In this case, record warning and skip
                        self.log.warning(
                            f"Specified key_path '{key_path}', but list item is not dictionary: "
                            f"{list_value}")
                        continue
                else:
                    # Otherwise, directly use list item itself
                    compare_value = list_value

                # Execute comparison operation, handling based on operator and value type
                match = False

                # Special handling for eq and ne operators when value is list
                if op_name == 'eq' and isinstance(value, list):
                    # When op is eq and value is list, check if compare_value is in value list
                    match = compare_value in value
                elif op_name == 'ne' and isinstance(value, list):
                    # When op is ne and value is list, check if compare_value is not in value list
                    match = compare_value not in value
                # For comparison operators requiring single value comparison when value is list
                elif op_name in ('gt', 'lt', 'ge', 'le') and isinstance(value, list):
                    self.log.warning(
                        f"Operator '{op_name}' is not suitable for comparing with list value "
                        f"{value}, this comparison will be skipped")
                    match = False
                # Normal operator execution
                else:
                    match = op(compare_value, value)

                if match:
                    matches += 1

            # If count is specified, check if matching count meets condition
            if count is not None and count_op:
                count_matched = OPERATORS[count_op](matches, count)
                if count_matched:
                    results.append(resource)
            # Otherwise, if at least one matching item, include this resource
            elif matches > 0:
                results.append(resource)

        return results


@Kafka.filter_registry.register('config-compliance')
class KafkaConfigComplianceFilter(ValueFilter):
    """
    Check if specific configuration item of Kafka instance meets expected value.

    This filter calls HuaweiCloud API to query specified Kafka instance configuration information,
    then compares actual value of configuration item (`key`) with expected value (`value`).

    :example:
    Find Kafka instances where 'auto.create.topics.enable' configuration is
    not set to 'false':

    .. code-block:: yaml

        policies:
          - name: kafka-with-auto-topic-creation
            resource: huaweicloud.kafka
            filters:
              - type: config-compliance      # Filter type
                key: auto.create.topics.enable # Kafka configuration item name to check
                op: ne                      # Comparison operator (ne means 'not equal')
                value: false                # Expected value
    """
    # Define this filter's input pattern (schema)
    schema = type_schema(
        'config-compliance',  # Filter type name
        rinherit=ValueFilter.schema,
        # Following attributes extend ValueFilter.schema
        key={'type': 'string'},  # Kafka configuration item name to check
        op={'enum': list(OPERATORS.keys()), 'default': 'eq'},
        # Comparison operator, default is 'eq' (equal)
        # Expected value, can be string, boolean, or number
        value={'oneOf': [
            {'type': 'string'},
            {'type': 'boolean'},
            {'type': 'number'}
        ]},
        # Declare 'key' and 'value' parameters are required
        required=['key', 'value']
    )
    schema_alias = True

    def get_permissions(self):
        return ('kafka:showInstanceConfigs',)

    def process(self, resources, event=None):
        # Initialize base configuration
        key = self.data.get('key')
        value = self.data.get('value')

        # Get HuaweiCloud Kafka service client
        client = local_session(self.manager.session_factory).client('kafka')

        for resource in resources:
            instance_id = resource.get('instance_id')
            if not instance_id:
                log.warning(
                    f"Skipping Kafka resource missing 'instance_id': "
                    f"{resource.get('name', 'Unknown Name')}")
                continue

            try:
                # Construct request to query instance configuration
                request = ShowInstanceConfigsRequest(instance_id=instance_id)
                # Call API to get configuration information
                response = client.show_instance_configs(request)
                configs = response.kafka_configs  # Get configuration list

                # Add configuration information to resource for ValueFilter processing
                config_found = False
                for config in configs:
                    if config.name == key:
                        config_found = True
                        actual_value_str = config.value  # API returned value is usually string
                        actual_value = actual_value_str  # Default use string value
                        # Try to convert actual value based on expected value type
                        if isinstance(value, bool):
                            # Convert string to boolean ('true' -> True, others -> False)
                            actual_value = actual_value_str.lower() == 'true'
                        elif isinstance(value, (int, float)):
                            # Try to convert string to expected number type
                            try:
                                actual_value = type(value)(actual_value_str)
                            except (ValueError, TypeError):
                                log.warning(
                                    f"Failed to convert Kafka instance {instance_id} config item "
                                    f"'{key}' value '{actual_value_str}' to "
                                    f"{type(value).__name__}."
                                    f"String comparison will be used.")
                                actual_value = actual_value_str  # Fallback to string comparison

                        # Add configuration value to resource
                        resource['KafkaConfig'] = {key: actual_value}
                        break

                if not config_found:
                    log.warning(
                        f"Configuration item '{key}' not found in Kafka instance {instance_id}")
                    resource['KafkaConfig'] = {key: None}

            except exceptions.ClientRequestException as e:
                # Handle API request exception
                log.error(
                    f"Failed to get Kafka instance {instance_id} config: "
                    f"{e.error_msg} (Status Code: {e.status_code})")
                continue
            except Exception as e:
                # Handle other potential exceptions
                log.error(f"Error occurred processing Kafka instance {instance_id}: {str(e)}")
                continue

        # Use parent class match method to filter resources
        original_key = self.data.get('key')
        self.data['key'] = f'KafkaConfig."{original_key}"'

        try:
            filtered = super(KafkaConfigComplianceFilter, self).process(resources, event)
        finally:
            # Restore original key, avoid affecting other filters
            self.data['key'] = original_key
        return filtered


@Kafka.filter_registry.register('marked-for-op')
class KafkaMarkedForOpFilter(Filter):
    """
    Filter Kafka instances based on specific "marked operation" tag.

    This filter is used to find those marked for `mark-for-op` action to perform specific
    operation (like delete, stop) at some future time.
    It checks specified tag key (`tag`), parses operation type and scheduled execution time
    from tag value, and compares with current time.

    :example:
    Find all Kafka instances marked for deletion, and tag key is 'custodian_cleanup':

    .. code-block:: yaml

        policies:
          - name: find-kafka-marked-for-deletion
            resource: huaweicloud.kafka
            filters:
              - type: marked-for-op          # Filter type
                op: delete                  # Operation type to find ('delete', 'stop', 'restart')
                tag: custodian_cleanup      # Tag key used for marking operation
                # skew: 1                   # (Optional) Time offset (days)
                # skew_hours: 2             # (Optional) Time offset (hours)
    """
    # Define this filter's input pattern (schema)
    schema = type_schema(
        'marked-for-op',  # Filter type name
        # Operation type to find
        op={'type': 'string', 'enum': ['delete', 'stop', 'restart']},
        # Tag key used for marking operation, default is 'mark-for-op-custodian'
        tag={'type': 'string', 'default': 'mark-for-op-custodian'},
        # (Optional) Time offset (days), allow N days in advance match, default is 0
        skew={'type': 'number', 'default': 0},
        # (Optional) Time offset (hours), allow N hours in advance match, default is 0
        skew_hours={'type': 'number', 'default': 0},
        # Time zone, default is 'utc'
        tz={'type': 'string', 'default': 'utc'},
    )
    schema_alias = True
    DEFAULT_TAG = "mark-for-op-custodian"

    def __init__(self, data, manager=None):
        super(KafkaMarkedForOpFilter, self).__init__(data, manager)
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
        """Process tag value, determine if it meets filter condition"""
        if not tag_value:
            return False

        # Process KafkaMarkForOpAction created value format "operation@timestamp"
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
            # Try to directly parse KafkaMarkForOpAction generated standard timestamp format
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
                self.log.warning(f"Failed to parse tag value: {tag_value}, error: {str(nested_e)}")
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
        """Replace nth occurrence of old with new in string"""
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
                        # Compatible with Huawei Cloud specific [{key: k1, value: v1}] format
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


@Kafka.action_registry.register('mark-for-op')
class KafkaMarkForOpAction(HuaweiCloudBaseAction):
    """
    Add a "marked operation" tag to Kafka instance.

    This action is used to mark resource so that it can be identified and executed by other policy
    (using `marked-for-op` filter) at some future time.
    It will create a tag on resource, tag value contains specified operation (`op`) and execution
    timestamp.

    :example:
    Mark Kafka instances created more than 90 days ago, let them be deleted 7 days later:

    .. code-block:: yaml

        policies:
          - name: mark-old-kafka-for-deletion
            resource: huaweicloud.kafka
            filters:
              - type: age
                days: 90
                op: gt
            actions:
              - type: mark-for-op          # Action type
                op: delete                  # Marked operation ('delete', 'stop', 'restart')
                days: 7                     # Delay execution days (from now)
                # hours: 0                  # (Optional) Delay execution hours (from now)
                tag: custodian_cleanup      # Marking tag key (should match with filter's tag)
    """
    # Define this action's input pattern (schema)
    schema = type_schema(
        'mark-for-op',  # Action type name
        # Marked operation type
        op={'enum': ['delete', 'stop', 'restart']},
        # Delay execution days (from current time)
        days={'type': 'number', 'minimum': 0, 'default': 0},
        # Delay execution hours (from current time)
        hours={'type': 'number', 'minimum': 0, 'default': 0},
        # Marking tag key, default is 'mark-for-op-custodian'
        tag={'type': 'string', 'default': 'mark-for-op-custodian'},
        # Declare 'op' parameter is required
        required=['op']
    )

    def perform_action(self, resource):
        """
        Perform marked operation on single resource.

        :param resource: Kafka instance resource dictionary to mark
        :return: None or API response (but usually no specific result)
        """
        # Get parameters from policy definition
        op = self.data.get('op')
        tag_key = self.data.get('tag', 'mark-for-op-custodian')
        days = self.data.get('days', 0)
        hours = self.data.get('hours', 0)

        instance_id = resource.get('instance_id')
        if not instance_id:
            log.error(
                f"Failed to mark Kafka resource missing 'instance_id': "
                f"{resource.get('name', 'Unknown Name')}")
            return None

        # Calculate scheduled execution time (UTC)
        from datetime import datetime, timedelta
        try:
            action_time = datetime.utcnow() + timedelta(days=days, hours=hours)
            # Format timestamp string, must be consistent with TagActionFilter parsing format
            action_time_str = action_time.strftime('%Y/%m/%d %H:%M:%S UTC')
        except OverflowError:
            log.error(
                f"Invalid marked operation timestamp calculation for Kafka instance {instance_id} "
                f"(days={days}, hours={hours})")
            return None

        # Build tag value, format is "operation_timestamp"
        tag_value = f"{op}@{action_time_str}"  # Use @ as separator, clearer

        # Call internal method to create tag
        self._create_or_update_tag(resource, tag_key, tag_value)

        return None  # Usually marking operation does not return specific result

    def _create_or_update_tag(self, resource, key, value):
        """
        Create or update tag for specified resource.

        :param resource: Target resource dictionary
        :param key: Tag key
        :param value: Tag value
        """
        instance_id = resource['instance_id']
        instance_name = resource.get('name', 'Unknown Name')
        # Get HuaweiCloud Kafka client
        client = self.manager.get_client()
        # Construct tag entity (using HuaweiCloud SDK TagEntity class)
        tag_entity = SDKTagEntity(key=key, value=value)
        try:
            # Construct batch create/delete tags request
            request = BatchCreateOrDeleteKafkaTagRequest()
            request.instance_id = instance_id
            request.body = BatchCreateOrDeleteTagReq()
            # HuaweiCloud batch interface has no direct "update" operation.
            # Current implementation assumes 'create' will overwrite existing tags.
            request.body.action = "create"
            request.body.tags = [tag_entity]
            # Call API to execute operation
            client.batch_create_or_delete_kafka_tag(request)
            log.info(
                f"Added or updated tag for Kafka instance {instance_name} ({instance_id}): "
                f"{key}={value}")
        except exceptions.ClientRequestException as e:
            # Handle API request exception
            log.error(
                f"Failed to add or update tag {key} for Kafka instance {instance_name} "
                f"({instance_id}): {e.error_msg} (Status Code: {e.status_code})"
            )
        except Exception as e:
            # Handle other potential exceptions
            log.error(
                f"Failed to add or update tag {key} for Kafka instance {instance_name} "
                f"({instance_id}): {str(e)}")


@Kafka.action_registry.register('auto-tag-user')
class KafkaAutoTagUser(HuaweiCloudBaseAction):
    """
    (Conceptual) Automatically add creator user tag to Kafka instance.

    **Important Note:** This action depends on resource data containing creator information
    (such as 'user_name' field here).
    HuaweiCloud API returned Kafka instance information **usually does not directly contain creator
    IAM user name**.
    Therefore, the effectiveness of this action depends on whether `QueryResourceManager`
    or its `augment` method can obtain and fill `user_name` field through other means
    (such as querying CTS operation log service). If unable to obtain, tag value will be 'unknown'.

    :example:
    Add tag 'Creator' to Kafka instances missing this tag,
    value is creator user name (if can obtain):

    .. code-block:: yaml

        policies:
          - name: tag-kafka-creator-if-missing
            resource: huaweicloud.kafka
            filters:
              - "tag:Creator": absent       # Filter out instances without 'Creator' tag
            actions:
              - type: auto-tag-user         # Action type
                tag: Creator                # Tag key to add (Default is 'CreatorName')
    """
    # Define this action's input pattern (schema)
    schema = type_schema(
        'auto-tag-user',  # Action type name
        # Specify tag key to add, default is 'CreatorName'
        tag={'type': 'string', 'default': 'CreatorName'},
        # This action's mode pattern, default is 'resource'
        # Optional 'account'(might represent current executing policy account, but not meaningful)
        mode={'type': 'string', 'enum': ['resource', 'account'], 'default': 'resource'},
        # If mode is 'resource', specify resource dictionary key to get user name
        user_key={'type': 'string', 'default': 'creator'},
        # Changed to 'creator' might be more general
        # Whether to update existing tag, default is True
        update={'type': 'boolean', 'default': True},
        required=[]  # No required parameters (because all have default values)
    )

    # Permission declaration (if specific permission is needed to get user information)
    # permissions = ('cts:listOperations',) # For example, if need to check CTS log

    def perform_action(self, resource):
        """
        Perform automatic marked user operation on single resource.

        :param resource: Kafka instance resource dictionary to mark
        :return: None
        """
        tag_key = self.data.get('tag', 'CreatorName')
        mode = self.data.get('mode', 'resource')
        user_key = self.data.get('user_key', 'creator')
        update = self.data.get('update', True)

        instance_id = resource.get('instance_id')
        instance_name = resource.get('name', 'Unknown Name')
        if not instance_id:
            log.error(f"Failed to mark Kafka resource missing 'instance_id': {instance_name}")
            return None

        # Check if update is needed, and whether tag already exists
        if not update and tag_key in [t.get('Key') for t in resource.get('Tags', [])]:
            log.debug(
                f"Kafka instance {instance_name} ({instance_id}) already exists tag '{tag_key}' "
                f"and not allowed to update, skip.")
            return None

        user_name = 'unknown'  # Default value
        if mode == 'resource':
            # Try to get user name from resource dictionary
            user_name = resource.get(user_key, 'unknown')
            if user_name == 'unknown':
                # If default 'creator' key not found, also try original code's 'user_name'
                user_name = resource.get('user_name', 'unknown')

                # If still unknown, can consider adding logic to query CTS log
                if user_name == 'unknown':
                    log.warning(
                        f"Unable to find creator information for Kafka instance {instance_name} "
                        f"({instance_id}) (tried keys: '{user_key}', 'user_name'). "
                        f"Using 'unknown'.")
        elif mode == 'account':
            log.warning("'account' mode in KafkaAutoTagUser is not fully implemented yet.")
            user_name = 'unknown'

        # Reuse KafkaMarkForOpAction's helper method
        kafka_marker = KafkaMarkForOpAction(self.data, self.manager)
        kafka_marker._create_or_update_tag(resource, tag_key, user_name)

        return None


@Kafka.action_registry.register('tag')
class KafkaTag(HuaweiCloudBaseAction):
    """
    Add or update a specified tag to Kafka instance.

    This is a generic tag adding action, allowing users to directly specify tag key and value.
    If same name tag key already exists, default will overwrite its value.

    :example:
    Add 'Environment=Production' tag to all Kafka instances in production environment:

    .. code-block:: yaml

        policies:
          - name: tag-kafka-production-env
            resource: huaweicloud.kafka
            # May need a filter to identify production environment instances
            # filters:
            #   - ...
            actions:
              - type: tag                   # Action type
                key: Environment            # Tag key to add/update
                value: Production           # Tag value to set
    """
    # Define this action's input pattern (schema)
    schema = type_schema(
        'tag',  # Action type name
        key={'type': 'string'},  # Tag key
        value={'type': 'string'},  # Tag value
        # Declare 'key' and 'value' parameters are required
        required=['key', 'value']
    )

    def perform_action(self, resource):
        """
        Perform add/update tag operation on single resource.

        :param resource: Kafka instance resource dictionary to mark
        :return: None
        """
        key = self.data.get('key')
        value = self.data.get('value')

        instance_id = resource.get('instance_id')
        if not instance_id:
            log.error(
                f"Failed to mark Kafka resource missing 'instance_id': "
                f"{resource.get('name', 'Unknown Name')}")
            return None

        # Reuse KafkaMarkForOpAction's helper method
        kafka_marker = KafkaMarkForOpAction(self.data, self.manager)
        kafka_marker._create_or_update_tag(resource, key, value)

        return None


@Kafka.action_registry.register('remove-tag')
class KafkaRemoveTag(HuaweiCloudBaseAction):
    """
    Remove one or more specified tags from Kafka instance.

    Allow users to remove tags from instance based on tag key.

    :example:
    Remove 'Temporary' tag from all Kafka instances:

    .. code-block:: yaml

        policies:
          - name: remove-temp-kafka-tags
            resource: huaweicloud.kafka
            # Can add filter to ensure only operate on instances containing this tag
            filters:
              - "tag:Temporary": present
            actions:
              - type: remove-tag            # Action type
                key: Temporary              # Tag key to remove (Required)
              # Can specify multiple keys to remove multiple tags at once
              # - type: remove-tag
              #   keys: ["Temp1", "Temp2"]
    """
    # Define this action's input pattern (schema)
    schema = type_schema(
        'remove-tag',  # Action type name
        # Can specify single key or keys list
        key={'type': 'string'},  # Single tag key to remove
        keys={'type': 'array', 'items': {'type': 'string'}},  # Tag key list to remove
        # required=['keys'] # Should at least need key or keys
        # Better way is to use oneOf or anyOf, but Custodian's schema might not support
        # Temporary allow key and keys to be optional, handle in code
    )

    def perform_action(self, resource):
        """
        Perform remove tag operation on single resource.

        :param resource: Kafka instance resource dictionary to remove tag
        :return: None
        """
        # Get tag keys list to remove
        tags_to_remove = self.data.get('keys', [])
        single_key = self.data.get('key')
        if single_key and single_key not in tags_to_remove:
            tags_to_remove.append(single_key)

        if not tags_to_remove:
            log.warning("No tag key specified in remove-tag action (key or keys).")
            return None

        instance_id = resource.get('instance_id')
        instance_name = resource.get('name', 'Unknown Name')
        if not instance_id:
            log.error(
                f"Failed to remove tag, Kafka resource missing 'instance_id': {instance_name}")
            return None

        # Check actual tags existing on instance, avoid trying to delete non-existing tag
        # (although API might allow, it produces unnecessary call)
        current_tags = {t.get('Key') for t in resource.get('Tags', [])}
        keys_that_exist = [k for k in tags_to_remove if k in current_tags]

        if not keys_that_exist:
            log.debug(
                f"Kafka instance {instance_name} ({instance_id}) has no tags to remove: "
                f"{tags_to_remove}")
            return None

        # Call internal method to remove tag
        self._remove_tags_internal(resource, keys_that_exist)

        return None

    def _remove_tags_internal(self, resource, keys_to_delete):
        """
        Internal helper method, call API to remove specified tag key list.

        :param resource: Target resource dictionary
        :param keys_to_delete: Tag key string list to delete
        """
        instance_id = resource['instance_id']
        instance_name = resource.get('name', 'Unknown Name')
        client = self.manager.get_client()

        # Create TagEntity for each key to delete (only provide key)
        tag_entities = [SDKTagEntity(key=k) for k in keys_to_delete]

        try:
            # Construct batch delete tags request
            request = BatchCreateOrDeleteKafkaTagRequest()
            request.instance_id = instance_id
            request.body = BatchCreateOrDeleteTagReq()
            request.body.action = "delete"  # Specify action as delete
            request.body.tags = tag_entities  # Include tags to delete
            # Call API to execute delete
            client.batch_create_or_delete_kafka_tag(request)
            log.info(
                f"Removed tags from Kafka instance {instance_name} ({instance_id}): "
                f"{keys_to_delete}")
        except exceptions.ClientRequestException as e:
            log.error(
                f"Failed to remove tags {keys_to_delete} from Kafka instance {instance_name} "
                f"({instance_id}): {e.error_msg} (Status Code: {e.status_code})"
            )
        except Exception as e:
            log.error(
                f"Failed to remove tags {keys_to_delete} from Kafka instance {instance_name} "
                f"({instance_id}): {str(e)}")


@Kafka.action_registry.register('rename-tag')
class KafkaRenameTag(HuaweiCloudBaseAction):
    """
    Rename a tag key on Kafka instance.

    This operation is actually "copy and delete":
    1. Read value of tag with old key (`old_key`).
    2. Create a new tag with new key (`new_key`) and old value.
    3. Delete tag with old key (`old_key`).

    :example:
    Rename all 'Env' tags to 'Environment' on all instances:

    .. code-block:: yaml

        policies:
          - name: standardize-env-tag-kafka
            resource: huaweicloud.kafka
            filters:
              - "tag:Env": present          # Ensure only operate on instances with 'Env' tag
            actions:
              - type: rename-tag            # Action type
                old_key: Env                # Old tag key
                new_key: Environment        # New tag key
    """
    # Define this action's input pattern (schema)
    schema = type_schema(
        'rename-tag',  # Action type name
        old_key={'type': 'string'},  # Old tag key
        new_key={'type': 'string'},  # New tag key
        # Declare 'old_key' and 'new_key' parameters are required
        required=['old_key', 'new_key']
    )

    def perform_action(self, resource):
        """
        Perform rename tag operation on single resource.

        :param resource: Kafka instance resource dictionary to rename tag
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
        instance_name = resource.get('name', 'Unknown Name')
        if not instance_id:
            log.error(
                f"Failed to rename tag, Kafka resource missing 'instance_id': {instance_name}")
            return None

        # Find old tag value
        old_value = None
        if 'Tags' in resource:
            for tag in resource['Tags']:
                if tag.get('Key') == old_key:
                    old_value = tag.get('Value')
                    break

        # If old tag does not exist, no operation
        if old_value is None:
            log.info(
                f"Kafka instance {instance_name} ({instance_id}) does not find tag '{old_key}', "
                f"skip rename.")
            return None

        # Check if new tag already exists
        if 'Tags' in resource:
            for tag in resource['Tags']:
                if tag.get('Key') == new_key:
                    log.warning(
                        f"Kafka instance {instance_name} ({instance_id}) already exists "
                        f"target tag key '{new_key}'. Rename operation will overwrite its "
                        f"existing value (if continue execution).")
                    break

        # 1. Add new tag (using old value)
        kafka_marker = KafkaMarkForOpAction(self.data, self.manager)
        kafka_marker._create_or_update_tag(resource, new_key, old_value)

        # 2. Remove old tag
        remover = KafkaRemoveTag(self.data, self.manager)
        remover._remove_tags_internal(resource, [old_key])

        log.info(
            f"Renamed Kafka instance {instance_name} ({instance_id}) "
            f"tag '{old_key}' to '{new_key}'")

        return None


@Kafka.action_registry.register('delete')
class DeleteKafka(HuaweiCloudBaseAction):
    """
    Delete specified Kafka instance.

    **Warning:** This is a destructive operation, permanently deleting Kafka instance and its data
    Please use with caution.

    :example:
    Delete Kafka instances created more than 90 days ago and marked for deletion:

    .. code-block:: yaml

        policies:
          - name: delete-old-marked-kafka
            resource: huaweicloud.kafka
            filters:
              - type: marked-for-op
                op: delete
                tag: custodian_cleanup # Assume using this tag for marking
              - type: age
                days: 90
                op: gt
            actions:
              - type: delete             # Action type
    """
    # Define this action's input pattern (schema)
    schema = type_schema(
        'delete',  # Action type name
        # Can add force=True etc. parameters, if API supports forced delete
        # force={'type': 'boolean', 'default': False}
    )

    # Define required IAM permissions for executing this operation
    permissions = ('kafka:deleteInstance',)

    def perform_action(self, resource):
        """
        Perform delete operation on single resource.

        :param resource: Kafka instance resource dictionary to delete
        :return: API call response (might contain task ID etc.) or None (if failed)
        """
        instance_id = resource.get('instance_id')
        instance_name = resource.get('name', 'Unknown Name')
        if not instance_id:
            log.error(f"Failed to delete Kafka resource missing 'instance_id': {instance_name}")
            return None

        # Get HuaweiCloud Kafka client
        client = self.manager.get_client()

        try:
            # Construct delete instance request
            request = DeleteInstanceRequest(instance_id=instance_id)
            # Call API to execute delete operation
            response = client.delete_instance(request)
            log.info(
                f"Started delete Kafka instance {instance_name} ({instance_id}) operation. "
                f"Response: {response}")
            return response  # Return API response
        except exceptions.ClientRequestException as e:
            log.error(
                f"Failed to delete Kafka instance {instance_name} ({instance_id}): "
                f"{e.error_msg} (Status Code: {e.status_code})")
            return None  # Return None if delete failed
        except Exception as e:
            log.error(f"Failed to delete Kafka instance {instance_name} ({instance_id}): {str(e)}")
            return None


@Kafka.action_registry.register('set-config')
class SetKafkaConfig(HuaweiCloudBaseAction):
    """
    Modify Kafka instance configuration item.

    This action allows updating various configuration parameters of Kafka instance, such as log
    collection, access control, etc.
    Need to provide a dictionary containing configuration item to modify and its new value.

    **Note:** Please refer to HuaweiCloud DMS Kafka API documentation for supported specific
    configuration items and effective values.
    Incorrect configuration might cause instance function anomaly.

    :example:
    Enable log collection for instance where 'enable.log.collection' configuration is false:

    .. code-block:: yaml

        policies:
          - name: enable-kafka-log-collection
            resource: huaweicloud.kafka
            filters:
              - type: config-compliance
                key: enable.log.collection
                op: eq
                value: false
            actions:
              - type: set-config        # Action type (might change to 'set-config'?)
                config:                     # Dictionary containing configuration items to modify
                  enable.log.collection: "true" # Note: API might expect boolean string format
                  # access.user.enable: "true" # Can modify multiple configuration items at once
    """
    # Define this action's input pattern (schema)
    schema = type_schema(
        'set-config',  # Action type name
        # Dictionary containing configuration key-value pairs, at least need one attribute
        config={'type': 'object', 'minProperties': 1,
                'additionalProperties': {'type': ['string', 'number', 'boolean']}},
        # Declare 'config' parameter is required
        required=['config']
    )

    # Define required IAM permissions for executing this operation
    permissions = ('kafka:modifyInstanceConfigs',)

    def perform_action(self, resource):
        """
        Perform modify configuration operation on single resource.

        :param resource: Kafka instance resource dictionary to modify configuration
        :return: API call response or None (if failed)
        """
        instance_id = resource.get('instance_id')
        instance_name = resource.get('name', 'Unknown Name')
        if not instance_id:
            log.error(
                f"Failed to modify configuration, Kafka resource missing 'instance_id': "
                f"{instance_name}")
            return None

        # Get configuration item dictionary from policy
        config_data = self.data.get('config', {})
        if not config_data:
            log.warning(
                f"No 'config' data provided in set-config action, skip instance "
                f"{instance_name} ({instance_id}).")
            return None

        # Get HuaweiCloud Kafka client
        client = self.manager.get_client()

        try:
            # Construct modify instance configuration request
            request = ModifyInstanceConfigsRequest()
            request.instance_id = instance_id
            # Create request body
            request.body = ModifyInstanceConfigsReq()

            # Prepare configuration item list for request
            # HuaweiCloud Kafka API expects a list of name/value configuration items instead of
            # directly setting attributes on request body
            from huaweicloudsdkkafka.v2.model import ModifyInstanceConfig
            kafka_configs = []

            # Convert key-value pairs from configuration dictionary to ModifyInstanceConfig objects
            for key, value in config_data.items():
                # Data type conversion (according to API requirements)
                if isinstance(value, bool):
                    processed_value = str(value).lower()  # Boolean to "true" or "false"
                elif isinstance(value, (int, float)):
                    processed_value = str(value)  # Number to string
                else:
                    processed_value = value  # Other types directly use

                # Create configuration object and add to list
                config_item = ModifyInstanceConfig(name=key, value=processed_value)
                kafka_configs.append(config_item)

            # Set request body kafka_configs attribute
            request.body.kafka_configs = kafka_configs

            if not kafka_configs:
                log.warning(
                    f"No valid configuration items provided for set-config action, "
                    f"skip instance {instance_name} ({instance_id}).")
                return None

            # Record prepared configuration items (for logging)
            processed_configs = {c.name: c.value for c in kafka_configs}
            config_item_str = [f'{c.name}={c.value}' for c in kafka_configs]
            log.debug(
                f"Prepared configuration items for Kafka instance "
                f"{instance_name} ({instance_id}): "
                f"{config_item_str}")

            # Call API to execute modify configuration operation
            response = client.modify_instance_configs(request)
            log.info(
                f"Modified configuration for Kafka instance {instance_name} ({instance_id}): "
                f"{processed_configs}. Response: {response}")
            return response  # Return API response
        except exceptions.ClientRequestException as e:
            log.error(
                f"Failed to modify Kafka instance {instance_name} ({instance_id}) "
                f"configuration {config_data}: {e.error_msg} (Status Code: {e.status_code})"
            )
            return None  # Return None if modification failed
        except Exception as e:
            log.error(
                f"Failed to modify Kafka instance {instance_name} ({instance_id}) "
                f"configuration: {str(e)}")
            return None
