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


@resources.register('reliability')
class RocketMQ(QueryResourceManager):
    """HuaweiCloud RocketMQ Instance Resource Manager.

    Responsible for discovering, filtering, and managing RocketMQ instance resources.

    :example:
    Define a simple policy to get all RocketMQ instances:

    .. code-block:: yaml

        policies:
          - name: rocketmq-instances-discovery  # Policy name
            resource: huaweicloud.reliability  # Specify resource type as HuaweiCloud RocketMQ
    """

    class resource_type(TypeInfo):
        """Define RocketMQ resource metadata and type information"""
        service = 'reliability'
        enum_spec = ('list_instances', 'instances',
                     'offset', 10)
        id = 'instance_id'  # Specify the field name for the resource's unique identifier
        name = 'name'  # Specify the field name for the resource's name
        date = 'created_at'  # Specify the field name for the resource's creation time
        tag = True  # Indicate that this resource supports tags
        tag_resource_type = 'rocketmq'  # Specify the resource type for querying tags

    def augment(self, resources):
        """
        Filter resource list to include only RocketMQ instances based on engine type.

        This method filters the API returned resources to only include instances
        with engine type 'reliability', which are the RocketMQ instances in
        HuaweiCloud DMS service.

        :param resources: Original resource list returned from API
        :return: Filtered resource list containing only RocketMQ instances
        """
        if not resources:
            return []

        filtered_resources = []
        for resource in resources:
            # Check if engine type is 'reliability'
            if resource.get('engine') == 'reliability':
                filtered_resources.append(resource)

        log.debug(f"Filtered DMS instances: {len(resources)} total, \
            {len(filtered_resources)} RocketMQ instances")
        return filtered_resources


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
            resource: huaweicloud.reliability
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
            resource: huaweicloud.reliability
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
            resource: huaweicloud.reliability
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
        from datetime import datetime
        from dateutil.tz import tzutc

        days = self.data.get('days', 0)
        hours = self.data.get('hours', 0)
        minutes = self.data.get('minutes', 0)

        now = datetime.now(tz=tzutc())
        log.info(f"filtering resources created \
            {op} {days} days, {hours} hours, {minutes} minutes ago")

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
                if isinstance(created_str, (int, float)) \
                    or (isinstance(created_str, str) and created_str.isdigit()):
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
                    except (ValueError, TypeError, OverflowError):
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
