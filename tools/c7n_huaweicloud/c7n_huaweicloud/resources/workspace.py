# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from c7n.filters import Filter
from c7n.utils import type_schema, local_session

from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, ResourceManager, TypeInfo
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from huaweicloudsdkworkspace.v2 import BatchDeleteDesktopsRequest, SetUserEventsLtsConfigurationsRequest, \
    SetUserEventsLtsConfigurationsRequestBody

log = logging.getLogger('custodian.huaweicloud.workspace')


@resources.register('workspace-desktop')
class Workspace(QueryResourceManager):
    """Huawei Cloud Workspace Resource Manager

    This resource type manages cloud desktop instances in Huawei Cloud Workspace service.
    """

    class resource_type(TypeInfo):
        service = 'workspace'
        enum_spec = ('list_desktops_detail', 'desktops', 'offset')
        id = 'desktop_id'
        name = 'computer_name'
        tag_resource_type = 'workspace-desktop'
        date = 'created'

    def augment(self, resources):
        """Enhance resource data

        This method ensures each resource has a valid ID field and adds additional
        information as needed.

        :param resources: List of resource objects
        :return: Enhanced resource object list
        """
        for r in resources:
            # Ensure each resource has an ID field
            if 'id' not in r and self.resource_type.id in r:
                r['id'] = r[self.resource_type.id]

            # Convert tags to standard format
            if 'tags' in r:
                r['Tags'] = self.normalize_tags(r['tags'])

        return resources

    def normalize_tags(self, tags):
        """Convert tags to standard format

        :param tags: Original tag data
        :return: Normalized tag dictionary
        """
        if not tags:
            return {}

        if isinstance(tags, dict):
            return tags

        normalized = {}
        for tag in tags:
            if isinstance(tag, dict):
                if 'key' in tag and 'value' in tag:
                    normalized[tag['key']] = tag['value']
                else:
                    for k, v in tag.items():
                        normalized[k] = v
            elif isinstance(tag, str) and '=' in tag:
                k, v = tag.split('=', 1)
                normalized[k] = v

        return normalized


@Workspace.filter_registry.register('connection-status')
class ConnectionStatusFilter(Filter):
    """Filter desktops based on user connection information

    :example:

    .. code-block:: yaml

        policies:
          - name: find-unregister-desktops
            resource: huaweicloud.workspace-desktop
            filters:
              - type: connection-status
                op: eq
                value: UNREGISTER
    """
    schema = {
        'type': 'object',
        'properties': {
            'type': {'enum': ['connection-status']},
            'op': {'enum': ['eq', 'ne', 'in', 'not-in']},
            'value': {'oneOf': [{'type': 'string'}, {'type': 'array', 'items': {'type': 'string'}}]}
        },
        'required': ['type', 'op', 'value']
    }
    schema_alias = False
    annotation_key = 'c7n:ConnectionStatus'

    def process(self, resources, event=None):
        op = self.data.get('op')
        expected = self.data.get('value')

        results = []
        for r in resources:
            login_status = r.get('login_status')

            if login_status is None:
                continue

            if op == 'eq' and login_status == expected:
                results.append(r)
            elif op == 'ne' and login_status != expected:
                results.append(r)
            elif op == 'in' and login_status in expected:
                results.append(r)
            elif op == 'not-in' and login_status not in expected:
                results.append(r)

        return results


@Workspace.action_registry.register('delete')
class DeleteWorkspace(HuaweiCloudBaseAction):
    """Delete cloud desktops

    This action uses BatchDeleteDesktops API to delete one or more cloud desktop instances.

    :example:

    .. code-block:: yaml

        policies:
          - name: delete-workspace-desktop
            resource: huaweicloud.workspace-desktop
            filters:
              - type: tag-count
                count: 2
            actions:
              - delete
    """

    schema = type_schema('delete')

    def process(self, resources):
        """Process resources in batch

        :param resources: List of resources to process
        :return: Operation results
        """
        if not resources:
            return []

        return self.batch_delete(resources)

    def batch_delete(self, resources):
        """Delete cloud desktops in batch

        :param resources: List of resources
        :return: Operation results
        """
        session = local_session(self.manager.session_factory)
        client = session.client('workspace')

        # Extract desktop IDs
        desktop_ids = [r['id'] for r in resources]

        # Process up to 100 at a time
        results = []
        for i in range(0, len(desktop_ids), 100):
            batch = desktop_ids[i:i + 100]
            try:
                request = BatchDeleteDesktopsRequest()
                request.body = {"desktop_ids": batch}
                response = client.batch_delete_desktops(request)
                results.append(response.to_dict())
                self.log.info(f"Successfully submitted delete request for {len(batch)} desktops")
            except Exception as e:
                self.log.error(f"Failed to delete desktops: {e}")

        return results

    def perform_action(self, resource):
        return super().perform_action(resource)


@resources.register('workspace-user-event-lts-status')
class WorkspaceUserEventLtsStatus(ResourceManager):
    class resource_type(TypeInfo):
        id = 'id'
        name = 'status'

    def resources(self, query=None):

        session = local_session(self.session_factory)
        client = session.client('workspace')

        try:
            request = ListUserEventsLtsConfigurationsRequest()
            response = client.list_user_events_lts_configurations(request)

            enable_status = getattr(response, 'enable', False)
            log_group_id = getattr(response, 'log_group_id', None)
            log_stream_id = getattr(response, 'log_stream_id', None)

            status_resource = {
                'id': 'workspace-user-event-lts-status-singleton',
                'status': 'enabled' if enable_status else 'disabled',
                'enable': enable_status,
                'log_group_id': log_group_id,
                'log_stream_id': log_stream_id,
            }

            return [status_resource]

        except Exception as e:
            self.log.error(f"Failed to fetch Workspace User Event LTS status: {e}")
            return []


@WorkspaceUserEventLtsStatus.action_registry.register('enable-user-event-lts')
class EnableUserEventLts(HuaweiCloudBaseAction):
    schema = {
        'type': 'object',
        'properties': {
            'type': {'enum': ['enable-user-event-lts']},
            'log_group_id': {'type': 'string'},
            'log_stream_id': {'type': 'string'},
        },
        'required': ['type', 'log_group_id', 'log_stream_id']
    }

    def process(self, resources):
        for r in resources:
            self.perform_action(r)
        return []

    def perform_action(self, resource):
        session = local_session(self.manager.session_factory)
        client = session.client('workspace')

        if resource.get('enable') is True:
            self.log.info(f"Skipping resource {resource.get('id')}: LTS already enabled.")
            return

        enable_value = True
        log_group_id = self.data.get('log_group_id') or resource.get('log_group_id')
        log_stream_id = self.data.get('log_stream_id') or resource.get('log_stream_id')

        if not log_group_id or not log_stream_id:
            raise Exception("log_group_id and log_stream_id must be provided.")

        request_body_model = SetUserEventsLtsConfigurationsRequestBody(
            enable=enable_value,
            log_group_id=log_group_id,
            log_stream_id=log_stream_id
        )

        request = SetUserEventsLtsConfigurationsRequest(body=request_body_model)
        response = client.set_user_events_lts_configurations(request)

        self.log.info(f"Successfully submitted set user event LTS configuration.")