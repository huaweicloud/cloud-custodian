# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from c7n.utils import type_schema
from c7n.filters import AgeFilter
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

from huaweicloudsdksecmaster.v2 import (
    ListAlertsRequest,
    ListPlaybooksRequest,
    ListPlaybookVersionsRequest,
    UpdatePlaybookRequest,
    ModifyPlaybookInfo,
    DataobjectSearch,
)

log = logging.getLogger("custodian.huaweicloud.resources.secmaster")


@resources.register("secmaster")
class SecMaster(QueryResourceManager):
    """Huawei Cloud SecMaster Security Brain instance resource manager.

    Used to manage SecMaster to ensure that security operation accounts cover all business accounts.
    """

    class resource_type(TypeInfo):
        service = "secmaster"
        # TODO: The API for querying SecMaster instances is not yet available
        enum_spec = ("list_instances", "instances", "offset")
        id = "id"
        name = "name"
        tag_resource_type = ""

    # TODO: Implement the logic to get the list of SecMaster instances
    def _fetch_resources(self, query):
        """Get the list of SecMaster instance resources.

        Note: Since the API for querying whether a security account has purchased,
        the implementation here is temporarily marked as TODO.
        """
        log.warning(
            "The SecMaster instance query API is not yet available, returning an empty list"
        )
        return []


@SecMaster.action_registry.register("send-msg")
class SecMasterSendMsg(HuaweiCloudBaseAction):
    """SecMaster instance send message notification action.

    Used to send email notifications during SecMaster coverage checks.

    :example:

    .. code-block:: yaml

        policies:
          - name: secmaster-coverage-check
            resource: huaweicloud.secmaster
            actions:
              - type: send-msg
                message: "SecMaster instance coverage check result"
                subject: "Security Brain coverage check"
    """

    schema = type_schema(
        "send-msg",
        message={"type": "string"},
        subject={"type": "string"},
        required=("message",),
    )

    def perform_action(self, resource):
        """Perform the send message action.

        TODO: email notification function is not yet available and needs to be implemented later.
        """
        message = self.data.get("message", "SecMaster notification")
        subject = self.data.get("subject", "SecMaster notification")

        log.info(
            f"TODO: Send SecMaster notification - Subject: {subject}, Message: {message}"
        )
        log.info(f"Resource ID: {resource.get('id', 'unknown')}")

        # TODO: Implement the email notification logic
        return {
            "status": "TODO",
            "message": "Email notification function to be implemented",
        }


@resources.register("secmaster-workspace")
class SecMasterWorkspace(QueryResourceManager):
    """Huawei Cloud SecMaster workspace resource manager.

    Used to  workspaces to ensure  resource monitoring  on security baselines is enabled.

    Important Note:
    The workspace results include an `is_view` field, indicating whether it is a workspace view.
    Generally, it is recommended to filter workspaces where `is_view` is `false`,
    because only real workspaces (not views) can perform actual security operations.

    :example:

    Filter real workspaces (not views):

    .. code-block:: yaml

        policies:
          - name: secmaster-real-workspaces
            resource: huaweicloud.secmaster-workspace
            filters:
              - type: value
                key: is_view
                value: false
            actions:
              - type: send-msg
                message: "Real workspace found"
                subject: "SecMaster workspace check"
    """

    class resource_type(TypeInfo):
        service = "secmaster"
        enum_spec = ("list_workspaces", "workspaces", "offset", 500)
        id = "id"
        name = "name"
        date = "create_time"
        tag_resource_type = ""


@SecMasterWorkspace.action_registry.register("send-msg")
class WorkspaceSendMsg(HuaweiCloudBaseAction):
    """Workspace send message notification action.

    Used to send email notifications during workspace checks.
    Also supports sending warning notifications when there are no workspaces.

    :example:

    .. code-block:: yaml

        policies:
          - name: secmaster-workspace-check
            resource: huaweicloud.secmaster-workspace
            actions:
              - type: send-msg
                message: "Workspace status check result"
                subject: "SecMaster workspace check"

          - name: secmaster-no-workspace-alert
            resource: huaweicloud.secmaster-workspace
            actions:
              - type: send-msg
                message: "Warning: No SecMaster workspaces found"
                subject: "SecMaster workspace missing warning"
                send_when_empty: true
    """

    schema = type_schema(
        "send-msg",
        message={"type": "string"},
        subject={"type": "string"},
        send_when_empty={"type": "boolean"},
        required=("message",),
    )

    def process(self, resources):
        """Process the resource list, supporting sending notifications when no resources.

        If send_when_empty=true is set, a notification will be sent even when no workspaces.
        """
        # Check if a notification needs to be sent when there are no resources
        send_when_empty = self.data.get("send_when_empty", False)

        if not resources and send_when_empty:
            # No workspaces and need to send an empty resource notification
            log.info("No SecMaster workspaces found, sending warning notification")

            # Perform the empty resource notification logic
            message = self.data.get("message", "Workspace notification")
            subject = self.data.get("subject", "SecMaster workspace notification")

            log.info(
                f"TODO: Send workspace missing warning - Subject: {subject}, Message: {message}"
            )
            log.info("No SecMaster workspaces found for the current account")

            # TODO: Implement the email notification logic
            # Actual email sending logic can be called here

            # Return an empty list, do not create virtual resources
            return []
        elif not resources:
            # No workspaces and no need to send a notification
            log.info("No SecMaster workspaces found")
            return []
        else:
            # There are workspaces, process normally
            return super().process(resources)

    def perform_action(self, resource):
        """Perform the send message action."""
        message = self.data.get("message", "Workspace notification")
        subject = self.data.get("subject", "SecMaster workspace notification")

        log.info(
            f"TODO: Send workspace notification - Subject: {subject}, Message: {message}"
        )
        log.info(
            f"Workspace: {resource.get('name', 'unknown')} (ID: {resource.get('id', 'unknown')})"
        )

        # TODO: Implement the email notification logic
        return {
            "status": "TODO",
            "message": "Email notification function to be implemented",
        }


@resources.register("secmaster-alert")
class SecMasterAlert(QueryResourceManager):
    """Huawei Cloud SecMaster alert resource manager.

    Used to manage SecMaster alerts to ensure log recording and alerts are set.
    """

    class resource_type(TypeInfo):
        service = "secmaster"
        enum_spec = ("list_alerts", "data", "offset")
        id = "id"
        name = "title"
        date = "create_time"
        tag_resource_type = ""

    def _fetch_resources(self, query):
        """Get the list of alert resources.

        The workspace_id parameter needs to be specified to query alerts for a specific workspace.
        """
        client = self.get_client()
        resources = []

        # Get the list of workspaces to query alerts for each workspace
        workspace_manager = self.get_resource_manager("huaweicloud.secmaster-workspace")
        workspaces = workspace_manager.resources()

        for workspace in workspaces:
            workspace_id = workspace.get("id")
            if not workspace_id:
                continue

            offset = 0
            limit = 500

            while True:
                try:
                    # Create a search request body
                    search_body = DataobjectSearch(limit=limit, offset=offset)

                    request = ListAlertsRequest(
                        workspace_id=workspace_id, body=search_body
                    )
                    response = client.list_alerts(request)

                    if not response.data:
                        break

                    # Convert the response data to dictionary format
                    for alert in response.data:
                        if hasattr(alert, "to_dict"):
                            alert_dict = alert.to_dict()
                        else:
                            alert_dict = alert

                        # Keep the original hierarchical structure, do not flatten data_object
                        # Add workspace information to the top level
                        alert_dict["workspace_name"] = workspace.get("name")
                        resources.append(alert_dict)

                    # Check if there is more data
                    if len(response.data) < limit:
                        break

                    offset += limit

                except Exception as e:
                    error_msg = str(e).lower()
                    # Distinguish different types of errors
                    if any(
                        x in error_msg
                        for x in ["unauthorized", "401", "authentication", "credential"]
                    ):
                        log.error(
                            f"alert query authentication failed (Workspace: {workspace_id}): {e}"
                        )
                        raise  # Re-throw authentication error
                    elif any(
                        x in error_msg
                        for x in ["not found", "404", "resource not exist"]
                    ):
                        log.info(
                            f"Workspace {workspace_id} has no alert resources, skipping: {e}"
                        )
                        break  # No alerts is a normal situation
                    elif any(
                        x in error_msg for x in ["forbidden", "403", "permission"]
                    ):
                        log.error(
                            f"alert query permission insufficient (Workspace: {workspace_id}): {e}"
                        )
                        raise  # Re-throw permission error
                    else:
                        log.error(
                            f"Failed to get the alert list for workspace {workspace_id}: {e}"
                        )
                        raise  # Re-throw other unknown errors

        return resources


@SecMasterAlert.filter_registry.register("age")
class AlertAgeFilter(AgeFilter):
    """SecMaster alert age filter.

    Filter alerts created within N days/hours/minutes based on the alert creation time.

    :example:

    .. code-block:: yaml

        policies:
          - name: secmaster-recent-alerts
            resource: huaweicloud.secmaster-alert
            filters:
              - type: age
                days: 7
                op: lt  # Filter alerts within 7 days
    """

    date_attribute = "create_time"  # Alert creation time is in data_object

    schema = type_schema(
        "age",
        op={"$ref": "#/definitions/filters_common/comparison_operators"},
        days={"type": "number"},
        hours={"type": "number"},
        minutes={"type": "number"},
    )


@SecMasterAlert.action_registry.register("send-msg")
class AlertSendMsg(HuaweiCloudBaseAction):
    """Alert send message notification action.

    Used to send email notifications during alert checks, regardless of whether there are alerts.

    :example:

    .. code-block:: yaml

        policies:
          - name: secmaster-alert-notification
            resource: huaweicloud.secmaster-alert
            filters:
              - type: age
                days: 1
                op: lt
            actions:
              - type: send-msg
                message: "Recent 24-hour alerts found"
                subject: "SecMaster alert notification"
    """

    schema = type_schema(
        "send-msg",
        message={"type": "string"},
        subject={"type": "string"},
        required=("message",),
    )

    def perform_action(self, resource):
        """Perform the send message action."""
        message = self.data.get("message", "Alert notification")
        subject = self.data.get("subject", "SecMaster alert notification")

        # Get alert data from the nested structure
        # data_object = resource.get("data_object", {})
        resource.get("data_object", {})
        log.info(
            f"TODO: Send alert notification - Subject: {subject}, Message: {message}"
        )
        log.info(f"Workspace: {resource.get('workspace_name', 'unknown')}")

        # TODO: Implement the email notification logic
        return {
            "status": "TODO",
            "message": "Email notification function to be implemented",
        }


@resources.register("secmaster-playbook")
class SecMasterPlaybook(QueryResourceManager):
    """Huawei Cloud SecMaster playbook resource manager.

    Used to manage SecMaster playbooks to ensure  high-risk operations are reported to SecMaster.
    """

    class resource_type(TypeInfo):
        service = "secmaster"
        enum_spec = ("list_playbooks", "data", "offset")
        id = "id"
        name = "name"
        date = "create_time"
        tag_resource_type = ""

    def get_resources(self, resource_ids):
        result = []
        resources = self._fetch_resources(query=None)
        for resource in resources:
            if resource["id"] in resource_ids:
                result.append(resource)

        return result

    def _fetch_resources(self, query):
        """Get the list of playbook resources.

        The workspace_id parameter needs to be to query playbooks for a specific workspace.
        """
        client = self.get_client()
        resources = []

        # Get the list of workspaces to query playbooks for each workspace
        workspace_manager = self.get_resource_manager("huaweicloud.secmaster-workspace")
        workspaces = workspace_manager.resources()
        for workspace in workspaces:
            workspace_id = workspace.get("id")
            if not workspace_id:
                continue

            offset = 0
            limit = 500

            while True:
                try:
                    request = ListPlaybooksRequest(
                        workspace_id=workspace_id, offset=offset, limit=limit
                    )
                    response = client.list_playbooks(request)

                    if not response.data:
                        break

                    # Convert the response data to dictionary format
                    for playbook in response.data:
                        if hasattr(playbook, "to_dict"):
                            playbook_dict = playbook.to_dict()
                        else:
                            playbook_dict = playbook
                        # Add workspace information
                        playbook_dict["workspace_id"] = workspace_id
                        playbook_dict["workspace_name"] = workspace.get("name")
                        resources.append(playbook_dict)

                    # Check if there is more data
                    if len(response.data) < limit:
                        break

                    offset += limit

                except Exception as e:
                    error_msg = str(e).lower()
                    # Distinguish different types of errors
                    if any(
                        x in error_msg
                        for x in ["unauthorized", "401", "authentication", "credential"]
                    ):
                        log.error(
                            f"playbook query authentication failed (Workspace: {workspace_id}): {e}"
                        )
                        raise  # Re-throw authentication error
                    elif any(
                        x in error_msg
                        for x in ["not found", "404", "resource not exist"]
                    ):
                        log.info(
                            f"Workspace {workspace_id} has no playbook resources, skipping: {e}"
                        )
                        break  # No playbooks is a normal situation
                    elif any(
                        x in error_msg for x in ["forbidden", "403", "permission"]
                    ):
                        log.error(
                            f"playbook query permission (Workspace: {workspace_id}): {e}"
                        )
                        raise  # Re-throw permission error
                    else:
                        log.error(
                            f"Failed to get the playbook list for workspace {workspace_id}: {e}"
                        )
                        raise  # Re-throw other unknown errors

        return resources


@SecMasterPlaybook.action_registry.register("enable-playbook")
class EnablePlaybook(HuaweiCloudBaseAction):
    """Enable playbook action.

    Used to enable playbooks to ensure that high-risk operations can be reported.

    :example:

    .. code-block:: yaml

        policies:
          - name: enable-security-playbooks
            resource: huaweicloud.secmaster-playbook
            filters:
              - type: value
                key: name
                value: "High-risk operation monitoring playbook"
              - type: value
                key: enabled
                value: false
            actions:
              - type: enable-playbook
    """

    schema = type_schema("enable-playbook")

    def perform_action(self, resource):
        """Perform the enable playbook action."""
        client = self.manager.get_client()
        workspace_id = resource.get("workspace_id")
        playbook_id = resource.get("id")
        playbook_name = resource.get("name")

        if not workspace_id or not playbook_id:
            log.error(
                f"ID is missing: workspace_id={workspace_id}, playbook_id={playbook_id}"
            )
            return {
                "status": "error",
                "message": "Workspace ID or playbook ID is missing",
            }

        try:
            # First, query the playbook version list to find the latest version
            log.info(f"Querying the version list of playbook {playbook_name}...")

            offset = 0
            limit = 500
            latest_version = None
            latest_update_time = None

            while True:
                version_request = ListPlaybookVersionsRequest(
                    workspace_id=workspace_id,
                    playbook_id=playbook_id,
                    offset=offset,
                    limit=limit,
                )

                version_response = client.list_playbook_versions(version_request)

                if not version_response.data:
                    break

                # Iterate through the version list to find the version with the latest update_time
                for version in version_response.data:
                    if hasattr(version, "to_dict"):
                        version_dict = version.to_dict()
                    else:
                        version_dict = version

                    update_time_str = version_dict.get("update_time")
                    if update_time_str:
                        try:
                            # Parse the time string
                            from dateutil.parser import parse

                            update_time = parse(update_time_str)

                            if (
                                latest_update_time is None
                                or update_time > latest_update_time
                            ):
                                latest_update_time = update_time
                                latest_version = version_dict
                        except Exception as e:
                            log.warning(
                                f"Failed to parse time: {update_time_str}, Error: {e}"
                            )
                            continue

                # Check if there is more data
                if len(version_response.data) < limit:
                    break

                offset += limit

            if not latest_version:
                log.error(f"No versions found for playbook {playbook_name}")
                return {"status": "error", "message": "No playbook versions found"}

            active_version_id = latest_version.get("id")
            log.info(
                f"Latest version found: {latest_version.get('version')} (ID: {active_version_id})"
            )

            # Build the modified playbook information to enable the playbook
            modify_info = ModifyPlaybookInfo(
                name=playbook_name,  # Set the playbook name
                enabled=True,  # Enable the playbook
                active_version_id=active_version_id,  # Set the enabled version ID
                description=resource.get("description", "")
                + " [Automatically enabled via policy]",
            )

            request = UpdatePlaybookRequest(
                workspace_id=workspace_id, playbook_id=playbook_id, body=modify_info
            )

            # response = client.update_playbook(request)
            client.update_playbook(request)

            log.info(
                f"enabled playbook: {playbook_name},{latest_version.get('version')}"
            )
            return {
                "status": "success",
                "message": f"{playbook_name} has been enabled,{latest_version.get('version')}",
                "playbook_id": playbook_id,
                "active_version_id": active_version_id,
                "active_version": latest_version.get("version"),
            }

        except Exception as e:
            log.error(f"Failed to enable playbook: {e}")
            return {"status": "error", "message": str(e)}


@SecMasterPlaybook.action_registry.register("send-msg")
class PlaybookSendMsg(HuaweiCloudBaseAction):
    """Playbook send message notification action.

    Used to send email notifications when the playbook status changes.

    :example:

    .. code-block:: yaml

        policies:
          - name: secmaster-playbook-notification
            resource: huaweicloud.secmaster-playbook
            filters:
              - type: value
                key: enabled
                value: true
            actions:
              - type: send-msg
                message: "Playbook enabled and in effect"
                subject: "SecMaster playbook status notification"
    """

    schema = type_schema(
        "send-msg",
        message={"type": "string"},
        subject={"type": "string"},
        required=("message",),
    )

    def perform_action(self, resource):
        """Perform the send message action."""
        message = self.data.get("message", "Playbook notification")
        subject = self.data.get("subject", "SecMaster playbook notification")

        log.info(
            f"TODO: Send playbook notification - Subject: {subject}, Message: {message}"
        )
        log.info(
            f"Playbook: {resource.get('name', 'unknown')} (ID: {resource.get('id', 'unknown')})"
        )
        log.info(f"Workspace: {resource.get('workspace_name', 'unknown')}")
        log.info(
            f"Playbook status: {'Enabled' if resource.get('enabled') else 'Disabled'}"
        )

        # TODO: Implement the email notification logic
        return {
            "status": "TODO",
            "message": "Email notification function to be implemented",
        }
