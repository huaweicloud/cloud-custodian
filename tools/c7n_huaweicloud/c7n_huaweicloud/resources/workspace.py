# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from c7n.filters import Filter
from c7n.utils import type_schema, local_session

from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from huaweicloudsdkworkspace.v2 import BatchDeleteDesktopsRequest, SetUserEventsLtsConfigurationsRequest, \
    SetUserEventsLtsConfigurationsRequestBody, ListUserEventsLtsConfigurationsRequest, ListPolicyDetailInfoByIdRequest, \
    UpdatePolicyGroupRequest, ModifyPolicyGroupRequest, PolicyGroupForUpdate
from huaweicloudsdklts.v2 import ListLogGroupsRequest, ListLogStreamRequest

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
class WorkspaceUserEventLtsStatus(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'workspace'
        enum_spec = ('list_user_events_lts_configurations', None, None)
        id = 'id'
        name = 'status'

    def resources(self, query=None):

        session = local_session(self.session_factory)
        client = session.client('workspace')

        try:
            request = ListUserEventsLtsConfigurationsRequest()
            response = client.list_user_events_lts_configurations(request)

            enable_status = getattr(response, 'enable', None)
            log_group_id = getattr(response, 'log_group_id', None)
            log_stream_id = getattr(response, 'log_stream_id', None)
            self.log.info(
                f"Fetched user events lts config: enable={enable_status}, log_group_id={log_group_id}, "
                f"log_stream_id={log_stream_id}")
            status_resource = {
                'id': 'Workspace',
                'status': 'enabled' if enable_status else 'disabled',
                'enable': enable_status,
                'log_group_id': log_group_id,
                'log_stream_id': log_stream_id,
            }

            return [status_resource]

        except Exception as e:
            self.log.error(f"Failed to fetch Workspace User Event LTS status: {e}")
            return []

    def get_resources(self, resource_ids):

        all_resources = self.resources()

        resource_map = {resource['id']: resource for resource in all_resources}

        found_resources = []
        for rid in resource_ids:
            if rid in resource_map:
                found_resources.append(resource_map[rid])
            else:
                self.log.warning(f"Resource ID '{rid}' not found for type '{self.type}'. Skipping.")

        return found_resources


@WorkspaceUserEventLtsStatus.action_registry.register('enable-user-event-lts')
class EnableUserEventLts(HuaweiCloudBaseAction):
    """Enable LTS for user events in workspace.

    This action updates the user event LTS status.

    :example:

    .. code-block:: yaml

        policies:
            - name: test-enable-workspace-user-event-lts
            resource: huaweicloud.workspace-user-event-lts-status
            filters:
              - type: value
              key: "enable"
              value: false
              op: eq
            actions:
              - type: enable-user-event-lts
                log_group_name: "lts-group-7eht"
                log_stream_name: "lts-topic-7ehu"
    """

    schema = {
        'type': 'object',
        'properties': {
            'type': {'enum': ['enable-user-event-lts']},
            'log_group_name': {'type': 'string'},
            'log_stream_name': {'type': 'string'},
        },
        'required': ['type', 'log_group_name', 'log_stream_name']
    }

    def process(self, resources):
        session = local_session(self.manager.session_factory)
        lts_client = session.client('lts-stream')

        log_group_name = self.data.get('log_group_name')
        log_stream_name = self.data.get('log_stream_name')

        log_group_id = self._get_log_group_id_by_name(lts_client, log_group_name)
        if not log_group_id:
            self.log.error(f"Log group with name '{log_group_name}' not found.")
            raise Exception(f"Log group name '{log_group_name}' does not find")

        log_stream_id = self._get_log_stream_id_by_name(lts_client, log_group_id, log_stream_name)
        if not log_stream_id:
            self.log.error(f"Log stream with name '{log_stream_name}' not found "
                           f"in log group '{log_group_name}'.")
            raise Exception(f"Log stream name '{log_stream_name}' does not find")

        self.resolved_log_group_id = log_group_id
        self.resolved_log_stream_id = log_stream_id

        for r in resources:
            self.perform_action(r)
        return []

    def _get_log_group_id_by_name(self, client, name):
        try:
            request = ListLogGroupsRequest()
            response = client.list_log_groups(request)

            for group in getattr(response, 'log_groups', []):
                if getattr(group, 'log_group_name', '') == name:
                    return getattr(group, 'log_group_id', None)
        except Exception as e:
            self.log.error(f"Error querying log group by name '{name}': {e}")
        return None

    def _get_log_stream_id_by_name(self, client, log_group_id, name):
        try:
            request = ListLogStreamRequest(log_group_id=log_group_id)
            response = client.list_log_stream(request)

            for stream in getattr(response, 'log_streams', []):
                if getattr(stream, 'log_stream_name', '') == name:
                    return getattr(stream, 'log_stream_id', None)
        except Exception as e:
            self.log.error(f"Error querying log stream by name '{name}' "
                           f"in group '{log_group_id}': {e}")
        return None

    def perform_action(self, resource):
        log_group_id = self.resolved_log_group_id
        log_stream_id = self.resolved_log_stream_id

        if not log_group_id or not log_stream_id:
            self.log.error("Log group or stream ID not resolved. Cannot perform action.")
            return

        session = local_session(self.manager.session_factory)
        client = session.client('workspace')

        if resource.get('enable') is True:
            self.log.info(f"Skipping resource {resource.get('id')}: LTS already enabled.")
            return

        enable_value = True

        request_body_model = SetUserEventsLtsConfigurationsRequestBody(
            enable=enable_value,
            log_group_id=log_group_id,
            log_stream_id=log_stream_id
        )

        request = SetUserEventsLtsConfigurationsRequest(body=request_body_model)
        client.set_user_events_lts_configurations(request)

        self.log.info(f"Successfully submitted set user event LTS configuration.")


@resources.register('workspace-policy-group')
class WorkspacePolicyGroup(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'workspace'
        enum_spec = ('list_policy_group_info', 'policy_groups', 'offset')
        id = 'policy_group_id'
        name = 'policy_group_name'
        tag_resource_type = ''

    def augment(self, resources):
        enhanced_resources = []
        for r in resources:
            if 'id' not in r and self.resource_type.id in r:
                r['id'] = r[self.resource_type.id]

            watermark_enable_value = None
            opacity_setting_value = None
            policies = r.get('policies')
            if policies:
                watermark = policies.get('watermark')
                if watermark:
                    watermark_enable_value = watermark.get('watermark_enable')

                    options = watermark.get('options')
                    if options:
                        opacity_str = options.get('opacity_setting')
                        if opacity_str is not None:
                            try:
                                opacity_setting_value = float(opacity_str)
                            except (TypeError, ValueError):
                                opacity_setting_value = None

            r['watermark_enable'] = watermark_enable_value
            r['opacity_setting'] = opacity_setting_value
            enhanced_resources.append(r)

        return enhanced_resources

    def get_resources(self, resource_ids):
        self.log.info(f"start get resources.resource_ids='{resource_ids}'")
        if "Workspace" in resource_ids:
            self.log.info("No resource IDs provided to get_resources, returning all resources.")
            return self.resources()

        all_resources = self.resources()

        resource_map = {resource[self.resource_type.id]: resource for resource in all_resources}

        found_resources = []
        for rid in resource_ids:
            if rid in resource_map:
                found_resources.append(resource_map[rid])
            else:
                self.log.warning(f"Resource ID '{rid}' not found for type '{self.type}'. Skipping.")

        return found_resources


@WorkspacePolicyGroup.action_registry.register('enable-watermark')
class UpdateWatermarkEnableAction(HuaweiCloudBaseAction):
    """Enable watermark for a workspace policy group

    This action retrieves the current policy settings for a workspace policy group,
    enables the watermark feature by setting 'watermark.watermark_enable' to True,
    and then updates the policy group using the ModifyPolicyGroup API.

    :example:

    .. code-block:: yaml

        policies:
          - name: enable-watermark-on-policy-group
            resource: huaweicloud.workspace-policy-group
            filters:
                - type: value
                key: "policies.watermark.watermark_enable"
                value: false
                op: eq
            actions:
              - type: enable-watermark
                opacity_setting: "20"
    """

    schema = type_schema(
        'enable-watermark',
        opacity_setting={'type': 'string'}  # Accepts any string value
    )

    WATERMARK_KEY = 'watermark'
    WATERMARK_ENABLE_KEY = 'watermark_enable'
    WATERMARK_OPACITY_KEY = 'opacity_setting'
    POLICIES_KEY = 'policies'

    def process(self, resources):
        if not resources:
            self.log.debug("No resources provided to process.")
            return []

        results = []
        for resource in resources:
            result = self.perform_action(resource)
            results.append(result)

        return results

    def perform_action(self, resource):

        policy_group_id = resource.get('policy_group_id')
        if not policy_group_id:
            self.log.error(f"Resource missing 'policy_group_id': {resource}")
            return False

        requested_opacity_setting = self.data.get('opacity_setting')

        # Validate opacity_setting if it's provided
        if requested_opacity_setting is not None:
            if not isinstance(requested_opacity_setting, str):
                self.log.error(
                    f"Invalid opacity_setting value '{requested_opacity_setting}' provided "
                    f"in action configuration for policy group {policy_group_id}. Must be a string.")
                return False

        self.log.info(f"Attempting to enable watermark for policy group {policy_group_id}.")

        session = local_session(self.manager.session_factory)
        client = session.client('workspace')

        try:
            show_request = ListPolicyDetailInfoByIdRequest(policy_group_id=policy_group_id)
            show_response = client.list_policy_detail_info_by_id(show_request)

            full_policy_group_obj = getattr(show_response, 'policy_group', None)
            if not full_policy_group_obj:
                self.log.error(
                    f"Could not retrieve detailed info for policy group {policy_group_id}. "
                    f"Response structure unexpected or empty 'policy_group'.")
                return False

            policies_obj_or_dict = getattr(full_policy_group_obj, self.POLICIES_KEY, {})
            if hasattr(policies_obj_or_dict, 'to_dict'):
                policies = policies_obj_or_dict.to_dict()
            elif isinstance(policies_obj_or_dict, dict):
                policies = policies_obj_or_dict
            else:
                self.log.error(
                    f"Policies attribute for policy group {policy_group_id} is neither a dict "
                    f"nor has to_dict(). Type: {type(policies_obj_or_dict)}")
                return False

            watermark = policies.get(self.WATERMARK_KEY, {})
            if not watermark:
                self.log.warning(
                    f"'{self.WATERMARK_KEY}' section missing in policies for "
                    f"policy group {policy_group_id}. Creating new section.")

            watermark[self.WATERMARK_ENABLE_KEY] = True

            if requested_opacity_setting is not None:
                watermark['options'][self.WATERMARK_OPACITY_KEY] = requested_opacity_setting
                self.log.debug(
                    f"Set '{self.WATERMARK_OPACITY_KEY}' to '{requested_opacity_setting}' "
                    f"for policy group {policy_group_id}.")

            policies[self.WATERMARK_KEY] = watermark

            policy_group_for_update_obj = PolicyGroupForUpdate(policies=policies)
            modify_request_body = ModifyPolicyGroupRequest(policy_group=policy_group_for_update_obj)
            update_request = UpdatePolicyGroupRequest(
                policy_group_id=policy_group_id,
                body=modify_request_body
            )

            client.update_policy_group(update_request)
            self.log.info(f"Successfully submitted update for policy group {policy_group_id} to enable watermark.")
            return True

        except AttributeError as e:
            self.log.error(f"Attribute error while processing policy group {policy_group_id}: {e}")
            return False
        except Exception as e:
            self.log.error(f"Unexpected error while updating watermark for policy group {policy_group_id}: {e}")
            return False
