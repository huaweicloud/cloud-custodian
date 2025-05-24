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
    ModifyInstanceConfigsRequest,
    ModifyInstanceConfigsReq,
    ShowInstanceConfigsRequest,
)

from c7n.filters import ValueFilter, AgeFilter, OPERATORS
from c7n.utils import type_schema, local_session

log = logging.getLogger("custodian.huaweicloud.resources.kafka")


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
        Filter resource list to include only kafka instances based on engine type.

        This method filters the API returned resources to only include instances
        with engine type 'kafka', which are the kafka instances in
        HuaweiCloud DMS service.

        :param resources: Original resource list returned from API
        :return: Filtered resource list containing only kafka instances
        """
        if not resources:
            return []

        filtered_resources = []
        for resource in resources:
            # Check if engine type is 'kafka'
            if resource.get('engine') == 'kafka':
                filtered_resources.append(resource)

        log.debug(f"Filtered DMS instances: {len(resources)} total, \
            {len(filtered_resources)} kafka instances")
        return filtered_resources


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
