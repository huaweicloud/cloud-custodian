# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import math
from time import sleep

from c7n.filters import Filter
from c7n.filters.core import type_schema
from c7n.utils import local_session
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

from huaweicloudsdkgaussdbfornosql.v3 import (
    ShowBackupPoliciesRequest, SetBackupPolicyRequest,
    SetBackupPolicyRequestBody, BackupPolicy,
    ListInstancesByTagsRequest
)
from huaweicloudsdkcore.exceptions import exceptions

log = logging.getLogger("custodian.huaweicloud.resources.geminidb")


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


@resources.register('geminidb')
class GeminiDB(QueryResourceManager):
    """Huawei Cloud GeminiDB Resource Manager

    Used to manage instances in the Huawei Cloud GeminiDB.

    :example:

    .. code-block:: yaml

        policies:
          - name: geminidb-instance-list
            resource: huaweicloud.geminidb
            filters:
              - type: value
                key: status
                value: ACTIVE
    """

    class resource_type(TypeInfo):
        service = 'geminidb'
        enum_spec = ('list_instances', 'instances', 'offset')
        id = 'id'
        name = 'name'
        filter_name = 'id'
        filter_type = 'scalar'
        date = 'created'
        taggable = True
        tag_resource_type = 'nosql'

    def get_resources(self, resource_ids):
        resources = self.augment_tags(self.source.get_resources(self.get_resource_query())) or []
        result = []
        for resource in resources:
            if resource["id"] in resource_ids:
                result.append(resource)
        return result

    def _fetch_resources(self, query):
        return self.augment_tags(self.source.get_resources(self.get_resource_query())) or []

    def augment_tags(self, resources):
        if not resources:
            return resources

        resources_and_tag = self.get_resources_and_tag()
        instance_id_to_tags_map = {
            item.instance_id: [{"key": tag.key, "value": tag.value} for tag in item.tags or []]
            for item in resources_and_tag
        }

        for resource in resources:
            if "tags" not in resource:
                instance_id = resource["id"]
                tags_of_instance = instance_id_to_tags_map.get(instance_id, [])
                resource["tags"] = tags_of_instance

        return resources

    def get_resources_and_tag(self):
        client = local_session(self.session_factory).client('geminidb')
        count_req = ListInstancesByTagsRequest()
        count_req.body = {
            "action": 'count'
        }
        count_rsp = client.list_instances_by_tags(count_req)
        total_count = count_rsp.total_count

        LIMIT = 100
        total_page = math.ceil(total_count / LIMIT)
        all_instances_with_tags = []

        for i in range(total_page):
            offset = i * LIMIT
            req = ListInstancesByTagsRequest()
            try:
                req.body = {
                    "limit": LIMIT,
                    "offset": offset,
                    "action": 'filter'
                }
                rsp = client.list_instances_by_tags(req)
                instances = rsp.instances

                all_instances_with_tags.extend(instances)
            except Exception as e:
                log.error(
                    f"[query resources with tags failed, req: [{req}] "
                    f"cause:{e}")
                raise

        self.log.info(f"Successfully get resources_with_tags"
                      f"{all_instances_with_tags}")
        return all_instances_with_tags


@GeminiDB.filter_registry.register('geminidb-list')
class GeminiDBListFilter(Filter):
    """Filter GeminiDB instances by specific instance IDs
    :example:
    .. code-block:: yaml
        policies:
          - name: geminidb-list-filter
            resource: huaweicloud.geminidb
            filters:
              - type: geminidb-list
                ids:
                  - 14f18a0c58e54c658896bf6e5160d343in06
                  - 90573dba4db7466bb7f26d7034b74befin06
    """
    schema = type_schema(
        'geminidb-list',
        ids={'type': 'array', 'items': {'type': 'string'}}
    )

    def process(self, resources, event=None):
        ids = self.data.get('ids', [])
        if not ids:
            return resources
        return [r for r in resources if r['id'] in ids]


@GeminiDB.filter_registry.register('backup-policy-disabled')
class BackupPolicyDisabledFilter(Filter):
    """Filter GeminiDB instances that do not have an auto backup policy enabled

    :example:

    .. code-block:: yaml

        policies:
          - name: geminidb-backup-policy-disabled
            resource: huaweicloud.geminidb
            filters:
              - type: backup-policy-disabled
    """
    schema = type_schema('backup-policy-disabled')

    def process(self, resources, event=None):
        client = local_session(self.manager.session_factory).client("geminidb")
        matched_resources = []
        invoke_count = 0
        invoke_count_batch = 10

        for resource in resources:
            instance_id = resource['id']
            instance_status = resource['status']
            instance_actions = resource['actions']

            if (instance_status in ['creating', 'createfail', 'abnormal']
                    or len(instance_actions) > 0):
                continue

            try:
                # Query instance backup policy
                # API Document: https://support.huaweicloud.com/intl/zh-cn/api-nosql/nosql_api_0030.html
                # GET /v3.1/{project_id}/instances/{instance_id}/backups/policies
                request = ShowBackupPoliciesRequest()
                request.instance_id = instance_id
                response = client.show_backup_policies(request)

                # Check if auto backup is enabled
                # If keep_days is 0, it is considered that auto backup is not enabled
                keep_days = response.backup_policy.keep_days

                if keep_days == 0:
                    matched_resources.append(resource)

                # When API invocation count reaches batch size,
                # reset invocation count to 0 and sleep 30 seconds to avoid API throttling
                if invoke_count >= invoke_count_batch:
                    invoke_count = 0
                    sleep(30)
            except Exception as e:
                self.log.error(
                    f"Failed to get backup policy for GeminiDB instance "
                    f"{resource['name']} (ID: {instance_id}): {e}")
                raise
            finally:
                # Increase API invocation count by 1
                invoke_count = invoke_count + 1

        return matched_resources


@GeminiDB.action_registry.register('set-backup-policy')
class SetBackupPolicyAction(HuaweiCloudBaseAction):
    """Set the auto backup policy for the GeminiDB instance

    :example:

    .. code-block:: yaml

        policies:
          - name: geminidb-enable-backup
            resource: huaweicloud.geminidb
            filters:
              - type: backup-policy-disabled
            actions:
              - type: set-backup-policy
                keep_days: 7
                start_time: "01:00-02:00"
                period: "1,2,3,4,5,6,7"
    """
    schema = type_schema(
        'set-backup-policy',
        required=['keep_days', 'start_time', 'period'],
        keep_days={'type': 'integer', 'minimum': 1, 'maximum': 3660},
        start_time={'type': 'string'},
        period={'type': 'string'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']
        keep_days = self.data['keep_days']
        start_time = self.data['start_time']
        period = self.data['period']

        try:
            # Set backup policy
            # API Document: https://support.huaweicloud.com/intl/zh-cn/api-nosql/nosql_api_0031.html
            # PUT /v3/{project_id}/instances/{instance_id}/backups/policy
            request = SetBackupPolicyRequest()
            request.instance_id = instance_id

            backupPolicyBody = BackupPolicy(keep_days=keep_days,
                                            start_time=start_time,
                                            period=period)

            # Construct the request body
            request_body = SetBackupPolicyRequestBody(
                backup_policy=backupPolicyBody
            )
            request.body = request_body

            response = client.set_backup_policy(request)
            self.log.info(f"Successfully set auto backup policy for GeminiDB instance "
                          f"{resource['name']} (ID: {instance_id})")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to set auto backup policy for GeminiDB instance "
                f"{resource['name']} (ID: {instance_id}): {e}")
            raise


@GeminiDB.filter_registry.register('multi-availability-zone-deployment-disabled')
class MultiAzDeploymentDisabledFilter(Filter):
    """Filter GeminiDB instances that do not deploy in multiple availability zones

    :example:

    .. code-block:: yaml

        policies:
          - name: multi-availability-zone-deployment-disabled
            resource: huaweicloud.geminidb
            filters:
              - type: multi-availability-zone-deployment-disabled
    """
    schema = type_schema('multi-availability-zone-deployment-disabled')

    def process(self, resources, event=None):
        matched_resources = []

        for resource in resources:
            instance_id = resource['id']
            instance_status = resource['status']
            instance_availability_zone = resource['availability_zone']

            if instance_status in ['creating', 'createfail']:
                continue

            try:
                availability_zones = instance_availability_zone.split(',')
                unique_availability_zones = set(availability_zones)
                if len(unique_availability_zones) == 1:
                    matched_resources.append(resource)
            except Exception as e:
                self.log.error(
                    f"Failed to get availability zone for GeminiDB instance "
                    f"{resource['name']} (ID: {instance_id}): {e}")
                raise

        return matched_resources
