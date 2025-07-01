# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from c7n.filters import Filter
from c7n.filters.core import OPERATORS, type_schema
from c7n.utils import local_session
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

from huaweicloudsdkrds.v3 import (
    SetSecurityGroupRequest, SwitchSslRequest,
    UpdatePortRequest, CustomerModifyAutoEnlargePolicyReq, AttachEipRequest,
    CustomerUpgradeDatabaseVersionReq,
    SetAuditlogPolicyRequest, ShowAuditlogPolicyRequest, ListDatastoresRequest,
    ShowAutoEnlargePolicyRequest, ShowBackupPolicyRequest, SetBackupPolicyRequest,
    SetBackupPolicyRequestBody, ShowInstanceConfigurationRequest,
    UpdateInstanceConfigurationRequest, UpdateInstanceConfigurationRequestBody, BackupPolicy,
    SetAutoEnlargePolicyRequest, UpgradeDbVersionNewRequest,
    ListPostgresqlHbaInfoRequest, ModifyPostgresqlHbaConfRequest,
    UpdateTdeStatusRequest
)
from huaweicloudsdkcore.exceptions import exceptions

log = logging.getLogger("custodian.huaweicloud.resources.rds")


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
    """Huawei Cloud RDS Resource Manager

    Used to manage instances in the Huawei Cloud Relational Database Service.

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-instance-list
            resource: huaweicloud.rds
            filters:
              - type: value
                key: status
                value: ACTIVE
    """

    class resource_type(TypeInfo):
        service = 'rds'
        enum_spec = ('list_instances', 'instances', 'offset')
        id = 'id'
        name = 'name'
        filter_name = 'id'
        filter_type = 'scalar'
        date = 'created'
        taggable = True
        tag_resource_type = 'rds'


@RDS.filter_registry.register('rds-list')
class RDSListFilter(Filter):
    """Filter RDS instances by specific instance IDs
    :example:
    .. code-block:: yaml
        policies:
          - name: rds-list-filter
            resource: huaweicloud.rds
            filters:
              - type: rds-list
                ids:
                  - 5fc738f6-67da-4f1f-a78b-f9d61588fdee
                  - 76e4bc08-2e5b-4ccc-b26a-e6484f022365
    """
    schema = type_schema(
        'rds-list',
        ids={'type': 'array', 'items': {'type': 'string'}}
    )

    def process(self, resources, event=None):
        ids = self.data.get('ids', [])
        if not ids:
            return resources
        return [r for r in resources if r['id'] in ids]


@RDS.filter_registry.register('disk-auto-expansion')
class DiskAutoExpansionFilter(Filter):
    """Filter RDS instances by disk auto-expansion status

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-disk-auto-expansion-disabled
            resource: huaweicloud.rds
            filters:
              - type: disk-auto-expansion
                enabled: false
    """
    schema = type_schema(
        'disk-auto-expansion',
        enabled={'type': 'boolean'}
    )

    def process(self, resources, event=None):
        enabled = self.data.get('enabled', True)
        client = local_session(self.manager.session_factory).client("rds")
        matched_resources = []

        for resource in resources:
            instance_id = resource['id']
            try:
                # Query instance disk auto-expansion policy
                # API Documentation: https://support.huaweicloud.com/api-rds/rds_05_0027.html
                # GET /v3/{project_id}/instances/{instance_id}/disk-auto-expansion
                # Call the API path directly without using the predefined request object in the SDK

                request = ShowAutoEnlargePolicyRequest(instance_id=instance_id)
                response = client.show_auto_enlarge_policy(request)

                # Determine if auto-expansion is enabled based on the API response
                auto_expansion_enabled = response.switch_option

                if auto_expansion_enabled == enabled:
                    matched_resources.append(resource)
            except Exception as e:
                self.log.error(
                    f"Failed to get auto-expansion policy for RDS instance {resource['name']} "
                    f"(ID: {instance_id}): {e}")
                # If the auto-expansion policy cannot be obtained, assume it is not enabled
                if not enabled:
                    matched_resources.append(resource)
        return matched_resources


@RDS.filter_registry.register('database-version')
class DatabaseVersionFilter(Filter):
    """Filter RDS instances that are not the latest minor version

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-outdated-version
            resource: huaweicloud.rds
            filters:
              - type: database-version
                database_name: mysql  # Optional, specify the database engine type
    """
    schema = type_schema(
        'database-version',
        database_name={'enum': ['mysql', 'postgresql', 'sqlserver'], 'default': 'mysql'}
    )

    def process(self, resources, event=None):
        client = local_session(self.manager.session_factory).client("rds")
        database_name = self.data.get('database_name', 'mysql').lower()

        # Get the latest minor version information for all database versions
        try:
            # Call the API to get the list of available versions for the specified database engine
            # API Documentation: https://support.huaweicloud.com/api-rds/rds_06_0001.html
            # GET /v3/{project_id}/datastores/{database_name}
            request = ListDatastoresRequest()
            request.database_name = database_name
            response = client.list_datastores(request)

            # Store the latest minor version number for each major version
            latest_versions = {}
            for datastore in response.data_stores:
                version_parts = datastore.name.split('.')
                if len(version_parts) >= 2:
                    # Extract the major version number, such as 5.7, 8.0, etc.
                    major_version = '.'.join(version_parts[:2])

                    # If the major version has not been recorded or the current version
                    # is more recent, update the record
                    if major_version not in latest_versions or self._compare_versions(
                            datastore.name, latest_versions[major_version]) > 0:
                        latest_versions[major_version] = datastore.name

            self.log.debug(f"Get the latest minor versions for each major version "
                           f"of the {database_name} engine: {latest_versions}")
        except Exception as e:
            self.log.error(f"Failed to get the version list of the "
                           f"database engine {database_name}: {e}")
            return []

        # Filter out instances that are not the latest minor version
        outdated_resources = []
        for resource in resources:
            datastore = resource.get('datastore', {})
            resource_type = datastore.get('type', '').lower()

            # Skip mismatched database types
            if resource_type != database_name:
                continue

            # Get the major version number from the complete version number
            complete_version = datastore.get('complete_version', datastore.get('version', ''))
            if not complete_version:
                continue

            version_parts = complete_version.split('.')
            if len(version_parts) < 2:
                continue

            # Extract the major version number
            major_version = '.'.join(version_parts[:2])

            # Extract the first three parts as the comparison
            # version number (e.g., 8.0.28.231003 -> 8.0.28)
            instance_version_to_compare = '.'.join(version_parts[:3]) \
                if len(version_parts) >= 3 else complete_version

            # Check if there is a corresponding latest minor version for the major version
            if major_version in latest_versions:
                latest_version = latest_versions[major_version]
                latest_version_parts = latest_version.split('.')
                latest_version_to_compare = '.'.join(latest_version_parts[:3]) \
                    if len(latest_version_parts) >= 3 else latest_version

                # Compare versions by only comparing the first three parts,
                # ignoring the build number after that
                if self._compare_versions(instance_version_to_compare,
                                          latest_version_to_compare) < 0:
                    self.log.debug(
                        f"Instance {resource['name']} version"
                        f" {complete_version} is not the latest minor version {latest_version}")
                    outdated_resources.append(resource)
            else:
                self.log.debug(
                    f"Cannot find the latest minor version corresponding to the "
                    f"main version {major_version} of instance {resource['name']}")
        return outdated_resources

    def _compare_versions(self, version1, version2):
        """Compare the sizes of two version numbers, only comparing the
        first three parts (e.g., 8.0.28), ignoring the build number after that.
        Return value:
            -1: version1 < version2
             0: version1 = version2
             1: version1 > version2
        """
        # Ensure only the first three parts of the version number are compared
        v1_parts = version1.split('.')[:3]
        v2_parts = version2.split('.')[:3]
        for i in range(max(len(v1_parts), len(v2_parts))):
            # If a version number part does not exist, it is considered as 0
            v1 = int(v1_parts[i]) if i < len(v1_parts) else 0
            v2 = int(v2_parts[i]) if i < len(v2_parts) else 0

            if v1 < v2:
                return -1
            elif v1 > v2:
                return 1

        return 0


@RDS.filter_registry.register('eip')
class EIPFilter(Filter):
    """Filter RDS instances that have or do not have an Elastic Public IP (EIP) bound
    :example:

    .. code-block:: yaml

        policies:
          - name: rds-with-eip
            resource: huaweicloud.rds
            filters:
              - type: eip
                exists: true
    """
    schema = type_schema(
        'eip',
        exists={'type': 'boolean'}
    )

    def process(self, resources, event=None):
        exists = self.data.get('exists', True)
        matched = []
        for resource in resources:
            has_eip = resource.get('public_ips') is not None and len(
                resource.get('public_ips', [])) > 0
            if has_eip == exists:
                matched.append(resource)
        return matched


@RDS.filter_registry.register('audit-log-disabled')
class AuditLogDisabledFilter(Filter):
    """Filter RDS instances that do not have audit logs enabled

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-audit-log-disabled
            resource: huaweicloud.rds
            filters:
              - type: audit-log-disabled
    """
    schema = type_schema('audit-log-disabled')

    def process(self, resources, event=None):
        client = local_session(self.manager.session_factory).client("rds")
        matched_resources = []

        for resource in resources:
            instance_id = resource['id']
            try:
                request = ShowAuditlogPolicyRequest()
                request.instance_id = instance_id
                response = client.show_auditlog_policy(request)

                # keep_days is 0, which means the audit log policy is disabled
                if response.keep_days == 0:
                    matched_resources.append(resource)
            except Exception as e:
                self.log.error(
                    f"Get the audit log policy of RDS instance {resource['name']} "
                    f"(ID: {instance_id}) failed: {e}")
                # If the audit log policy cannot be obtained, assume it is not enabled
                matched_resources.append(resource)

        return matched_resources


@RDS.filter_registry.register('backup-policy-disabled')
class BackupPolicyDisabledFilter(Filter):
    """Filter RDS instances that do not have an auto backup policy enabled

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-backup-policy-disabled
            resource: huaweicloud.rds
            filters:
              - type: backup-policy-disabled
    """
    schema = type_schema('backup-policy-disabled')

    def process(self, resources, event=None):
        client = local_session(self.manager.session_factory).client("rds")
        matched_resources = []

        for resource in resources:
            instance_id = resource['id']
            try:
                # Query instance backup policy
                # API Document: https://support.huaweicloud.com/api-rds/rds_09_0003.html
                # GET /v3/{project_id}/instances/{instance_id}/backups/policy
                request = ShowBackupPolicyRequest()
                request.instance_id = instance_id
                response = client.show_backup_policy(request)

                # Check if auto backup is enabled
                # If keep_days is 0 or backup_type is empty, it is considered
                # that auto backup is not enabled
                keep_days = response.backup_policy.keep_days

                if keep_days == 0:
                    matched_resources.append(resource)
            except Exception as e:
                self.log.error(
                    f"Failed to get backup policy for RDS instance "
                    f"{resource['name']} (ID: {instance_id}): {e}")
                # If the backup policy cannot be obtained, assume it is not enabled
                matched_resources.append(resource)

        return matched_resources


@RDS.filter_registry.register('instance-parameter')
class InstanceParameterFilter(Filter):
    """Filter RDS instances by specific parameter configurations

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-max-connections-too-low
            resource: huaweicloud.rds
            filters:
              - type: instance-parameter
                name: max_connections
                value: 500
                op: lt
    """
    schema = type_schema(
        'instance-parameter',
        required=['name'],
        name={'type': 'string'},
        value={'oneOf': [
            {'type': 'string'},
            {'type': 'integer'},
            {'type': 'boolean'}
        ]},
        op={'enum': list(OPERATORS.keys()), 'default': 'eq'}
    )

    def process(self, resources, event=None):
        client = local_session(self.manager.session_factory).client("rds")
        param_name = self.data.get('name')
        param_value = self.data.get('value')
        op_name = self.data.get('op', 'eq')
        op = OPERATORS.get(op_name)

        matched_resources = []

        for resource in resources:
            instance_id = resource['id']
            try:
                # Query instance parameter template
                # API Document: https://support.huaweicloud.com/api-rds/rds_09_0306.html
                # GET /v3/{project_id}/instances/{instance_id}/configurations
                request = ShowInstanceConfigurationRequest()
                request.instance_id = instance_id
                response = client.show_instance_configuration(request)

                # Find the target parameter in the parameter list
                found = False
                for param in response.configuration_parameters:
                    if param.name == param_name:
                        found = True
                        # Convert and compare the value based on the parameter type
                        current_value = param.value
                        if param.type == 'integer':
                            current_value = int(current_value)
                        elif param.type == 'boolean':
                            current_value = (current_value.lower() == 'true')

                        # Apply the operator to the parameter value for comparison
                        if op(current_value, param_value):
                            matched_resources.append(resource)
                        break

                if not found:
                    self.log.debug(
                        f"RDS instance {resource['name']} (ID: {instance_id}) "
                        f"does not have parameter {param_name}")
            except Exception as e:
                self.log.error(
                    f"Failed to get the parameter template for RDS instance "
                    f"{resource['name']} (ID: {instance_id}): {e}")

        return matched_resources


@RDS.action_registry.register('set-security-group')
class SetSecurityGroupAction(HuaweiCloudBaseAction):
    """Modify the security group of an RDS instance

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-set-security-group
            resource: huaweicloud.rds
            filters:
              - type: value
                key: name
                value: test-mysql
            actions:
              - type: set-security-group
                security_group_id: 438d0abe-0616-47bc-9573-ee1ed51c7e44
    """
    schema = type_schema(
        'set-security-group',
        required=['security_group_id'],
        security_group_id={'type': 'string'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        security_group_id = self.data['security_group_id']

        try:
            request = SetSecurityGroupRequest()
            request.instance_id = instance_id
            request_body = {
                'security_group_id': security_group_id
            }
            request.body = request_body
            response = client.set_security_group(request)
            self.log.info(f"Successfully set security group for RDS instance "
                          f"{resource['name']} (ID: {instance_id})")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(f"Failed to set security group for RDS instance "
                           f"{resource['name']} (ID: {instance_id}): {e}")
            raise


@RDS.action_registry.register('switch-ssl')
class SwitchSSLAction(HuaweiCloudBaseAction):
    """Enable or disable SSL encryption for the RDS instance,
    only supports MySQL, pg through modifying parameters to control

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-enable-ssl
            resource: huaweicloud.rds
            filters:
            - type: value
                key: enable_ssl
                value: true
            actions:
              - type: switch-ssl
                ssl_option: false
    """
    schema = type_schema(
        'switch-ssl',
        required=['ssl_option'],
        ssl_option={'type': 'boolean'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        ssl_option = self.data['ssl_option']

        try:
            request = SwitchSslRequest()
            request.instance_id = instance_id
            ssl_option = True if ssl_option else False
            request_body = {
                'ssl_option': ssl_option
            }
            request.body = request_body
            response = client.switch_ssl(request)
            self.log.info(
                f"Successfully {'enabled' if ssl_option else 'disabled'} "
                f"SSL encryption for RDS instance {resource['name']} (ID: {instance_id})")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to {'enable' if ssl_option else 'disable'} "
                f"SSL encryption for RDS instance {resource['name']} (ID: {instance_id}): {e}")
            raise


@RDS.action_registry.register('update-port')
class UpdatePortAction(HuaweiCloudBaseAction):
    """Modify the port of the RDS instance

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-update-port
            resource: huaweicloud.rds
            filters:
              - type: value
                key: name
                value: 3306
            actions:
              - type: update-port
                port: 3307
    """
    schema = type_schema(
        'update-port',
        required=['port'],
        port={'type': 'integer', 'minimum': 1, 'maximum': 65535}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        port = self.data['port']

        try:
            request = UpdatePortRequest()
            # Construct the request body
            request_body = {
                'port': port
            }
            request.instance_id = instance_id
            request.body = request_body
            response = client.update_port(request)
            self.log.info(f"Successfully updated port for RDS instance "
                          f"{resource['name']} (ID: {instance_id}) to {port}")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(f"Failed to update port for RDS instance "
                           f"{resource['name']} (ID: {instance_id}): {e}")
            raise


@RDS.action_registry.register('set-auto-enlarge-policy')
class SetAutoEnlargePolicyAction(HuaweiCloudBaseAction):
    """Set the autoEnlarge policy for the RDS instance

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-enable-auto-enlarge
            resource: huaweicloud.rds
            filters:
              - type: disk-auto-expansion
                enabled: false
            actions:
              - type: set-auto-enlarge-policy
                switch_option: true
                limit_size: 4000
                trigger_threshold: 10
                step_percent: 20
    """
    schema = type_schema(
        'set-auto-enlarge-policy',
        required=['switch_option'],
        switch_option={'type': 'boolean'},
        limit_size={'type': 'integer', 'minimum': 40, 'maximum': 4000},
        trigger_threshold={'type': 'integer', 'minimum': 5, 'maximum': 15},
        step_percent={'type': 'integer', 'minimum': 5, 'maximum': 100}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        switch_option = self.data['switch_option']

        if switch_option:
            body = CustomerModifyAutoEnlargePolicyReq(
                switch_option=switch_option,
                limit_size=self.data['limit_size'],
                trigger_threshold=self.data['trigger_threshold'],
                step_percent=self.data['step_percent'],
            )
        else:
            body = CustomerModifyAutoEnlargePolicyReq(
                switch_option=switch_option,
            )

        request = SetAutoEnlargePolicyRequest(instance_id=instance_id, body=body)

        try:
            response = client.set_auto_enlarge_policy(request)
            self.log.info(
                f"Successfully {'enabled' if switch_option else 'disabled'} "
                f"autoEnlarge policy for RDS instance {resource['name']} (ID: {instance_id})")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to set autoEnlarge policy for RDS instance "
                f"{resource['name']} (ID: {instance_id}): {e}")
            raise


@RDS.action_registry.register('attach-eip')
class AttachEIPAction(HuaweiCloudBaseAction):
    """Bind or unbind the EIP for the RDS instance

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-bind-eip
            resource: huaweicloud.rds
            filters:
              - type: rds-list
                ids:
                  - 926dfdb3ff654c6e9506ca91e0b403b3in03
            actions:
              - type: attach-eip
                is_bind: true
                public_ip: 1.178.45.199
                public_ip_id: 1bf25cb6-13ef-4a71-a85f-e4da190c016d
    """
    schema = type_schema(
        'attach-eip',
        required=['is_bind'],
        is_bind={'type': 'boolean'},
        public_ip={'type': 'string'},
        public_ip_id={'type': 'string'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        is_bind = self.data['is_bind']
        public_ip = self.data.get('public_ip')
        public_ip_id = self.data.get('public_ip_id')

        if is_bind == 'bind' and (not public_ip or not public_ip_id):
            self.log.error(
                "When binding an EIP, both public_ip and public_ip_id parameters must be provided")
            return

        try:
            request = AttachEipRequest()
            request.instance_id = instance_id
            request_body = {
                'is_bind': is_bind
            }
            if is_bind:
                request_body['public_ip'] = public_ip
                request_body['public_ip_id'] = public_ip_id
            request.body = request_body
            response = client.attach_eip(request)
            self.log.info(
                f"Successfully {'bound' if is_bind else 'unbound'} EIP for RDS instance "
                f"{resource['name']} (ID: {instance_id})")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to {'bind' if is_bind else 'unbind'} EIP for RDS instance "
                f"{resource['name']} (ID: {instance_id}): {e}")
            raise


@RDS.action_registry.register('upgrade-db-version')
class UpgradeDBVersionAction(HuaweiCloudBaseAction):
    """Upgrade the RDS instance to a minor version

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-upgrade-minor-version
            resource: huaweicloud.rds
            filters:
              - type: database-version
                version: 5.7.37
                op: lt
            actions:
              - type: upgrade-db-version
                is_delayed: false
                target_version: 5.7.41  # Optional parameter, specify the target version
                set_backup: true  # Optional parameter, whether to set auto backup
    """
    schema = type_schema(
        'upgrade-db-version',
        is_delayed={'type': 'boolean'},
        target_version={'type': 'string'},
        set_backup={'type': 'boolean'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        is_delayed = self.data.get('is_delayed', False)
        target_version = self.data.get('target_version')
        set_backup = self.data.get('set_backup', False)

        try:
            # Construct the version upgrade request
            # API Document: https://support.huaweicloud.com/api-rds/rds_05_0041.html
            # POST /v3/{project_id}/instances/{instance_id}
            request = UpgradeDbVersionNewRequest()
            request.instance_id = instance_id

            # Set upgrade parameters
            upgrade_req = CustomerUpgradeDatabaseVersionReq()
            upgrade_req.delay = is_delayed

            # If a target version is specified, set the target version
            if target_version:
                # First, get the list of available versions
                try:
                    datastore = resource.get('datastore', {})
                    database_name = datastore.get('type', 'mysql').lower()

                    # Get the list of available versions
                    datastores_request = ListDatastoresRequest()
                    datastores_request.database_name = database_name
                    datastores_response = client.list_datastores(datastores_request)

                    # Validate if the target version is valid
                    valid_version = False
                    for datastore_info in datastores_response.data_stores:
                        if datastore_info.name == target_version:
                            upgrade_req.target_version = datastore_info.id
                            self.log.info(f"Found target version {target_version}, "
                                          f"ID: {datastore_info.id}")
                            valid_version = True
                            break

                    if not valid_version:
                        self.log.warning(
                            f"Target version {target_version} not found, "
                            f"will use the default version for upgrade")
                except Exception as e:
                    self.log.error(f"Failed to get the list of available versions: {e}")

            # Set backup if specified
            if set_backup:
                upgrade_req.with_backup = True

            # Set the request body
            request.body = upgrade_req

            # Execute the upgrade request
            response = client.upgrade_db_version_new(request)
            self.log.info(
                f"Successfully submitted database version upgrade request for RDS instance "
                f"{resource['name']} (ID: {instance_id})")

            return response
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to upgrade database version for RDS instance "
                f"{resource['name']} (ID: {instance_id}): {e}")
            raise


@RDS.action_registry.register('set-audit-log-policy')
class SetAuditLogPolicyAction(HuaweiCloudBaseAction):
    """Set the audit log policy for the RDS instance

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-enable-audit-log
            resource: huaweicloud.rds
            filters:
              - type: audit-log-disabled
            actions:
              - type: set-audit-log-policy
                keep_days: 7
                audit_types:
                  - SELECT
                  - INSERT
                  - UPDATE
                  - DELETE
    """
    schema = type_schema(
        'set-audit-log-policy',
        required=['keep_days'],
        keep_days={'type': 'integer', 'minimum': 0, 'maximum': 732},
        reserve_auditlogs={'type': 'boolean'},
        audit_types={'type': 'array', 'items': {'type': 'string'}}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        keep_days = self.data['keep_days']
        reserve_auditlogs = self.data.get('reserve_auditlogs', True)
        audit_types = self.data.get('audit_types', [])

        try:
            request = SetAuditlogPolicyRequest()
            request.body = {}
            request.instance_id = instance_id
            request.body['keep_days'] = keep_days

            if keep_days == 0:
                request.body['reserve_auditlogs'] = reserve_auditlogs

            if audit_types and keep_days > 0:
                request.body['audit_types'] = audit_types

            response = client.set_auditlog_policy(request)
            self.log.info(
                f"Successfully {'enabled' if keep_days > 0 else 'disabled'} audit log policy "
                f"for RDS instance {resource['name']} (ID: {instance_id})")
            return response
        except Exception as e:
            self.log.error(
                f"Failed to set audit log policy for RDS instance "
                f"{resource['name']} (ID: {instance_id}): {e}")
            raise


@RDS.action_registry.register('set-backup-policy')
class SetBackupPolicyAction(HuaweiCloudBaseAction):
    """Set the auto backup policy for the RDS instance

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-enable-backup
            resource: huaweicloud.rds
            filters:
              - type: backup-policy-disabled
            actions:
              - type: set-backup-policy
                keep_days: 3
                start_time: "01:00-02:00"
                period: "1,2,3,4"
                reserve_backups: "true"
    """
    schema = type_schema(
        'set-backup-policy',
        required=['keep_days', 'start_time', 'period'],
        keep_days={'type': 'integer', 'minimum': 1, 'maximum': 732},
        start_time={'type': 'string'},
        period={'type': 'string'},
        reserve_backups={'enum': ['true', 'false'], 'default': 'true'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        keep_days = self.data['keep_days']
        start_time = self.data['start_time']
        period = self.data['period']
        reserve_backups = self.data.get('reserve_backups', 'true')

        try:
            # Set backup policy
            # API Document: https://support.huaweicloud.com/api-rds/rds_09_0002.html
            # PUT /v3/{project_id}/instances/{instance_id}/backups/policy
            request = SetBackupPolicyRequest()
            request.instance_id = instance_id

            backupPolicyBody = BackupPolicy(keep_days=keep_days,
                                            start_time=start_time,
                                            period=period)

            # Construct the request body
            request_body = SetBackupPolicyRequestBody(
                backup_policy=backupPolicyBody,
                reserve_backups=reserve_backups
            )
            request.body = request_body

            response = client.set_backup_policy(request)
            self.log.info(f"Successfully set auto backup policy for RDS instance "
                          f"{resource['name']} (ID: {instance_id})")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to set auto backup policy for RDS instance "
                f"{resource['name']} (ID: {instance_id}): {e}")
            raise


@RDS.action_registry.register('update-instance-parameter')
class UpdateInstanceParameterAction(HuaweiCloudBaseAction):
    """Modify the parameter configuration of an RDS instance

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-update-max-connections
            resource: huaweicloud.rds
            filters:
              - type: instance-parameter
                name: max_connections
                value: 500
                op: lt
            actions:
              - type: update-instance-parameter
                parameters:
                  - name: max_connections
                    value: "1000"
    """
    schema = type_schema(
        'update-instance-parameter',
        required=['parameters'],
        parameters={'type': 'array', 'items': {
            'type': 'object',
            'properties': {
                'name': {'type': 'string'},
                'value': {'type': 'string'}
            },
            'required': ['name', 'value']
        }}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        parameters = self.data['parameters']

        try:
            # Modify instance parameters
            # API Document: https://support.huaweicloud.com/api-rds/rds_09_0303.html
            # PUT /v3/{project_id}/instances/{instance_id}/configurations
            request = UpdateInstanceConfigurationRequest()
            request.instance_id = instance_id

            # Construct the request body
            request_body = UpdateInstanceConfigurationRequestBody(
                values={}
            )

            for param in parameters:
                request_body.values[param['name']] = param['value']

            request.body = request_body

            response = client.update_instance_configuration(request)
            self.log.info(f"Successfully modified parameters for RDS instance "
                          f"{resource['name']} (ID: {instance_id})")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(f"Failed to modify parameters for RDS instance "
                           f"{resource['name']} (ID: {instance_id}): {e}")
            raise


@RDS.filter_registry.register('postgresql-hba-conf')
class PostgresqlHbaConfFilter(Filter):
    """Filter PostgreSQL RDS instances based on pg_hba.conf configuration

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-pg-hba-conf-check
            resource: huaweicloud.rds
            filters:
              - type: postgresql-hba-conf
                has_config:
                  type: host
                  database: all
                  user: all
                  address: 0.0.0.0/0
                  method: md5
    """
    schema = type_schema(
        'postgresql-hba-conf',
        has_config={
            'type': 'object',
            'properties': {
                'type': {'type': 'string'},
                'database': {'type': 'string'},
                'user': {'type': 'string'},
                'address': {'type': 'string'},
                'mask': {'type': 'string'},
                'method': {'type': 'string'}
            }
        }
    )

    def process(self, resources, event=None):
        client = local_session(self.manager.session_factory).client("rds")
        has_config = self.data.get('has_config')
        matched_resources = []

        for resource in resources:
            # Process only PostgreSQL instances
            if resource.get('datastore', {}).get('type', '').lower() != 'postgresql':
                continue

            instance_id = resource['id']
            try:
                # Query the pg_hba.conf file configuration of the instance
                # API Document: https://support.huaweicloud.com/api-rds/rds_11_0020.html
                request = ListPostgresqlHbaInfoRequest()
                request.instance_id = instance_id
                response = client.list_postgresql_hba_info(request)

                if not has_config:
                    # If no filter conditions are specified, return all PostgreSQL instances
                    matched_resources.append(resource)
                    continue

                # configs = response.hba_conf_items
                # match_found = False

                # Check if each configuration matches the filter conditions
                for config in response.body:
                    config_match = True

                    # Check each specified attribute
                    for key, value in has_config.items():
                        if key == 'type' and getattr(config, 'type', None) != value:
                            config_match = False
                            break
                        elif key == 'database' and getattr(config, 'database', None) != value:
                            config_match = False
                            break
                        elif key == 'user' and getattr(config, 'user', None) != value:
                            config_match = False
                            break
                        elif key == 'address' and getattr(config, 'address', None) != value:
                            config_match = False
                            break
                        elif key == 'mask' and getattr(config, 'mask', None) != value:
                            config_match = False
                            break
                        elif key == 'method' and getattr(config, 'method', None) != value:
                            config_match = False
                            break

                    if config_match:
                        match_found = True
                        break

                if match_found:
                    matched_resources.append(resource)
            except Exception as e:
                self.log.error(
                    f"Failed to get the pg_hba.conf configuration for RDS PostgreSQL instance "
                    f"{resource['name']} (ID: {instance_id}): {e}")
        return matched_resources


@RDS.action_registry.register('modify-pg-hba-conf')
class ModifyPgHbaConfAction(HuaweiCloudBaseAction):
    """Modify one or more configurations in the pg_hba.conf file

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-modify-pg-hba-conf
            resource: huaweicloud.rds
            filters:
              - type: postgresql-hba-conf
                has_config:
                  type: host
                  database: all
                  user: all
                  address: 0.0.0.0/0
                  method: md5
            actions:
              - type: modify-pg-hba-conf
                configs:
                  - type: hostssl
                    database: all
                    user: all
                    address: 0.0.0.0/0
                    mask: ""
                    method: scram-sha-256
                    priority: 0
    """
    schema = type_schema(
        'modify-pg-hba-conf',
        required=['configs'],
        configs={
            'type': 'array',
            'items': {
                'type': 'object',
                'required': ['type', 'database', 'user', 'address', 'method'],
                'properties': {
                    'type': {'type': 'string'},
                    'database': {'type': 'string'},
                    'user': {'type': 'string'},
                    'address': {'type': 'string'},
                    'mask': {'type': 'string'},
                    'method': {'type': 'string'},
                    'priority': {'type': 'integer'}
                }
            }
        }
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        configs = self.data.get('configs', [])

        # Process only PostgreSQL instances
        if resource.get('datastore', {}).get('type', '').lower() != 'postgresql':
            self.log.warning(f"Instance {resource['name']}"
                             f" (ID: {instance_id}) is not a PostgreSQL instance, "
                             f"skipping modification of pg_hba.conf")
            return

        try:
            # Modify the pg_hba.conf file configuration
            # API Document: https://support.huaweicloud.com/api-rds/rds_11_0021.html
            request = ModifyPostgresqlHbaConfRequest()
            request.instance_id = instance_id
            request.body = configs

            response = client.modify_postgresql_hba_conf(request)
            self.log.info(f"Successfully modified RDS PostgreSQL instance {resource['name']}"
                          f" (ID: {instance_id})'s pg_hba.conf configuration")
            return response
        except Exception as e:
            self.log.error(f"Failed to modify RDS PostgreSQL instance {resource['name']}"
                           f" (ID: {instance_id})'s pg_hba.conf configuration: {e}")
            raise


@RDS.action_registry.register('enable-tde')
class EnableTDEAction(HuaweiCloudBaseAction):
    """Enable TDE (Transparent Data Encryption) feature for SQL Server instances

    :example:

    .. code-block:: yaml

        policies:
          - name: rds-enable-tde
            resource: huaweicloud.rds
            filters:
              - type: value
                key: datastore.type
                value: SQLServer
            actions:
              - type: enable-tde
    """
    schema = type_schema(
        'enable-tde',
        rotate_day={'type': 'integer', 'minimum': 1, 'maximum': 100000},
        secret_id={'type': 'string'},
        secret_name={'type': 'string'},
        secret_version={'type': 'string'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']

        # Check if it is a SQL Server instance
        if resource.get('datastore', {}).get('type', '').lower() != 'sqlserver':
            self.log.warning(f"Instance {resource['name']}"
                             f" (ID: {instance_id}) is not a SQL Server instance, "
                             f"skipping enabling TDE feature")
            return

        try:
            # Enable TDE feature
            # API Document: https://support.huaweicloud.com/api-rds/rds_06_0045.html
            # PUT /v3/{project_id}/instances/{instance_id}/tde
            request = UpdateTdeStatusRequest()
            request.instance_id = instance_id

            # If the TDE rotation feature is needed, add the corresponding parameters
            rotate_day = self.data.get('rotate_day')
            secret_id = self.data.get('secret_id')
            secret_name = self.data.get('secret_name')
            secret_version = self.data.get('secret_version')

            # Construct the request body, adding relevant parameters
            # only when using the rotation feature
            body = {}
            if rotate_day is not None:
                body['rotate_day'] = rotate_day
            if secret_id is not None:
                body['secret_id'] = secret_id
            if secret_name is not None:
                body['secret_name'] = secret_name
            if secret_version is not None:
                body['secret_version'] = secret_version

            request.body = body

            response = client.update_tde_status(request)
            self.log.info(f"Successfully enabled TDE feature for RDS SQL Server "
                          f"instance {resource['name']} (ID: {instance_id})")
            return response
        except Exception as e:
            self.log.error(f"Failed to enable TDE feature for RDS SQL Server "
                           f"instance {resource['name']} (ID: {instance_id}): {e}")
            raise
