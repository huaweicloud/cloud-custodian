# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from c7n.utils import type_schema
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.actions.tms import register_tms_actions
from c7n_huaweicloud.filters.tms import register_tms_filters
from c7n_huaweicloud.filters.vpc import SecurityGroupFilter, VpcFilter

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkrds.v3 import (
    DeleteInstanceRequest,
    StartInstanceRestartActionRequest,
    StartupInstanceRequest,
    StopInstanceRequest,
    CreateManualBackupRequest,
    CreateManualBackupRequestBody,
)

log = logging.getLogger('custodian.huaweicloud.resources.rds_mysql')


# Define a local TagEntity class to simplify tag operations
class TagEntity:
    """Simple tag structure to represent key-value pairs"""

    def __init__(self, key, value=None):
        """
        Initialize a tag entity
        :param key: Tag key (required)
        :param value: Tag value (optional)
        """
        self.key = key
        self.value = value


@resources.register('rds')
class RDS(QueryResourceManager):
    """Huawei Cloud RDS Instance Resource Manager

    :example:

        policies:
          - name: rds-list
            resource: huaweicloud.rds
    """

    class resource_type(TypeInfo):
        service = 'rds'
        enum_spec = ("list_instances", 'instances', 'offset')
        id = 'id'
        name = 'name'
        date = 'created'
        tag = True
        tag_resource_type = 'rds'

    def augment(self, resources):
        """
        Enhance the raw resource data obtained from the API.

        This method is mainly used to convert the tag list format from Huawei Cloud API
        (usually a list of dictionaries with 'key' and 'value' fields) to the AWS-compatible
        format used internally by Cloud Custodian (a list of dictionaries with
         'Key' and 'Value' fields).
        This improves consistency of cross-cloud provider policies.

        :param resources: List of raw resource dictionaries from the API
        :return: List of enhanced resource dictionaries with tags converted
        to AWS-compatible format under the 'Tags' key
        """
        for r in resources:
            # Check if the 'tags' key exists in the raw resource dictionary
            if 'tags' not in r:
                continue  # Skip this resource if there are no tags
            tags = []
            # Iterate through the original tag list
            for tag_entity in r['tags']:
                # Convert each tag to {'Key': ..., 'Value': ...} format
                tags.append({'Key': tag_entity.get('key'), 'Value': tag_entity.get('value')})
            # Add the converted tag list to the resource dictionary under the 'Tags' key
            r['Tags'] = tags
        return resources


# Register tag operations for RDS instances
register_tms_actions(RDS.action_registry)
register_tms_filters(RDS.filter_registry)


class RDSSecurityGroupFilter(SecurityGroupFilter):
    """Filter RDS instances by security group

    :example:

        policies:
          - name: rds-with-public-access-sg
            resource: huaweicloud.rds
            filters:
              - type: security-group
                key: name
                value: allow-public-access
    """

    RelatedIdsExpression = "security_group_id"


class RDSVpcFilter(VpcFilter):
    """Filter RDS instances by VPC

    :example:

        policies:
          - name: rds-in-production-vpc
            resource: huaweicloud.rds
            filters:
              - type: vpc
                key: name
                value: production-vpc
    """

    RelatedIdsExpression = "vpc_id"


# Register filters
RDS.filter_registry.register('security-group', RDSSecurityGroupFilter)
RDS.filter_registry.register('vpc', RDSVpcFilter)


@RDS.action_registry.register('delete')
class RDSDelete(HuaweiCloudBaseAction):
    """Delete RDS instance.

    :example:

        policies:
          - name: delete-test-rds
            resource: huaweicloud.rds
            filters:
              - type: value
                key: name
                value: test-rds
            actions:
              - delete
    """

    schema = type_schema('delete')
    permissions = ('rds:DeleteInstance',)

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        request = DeleteInstanceRequest(instance_id=instance_id)
        try:
            response = client.delete_instance(request)
            log.info(f"Successfully submitted request to delete RDS instance: {instance_id}")
            return response
        except exceptions.ClientRequestException as e:
            log.error(
                f"Failed to delete RDS instance: {e.status_code},"
                f" {e.request_id}, {e.error_code}, {e.error_msg}")
            raise


@RDS.action_registry.register('start')
class RDSStart(HuaweiCloudBaseAction):
    """Start RDS instance.

    :example:

        policies:
          - name: start-stopped-rds
            resource: huaweicloud.rds
            filters:
              - type: value
                key: status
                value: SHUTDOWN
            actions:
              - start
    """

    schema = type_schema('start')
    permissions = ('rds:StartInstance',)

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        request = StartupInstanceRequest(instance_id=instance_id)
        try:
            response = client.start_instance(request)
            log.info(f"Successfully submitted request to start RDS instance: {instance_id}")
            return response
        except exceptions.ClientRequestException as e:
            log.error(
                f"Failed to start RDS instance: {e.status_code}"
                f", {e.request_id}, {e.error_code}, {e.error_msg}")
            raise


@RDS.action_registry.register('stop')
class RDSStop(HuaweiCloudBaseAction):
    """Stop RDS instance.

    :example:

        policies:
          - name: stop-idle-rds
            resource: huaweicloud.rds
            filters:
              - type: value
                key: status
                value: ACTIVE
            actions:
              - stop
    """

    schema = type_schema('stop')
    permissions = ('rds:StopInstance',)

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        request = StopInstanceRequest(instance_id=instance_id)
        try:
            response = client.stop_instance(request)
            log.info(f"Successfully submitted request to stop RDS instance: {instance_id}")
            return response
        except exceptions.ClientRequestException as e:
            log.error(
                f"Failed to stop RDS instance: {e.status_code}"
                f", {e.request_id}, {e.error_code}, {e.error_msg}")
            raise


@RDS.action_registry.register('reboot')
class RDSReboot(HuaweiCloudBaseAction):
    """Reboot RDS instance.

    :example:

        policies:
          - name: reboot-hung-rds
            resource: huaweicloud.rds
            filters:
              - type: value
                key: status
                value: ACTIVE
            actions:
              - reboot
    """

    schema = type_schema('reboot')
    permissions = ('rds:RestartInstance',)

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        request = StartInstanceRestartActionRequest(instance_id=instance_id)
        try:
            response = client.restart_instance(request)
            log.info(f"Successfully submitted request to restart RDS instance: {instance_id}")
            return response
        except exceptions.ClientRequestException as e:
            log.error(
                f"Failed to restart RDS instance: {e.status_code}"
                f", {e.request_id}, {e.error_code}, {e.error_msg}")
            raise


@RDS.action_registry.register('snapshot')
class RDSSnapshot(HuaweiCloudBaseAction):
    """Create a manual backup (snapshot) of the RDS instance.

    :example:

        policies:
          - name: backup-critical-rds
            resource: huaweicloud.rds
            filters:
              - type: value
                key: name
                value: critical-db
            actions:
              - snapshot
    """

    schema = type_schema('snapshot')
    permissions = ('rds:CreateManualBackup',)

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']

        # Create backup request body
        backup_name = f"{resource['name']}-manual-backup"
        body = CreateManualBackupRequestBody(
            instance_id=instance_id,
            name=backup_name,
            description="Created by Cloud Custodian"
        )

        request = CreateManualBackupRequest(body=body)
        try:
            response = client.create_manual_backup(request)
            log.info(
                f"Successfully submitted request to create manual backup:"
                f" {instance_id}, backup name: {backup_name}")
            return response
        except exceptions.ClientRequestException as e:
            log.error(
                f"Failed to create manual backup: {e.status_code}"
                f", {e.request_id}, {e.error_code}, {e.error_msg}")
            raise
