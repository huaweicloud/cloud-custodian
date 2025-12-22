# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import logging
import uuid

from huaweicloudsdkaos.v1 import (UpdateStackRequestBody, UpdateStackRequest,
                                  GetStackMetadataRequest)

from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

log = logging.getLogger("custodian.huaweicloud.resources.rfs")


@resources.register('rfs-stack')
class Stack(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'rfs'
        resource_type_name = 'rfs-stack'
        tag_resource_type = ''
        enum_spec = ('list_stacks', 'stacks', 'marker')
        id = 'stack_id'

    def augment(self, resources):
        client = self.get_client()
        result = []
        for resource in resources:
            try:
                request = GetStackMetadataRequest(
                    client_request_id=str(uuid.uuid1()),
                    stack_name=resource['stack_name'],
                    stack_id=resource['id']
                )
                response = client.get_stack_metadata(request)
                resource = response.to_dict()
                resource['id'] = resource['stack_id']
                result.append(resource)
            except Exception as e:
                log.error(f"Failed to fetch full metadata for stack {resource['id']}: {e}")
                raise e
            # enable sleep here to prevent API rate limiting from cascading queries
            # when timer policy is supported later
            # time.sleep(random.uniform(0.1, 0.2))
        return result

    def get_resources(self, resource_ids):
        resources = (
                self.source.get_resources(self.get_resource_query()) or []
        )
        result = []
        for resource in resources:
            if resource["id"] in resource_ids:
                result.append(resource)
        result = self.augment(result)
        return result


@Stack.action_registry.register('enable_deletion_protection')
class EnableDeletionProtection(HuaweiCloudBaseAction):
    """Action to enable deletion protection for stack.

    :example

    .. code-block:: yaml

        policies:
            - name: enable-stack-deletion-protection
              resource: huaweicloud.rfs-stack
            filters:
              - type: value
                key: enable_deletion_protection
                value: false
            actions:
              - enable_deletion_protection
    """
    schema = type_schema('enable_deletion_protection')

    def perform_action(self, resource):
        client = self.manager.get_client()
        try:
            log.info(f"Start enable deletion protection for stack {resource['stack_id']}")
            request_body = UpdateStackRequestBody(
                enable_deletion_protection=True,
                stack_id=resource['stack_id']
            )
            request = UpdateStackRequest(
                client_request_id=str(uuid.uuid1()),
                stack_name=resource['stack_name'],
                body=request_body
            )
            client.update_stack(request)
            log.info(f"Successfully enable deletion protection for stack {resource['stack_id']}")
        except Exception as e:
            log.error(f"Failed to enable deletion protection for stack {resource['stack_id']}")
            raise e
