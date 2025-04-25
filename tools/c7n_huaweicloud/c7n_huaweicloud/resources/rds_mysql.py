# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import datetime
from c7n.filters import Filter, ValueFilter
from c7n.utils import type_schema, local_session
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.actions.tms import register_tms_actions
from c7n_huaweicloud.filters.tms import register_tms_filters
from c7n_huaweicloud.filters.vpc import SecurityGroupFilter, VpcFilter, SubnetFilter

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkrds.v3 import (
    ListInstancesRequest,
    DeleteInstanceRequest,
    StartInstanceRestartActionRequest,
    StartupInstanceRequest,
    StopInstanceRequest,
    CreateManualBackupRequest,
    CreateManualBackupRequestBody,
    ListDatabasesRequest,
    CreateDatabaseRequest,
    DeleteDatabaseRequest, 
    ListDbUsersRequest,
    CreateDbUserRequest,
    DeleteDbUserRequest,
    BatchTagActionAddRequestBody,
    BatchTagActionDelRequestBody,
    BatchTagAddActionRequest,
    BatchTagDelActionRequest
)
from huaweicloudsdkces.v1 import (
    BatchListMetricDataRequest,
    MetricsDimension,
    BatchListMetricDataRequestBody,
    BatchMetricData
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
    
    .. code-block:: yaml
    
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
        format used internally by Cloud Custodian (a list of dictionaries with 'Key' and 'Value' fields).
        This improves consistency of cross-cloud provider policies.
        
        :param resources: List of raw resource dictionaries from the API
        :return: List of enhanced resource dictionaries with tags converted to AWS-compatible format under the 'Tags' key
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
    
    .. code-block:: yaml
    
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
    
    .. code-block:: yaml
    
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
    
    .. code-block:: yaml
    
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
            log.error(f"Failed to delete RDS instance: {e.status_code}, {e.request_id}, {e.error_code}, {e.error_msg}")
            raise


@RDS.action_registry.register('start')
class RDSStart(HuaweiCloudBaseAction):
    """Start RDS instance.
    
    :example:
    
    .. code-block:: yaml
    
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
            log.error(f"Failed to start RDS instance: {e.status_code}, {e.request_id}, {e.error_code}, {e.error_msg}")
            raise


@RDS.action_registry.register('stop')
class RDSStop(HuaweiCloudBaseAction):
    """Stop RDS instance.
    
    :example:
    
    .. code-block:: yaml
    
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
            log.error(f"Failed to stop RDS instance: {e.status_code}, {e.request_id}, {e.error_code}, {e.error_msg}")
            raise


@RDS.action_registry.register('reboot')
class RDSReboot(HuaweiCloudBaseAction):
    """Reboot RDS instance.
    
    :example:
    
    .. code-block:: yaml
    
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
            log.error(f"Failed to restart RDS instance: {e.status_code}, {e.request_id}, {e.error_code}, {e.error_msg}")
            raise


@RDS.action_registry.register('snapshot')
class RDSSnapshot(HuaweiCloudBaseAction):
    """Create a manual backup (snapshot) of the RDS instance.
    
    :example:
    
    .. code-block:: yaml
    
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
            log.info(f"Successfully submitted request to create manual backup: {instance_id}, backup name: {backup_name}")
            return response
        except exceptions.ClientRequestException as e:
            log.error(f"Failed to create manual backup: {e.status_code}, {e.request_id}, {e.error_code}, {e.error_msg}")
            raise


# @resources.register('rds-mysql-database')
# class RDSMySQLDatabase(QueryResourceManager):
#     """Huawei Cloud RDS MySQL Database Resource Manager
#
#     This resource manager is specifically for MySQL database engines, not applicable to other database engines (like PostgreSQL, SQL Server, etc.).
#
#     :example:
#
#     .. code-block:: yaml
#
#         policies:
#           - name: rds-mysql-db-list
#             resource: huaweicloud.rds-mysql-database
#     """
#
#     class resource_type(TypeInfo):
#         service = 'rds'
#         enum_spec = ("list_databases", 'databases', 'page')
#         id = 'name'  # Database name as ID
#         name = 'name'
#         tag = False  # MySQL databases don't support tags
#
#     def resources(self, query=None):
#         """Override resources method to first get all RDS instances with MySQL engine, then query databases for each instance
#
#         First get all RDS instance IDs through the RDS resource manager, then filter out for MySQL engine instances,
#         finally iterate through these instances to query databases in each instance, using pagination to get all database lists.
#         """
#         # Create an RDS resource manager instance
#         rds_manager = RDS(self.ctx, self.data)
#
#         # Get all RDS instances
#         rds_instances = rds_manager.resources()
#
#         if not rds_instances:
#             self.log.warning("No RDS instances found")
#             return []
#
#         # Filter for MySQL engine instances
#         mysql_instances = []
#         for instance in rds_instances:
#             # Check instance database engine type
#             db_engine = instance.get('datastore', {}).get('type', '').lower()
#             if db_engine == 'mysql':
#                 mysql_instances.append(instance)
#
#         if not mysql_instances:
#             self.log.warning("No MySQL engine RDS instances found")
#             return []
#
#         self.log.info(f"Found {len(mysql_instances)} MySQL engine RDS instances")
#
#         # Get RDS client
#         client = self.get_client()
#
#         # Store databases from all instances
#         all_databases = []
#
#         # Set number of items per page
#         page_limit = 100
#
#         # Iterate through each MySQL instance to query its databases
#         for instance in mysql_instances:
#             instance_id = instance['id']
#             current_page = 1
#             total_count = 0
#
#             try:
#                 while True:
#                     # Create query database request, using pagination parameters
#                     request = ListDatabasesRequest(
#                         instance_id=instance_id,
#                         page=current_page,
#                         limit=page_limit
#                     )
#
#                     response = client.list_databases(request)
#
#                     # Get database list
#                     if hasattr(response, 'databases') and response.databases:
#                         # Get total count on first query
#                         if current_page == 1 and hasattr(response, 'total_count'):
#                             total_count = response.total_count
#                             self.log.info(f"MySQL instance {instance_id} ({instance.get('name', '')}) has {total_count} databases")
#
#                         # Add instance ID to each database for later use
#                         for db in response.databases:
#                             # Use vars() function to get object's attribute dictionary, if not available try to_dict() method
#                             if hasattr(db, 'to_dict'):
#                                 db_dict = db.to_dict()
#                             else:
#                                 # Manually create dictionary with necessary attributes
#                                 db_dict = {}
#                                 # Get common database attributes
#                                 for attr in ['name', 'character_set', 'status', 'created', 'updated']:
#                                     if hasattr(db, attr):
#                                         db_dict[attr] = getattr(db, attr)
#
#                             db_dict['instance_id'] = instance_id
#                             db_dict['instance_name'] = instance.get('name', '')
#                             db_dict['db_engine'] = 'mysql'  # Mark database engine as MySQL
#                             all_databases.append(db_dict)
#
#                         self.log.info(f"MySQL instance {instance_id} ({instance.get('name', '')}) currently getting page {current_page}, with {len(response.databases)} databases")
#
#                         # Determine if need to get next page
#                         if total_count > current_page * page_limit:
#                             current_page += 1
#                         else:
#                             # Got all data, exit loop
#                             break
#                     else:
#                         self.log.info(f"No databases found in MySQL instance {instance_id} ({instance.get('name', '')})")
#                         break
#
#             except exceptions.ClientRequestException as e:
#                 self.log.error(f"Failed to query databases for MySQL instance {instance_id}: {e.status_code}, {e.request_id}, {e.error_code}, {e.error_msg}")
#
#         self.log.info(f"Total found {len(all_databases)} MySQL databases")
#         return all_databases
#
#
# @RDSMySQLDatabase.action_registry.register('create')
# class RDSMySQLDatabaseCreate(HuaweiCloudBaseAction):
#     """Create MySQL database.
#
#     Note: This operation is only applicable to RDS instances with MySQL database engine, not applicable to other types of database engines.
#     This operation requires instance ID and database name.
#
#     :example:
#
#     .. code-block:: yaml
#
#         policies:
#           - name: create-mysql-db
#             resource: huaweicloud.rds
#             filters:
#               - type: value
#                 key: datastore.type
#                 value: MySQL
#             actions:
#               - type: create-database
#                 database_name: new_database
#                 character_set: utf8
#     """
#
#     schema = type_schema(
#         'create',
#         required=['database_name'],
#         database_name={'type': 'string'},
#         character_set={'type': 'string', 'default': 'utf8'}
#     )
#     permissions = ('rds:CreateDatabase',)
#
#     def process(self, resources):
#         client = self.manager.get_client()
#
#         database_name = self.data['database_name']
#         character_set = self.data.get('character_set', 'utf8')
#
#         # Filter for MySQL engine instances
#         mysql_resources = []
#         for resource in resources:
#             # Check instance database engine type
#             db_engine = resource.get('datastore', {}).get('type', '').lower()
#             if db_engine == 'mysql':
#                 mysql_resources.append(resource)
#
#         if not mysql_resources:
#             self.log.warning("No MySQL engine RDS instances found, skipping database creation")
#             return
#
#         self.log.info(f"Will create database in {len(mysql_resources)} MySQL instances")
#
#         for resource in mysql_resources:
#             instance_id = resource['id']
#             self.create_database(client, instance_id, database_name, character_set)
#
#     def create_database(self, client, instance_id, database_name, character_set):
#         request = CreateDatabaseRequest(instance_id=instance_id)
#         request.body = {"name": database_name, "character_set": character_set}
#
#         try:
#             response = client.create_database(request)
#             log.info(f"Successfully created MySQL database: Instance ID={instance_id}, Database name={database_name}")
#             return response
#         except exceptions.ClientRequestException as e:
#             log.error(f"Failed to create MySQL database: {e.status_code}, {e.request_id}, {e.error_code}, {e.error_msg}")
#             raise
#
#     def perform_action(self, resource):
#         # This method is called when processing a single resource
#         # Ensure to only perform operation on MySQL instances
#         db_engine = resource.get('datastore', {}).get('type', '').lower()
#         if db_engine != 'mysql':
#             self.log.info(f"Skipping non-MySQL instance: {resource.get('id')}, engine type: {db_engine}")
#             return
#
#         # Use generic method to create database
#         client = self.manager.get_client()
#         database_name = self.data['database_name']
#         character_set = self.data.get('character_set', 'utf8')
#         self.create_database(client, resource['id'], database_name, character_set)
#
#
# @RDSMySQLDatabase.action_registry.register('delete')
# class RDSMySQLDatabaseDelete(HuaweiCloudBaseAction):
#     """Delete MySQL database.
#
#     Note: This operation is only applicable to databases in RDS instances with MySQL database engine, not applicable to other types of database engines.
#
#     :example:
#
#     .. code-block:: yaml
#
#         policies:
#           - name: delete-test-db
#             resource: huaweicloud.rds-mysql-database
#             filters:
#               - type: value
#                 key: name
#                 value: test_db
#             actions:
#               - delete
#     """
#
#     schema = type_schema('delete')
#     permissions = ('rds:DeleteDatabase',)
#
#     def perform_action(self, resource):
#         # Ensure to only process MySQL engine databases
#         db_engine = resource.get('db_engine', '').lower()
#         if db_engine != 'mysql':
#             log.info(f"Skipping non-MySQL database: {resource.get('name')}, Instance ID: {resource.get('instance_id')}")
#             return
#
#         client = self.manager.get_client()
#         instance_id = resource['instance_id']
#         db_name = resource['name']
#
#         request = DeleteDatabaseRequest(instance_id=instance_id, db_name=db_name)
#         try:
#             response = client.delete_database(request)
#             log.info(f"Successfully deleted MySQL database: Instance ID={instance_id}, Database name={db_name}")
#             return response
#         except exceptions.ClientRequestException as e:
#             log.error(f"Failed to delete MySQL database: {e.status_code}, {e.request_id}, {e.error_code}, {e.error_msg}")
#             raise
#
#
# @resources.register('rds-mysql-user')
# class RDSMySQLUser(QueryResourceManager):
#     """Huawei Cloud RDS MySQL Database User Resource Manager
#
#     This resource manager is specifically for MySQL database engine user management, not applicable to other database engines (like PostgreSQL, SQL Server, etc.).
#
#     :example:
#
#     .. code-block:: yaml
#
#         policies:
#           - name: rds-mysql-user-list
#             resource: huaweicloud.rds-mysql-user
#     """
#
#     class resource_type(TypeInfo):
#         service = 'rds'
#         enum_spec = ("list_db_users", 'users', 'page')
#         id = 'name'  # Username as ID
#         name = 'name'
#         tag = False  # MySQL users don't support tags
#
#     def resources(self, query=None):
#         """Override resources method to first get all RDS instances with MySQL engine, then query users for each instance
#
#         First get all RDS instance IDs through the RDS resource manager, then filter out for MySQL engine instances,
#         finally iterate through these instances to query database users in each instance, using pagination to get all user lists.
#
#         Reference API: https://support.huaweicloud.com/intl/zh-cn/api-rds/rds_06_0032.html
#         URI: GET /v3/{project_id}/instances/{instance_id}/db_user/detail?page={page}&limit={limit}
#         """
#         # Create an RDS resource manager instance
#         rds_manager = RDS(self.ctx, self.data)
#
#         # Get all RDS instances
#         rds_instances = rds_manager.resources()
#
#         if not rds_instances:
#             self.log.warning("No RDS instances found")
#             return []
#
#         # Filter for MySQL engine instances
#         mysql_instances = []
#         for instance in rds_instances:
#             # Check instance database engine type
#             db_engine = instance.get('datastore', {}).get('type', '').lower()
#             if db_engine == 'mysql':
#                 mysql_instances.append(instance)
#
#         if not mysql_instances:
#             self.log.warning("No MySQL engine RDS instances found")
#             return []
#
#         self.log.info(f"Found {len(mysql_instances)} MySQL engine RDS instances")
#
#         # Get RDS client
#         client = self.get_client()
#
#         # Store users from all instances
#         all_users = []
#
#         # Set number of items per page (API limit is 1-100)
#         page_limit = 100
#
#         # Iterate through each MySQL instance to query its users
#         for instance in mysql_instances:
#             instance_id = instance['id']
#             instance_name = instance.get('name', '')
#
#             try:
#                 # Start querying from page 1
#                 page = 1
#                 while True:
#                     # Create user query request - set page and limit parameters as per API document requirements
#                     request = ListDbUsersRequest(
#                         instance_id=instance_id,
#                         page=page,
#                         limit=page_limit
#                     )
#
#                     # Send request and get response
#                     response = client.list_db_users(request)
#
#                     # Process response - get total_count and users list
#                     total_count = getattr(response, 'total_count', 0)
#                     users_list = getattr(response, 'users', [])
#
#                     # Record total count on first page
#                     if page == 1:
#                         self.log.info(f"MySQL instance {instance_id} ({instance_name}) has {total_count} users")
#
#                     # If no users, break the loop
#                     if not users_list:
#                         if page == 1:
#                             self.log.info(f"No users found in MySQL instance {instance_id} ({instance_name})")
#                         break
#
#                     # Process current page's user data
#                     for user in users_list:
#                         # Convert user object to dictionary
#                         if hasattr(user, 'to_dict'):
#                             user_dict = user.to_dict()
#                         else:
#                             # Manually build user dictionary
#                             user_dict = {
#                                 'name': getattr(user, 'name', ''),
#                                 'comment': getattr(user, 'comment', ''),
#                                 'hosts': getattr(user, 'hosts', [])
#                             }
#
#                             # Process database permissions list
#                             if hasattr(user, 'databases') and user.databases:
#                                 user_dict['databases'] = []
#                                 for db in user.databases:
#                                     if hasattr(db, 'to_dict'):
#                                         user_dict['databases'].append(db.to_dict())
#                                     else:
#                                         db_dict = {
#                                             'name': getattr(db, 'name', ''),
#                                             'readonly': getattr(db, 'readonly', False)
#                                         }
#                                         user_dict['databases'].append(db_dict)
#                             else:
#                                 user_dict['databases'] = []
#
#                         # Add instance information
#                         user_dict['instance_id'] = instance_id
#                         user_dict['instance_name'] = instance_name
#                         user_dict['db_engine'] = 'mysql'
#
#                         # Add to result list
#                         all_users.append(user_dict)
#
#                     self.log.info(f"MySQL instance {instance_id} ({instance_name}) getting page {page}, with {len(users_list)} users")
#
#                     # Determine if need to get next page based on total_count
#                     if total_count > page * page_limit:
#                         page += 1
#                     else:
#                         # Got all data, exit loop
#                         break
#
#             except exceptions.ClientRequestException as e:
#                 self.log.error(f"Failed to query users for MySQL instance {instance_id}: {e.status_code}, {e.request_id}, {e.error_code}, {e.error_msg}")
#
#         self.log.info(f"Total found {len(all_users)} MySQL users")
#         return all_users
#
#
# @RDSMySQLUser.filter_registry.register('instance-id')
# class RDSMySQLUserInstanceFilter(ValueFilter):
#     """Filter MySQL users by RDS instance ID
#
#     This filter is only applicable to users in RDS instances with MySQL database engine.
#
#     :example:
#
#     .. code-block:: yaml
#
#         policies:
#           - name: mysql-users-in-prod-instance
#             resource: huaweicloud.rds-mysql-user
#             filters:
#               - type: instance-id
#                 value: 97b026aa-000c-4866-b5b6-2298019a4e3a
#     """
#
#     schema = type_schema('instance-id', rinherit=ValueFilter.schema)
#     schema_alias = True
#
#     def process(self, resources, event=None):
#         # First filter out users belonging to MySQL engine
#         mysql_resources = [r for r in resources if r.get('db_engine', '').lower() == 'mysql']
#         if not mysql_resources:
#             self.log.warning("No MySQL engine users found, cannot apply instance ID filter")
#             return []
#
#         # Then filter by instance ID
#         matched = [r for r in mysql_resources if self.match(r.get('instance_id'))]
#         return matched
#
#
# @RDSMySQLUser.action_registry.register('create')
# class RDSMySQLUserCreate(HuaweiCloudBaseAction):
#     """Create MySQL database user
#
#     Note: This operation is only applicable to RDS instances with MySQL database engine, not applicable to other types of database engines.
#     This operation requires instance ID, username and password.
#
#     :example:
#
#     .. code-block:: yaml
#
#         policies:
#           - name: create-mysql-user
#             resource: huaweicloud.rds
#             filters:
#               - type: value
#                 key: datastore.type
#                 value: MySQL
#             actions:
#               - type: create-user
#                 username: new_user
#                 password: Strong_Password123!
#     """
#
#     schema = type_schema(
#         'create',
#         required=['username', 'password'],
#         username={'type': 'string'},
#         password={'type': 'string'}
#     )
#     permissions = ('rds:CreateDbUser',)
#
#     def process(self, resources):
#         client = self.manager.get_client()
#
#         username = self.data['username']
#         password = self.data['password']
#
#         # Filter for MySQL engine instances
#         mysql_resources = []
#         for resource in resources:
#             # Check instance database engine type
#             db_engine = resource.get('datastore', {}).get('type', '').lower()
#             if db_engine == 'mysql':
#                 mysql_resources.append(resource)
#
#         if not mysql_resources:
#             self.log.warning("No MySQL engine RDS instances found, skipping user creation")
#             return
#
#         self.log.info(f"Will create user in {len(mysql_resources)} MySQL instances")
#
#         for resource in mysql_resources:
#             instance_id = resource['id']
#             self.create_user(client, instance_id, username, password)
#
#     def create_user(self, client, instance_id, username, password):
#         request = CreateDbUserRequest(instance_id=instance_id)
#         request.body = {"name": username, "password": password}
#
#         try:
#             response = client.create_db_user(request)
#             log.info(f"Successfully created MySQL user: Instance ID={instance_id}, Username={username}")
#             return response
#         except exceptions.ClientRequestException as e:
#             log.error(f"Failed to create MySQL user: {e.status_code}, {e.request_id}, {e.error_code}, {e.error_msg}")
#             raise
#
#     def perform_action(self, resource):
#         # Ensure to only perform operation on MySQL instances
#         db_engine = resource.get('datastore', {}).get('type', '').lower()
#         if db_engine != 'mysql':
#             self.log.info(f"Skipping non-MySQL instance: {resource.get('id')}, engine type: {db_engine}")
#             return
#
#         # Use generic method to create user
#         client = self.manager.get_client()
#         username = self.data['username']
#         password = self.data['password']
#         self.create_user(client, resource['id'], username, password)
#
#
# @RDSMySQLUser.action_registry.register('delete')
# class RDSMySQLUserDelete(HuaweiCloudBaseAction):
#     """Delete MySQL database user
#
#     Note: This operation is only applicable to users in RDS instances with MySQL database engine, not applicable to other types of database engines.
#
#     :example:
#
#     .. code-block:: yaml
#
#         policies:
#           - name: delete-test-user
#             resource: huaweicloud.rds-mysql-user
#             filters:
#               - type: value
#                 key: name
#                 value: test_user
#             actions:
#               - delete
#     """
#
#     schema = type_schema('delete')
#     permissions = ('rds:DeleteDbUser',)
#
#     def perform_action(self, resource):
#         # Ensure to only process MySQL engine users
#         db_engine = resource.get('db_engine', '').lower()
#         if db_engine != 'mysql':
#             log.info(f"Skipping non-MySQL user: {resource.get('name')}, Instance ID: {resource.get('instance_id')}")
#             return
#
#         client = self.manager.get_client()
#         instance_id = resource['instance_id']
#         user_name = resource['name']
#
#         request = DeleteDbUserRequest(instance_id=instance_id, user_name=user_name)
#         try:
#             response = client.delete_db_user(request)
#             log.info(f"Successfully deleted MySQL user: Instance ID={instance_id}, Username={user_name}")
#             return response
#         except exceptions.ClientRequestException as e:
#             log.error(f"Failed to delete MySQL user: {e.status_code}, {e.request_id}, {e.error_code}, {e.error_msg}")
#             raise
