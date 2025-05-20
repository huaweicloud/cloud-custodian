# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from c7n.utils import type_schema, local_session, chunks
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction

from huaweicloudsdkhss.v5 import (
    SwitchHostsProtectStatusRequestInfo,
    SwitchHostsProtectStatusRequest,
    SetWtpProtectionStatusRequestInfo,
    SetWtpProtectionStatusInfoRequest,
    TagInfo,
)

from huaweicloudsdkcore.exceptions import exceptions


log = logging.getLogger("custodian.huaweicloud.hss")


@resources.register("hss")
class Hss(QueryResourceManager):
    """Huawei Cloud Host Security Service (Hss) Resource Manager"""

    class resource_type(TypeInfo):
        service = "hss"
        enum_spec = (
            "list_host_status",
            "data_list",
            "offset",
        )  # Use ListHostStatus API
        id = "host_id"
        name = "host_name"
        filter_name = "host_id"
        filter_type = "scalar"
        taggable = False
        tag_resource_type = None

    def augment(self, resources):
        # Ensure all important fields are present in resource objects
        for r in resources:
            r["id"] = r.get("host_id")  # Ensure id field exists
            if "register_time" in r:
                log.debug(
                    f"Resource {r['host_id']} has register_time: {r['register_time']}"
                )
            elif "agent_install_time" in r:
                r["register_time"] = r.get("agent_install_time")
                log.debug(
                    f"Using time as register_time for {r['host_id']}: {r['register_time']}"
                )
        return resources


@Hss.action_registry.register("switch-hosts-protect-status")
class SwitchHostsProtectStatusAction(HuaweiCloudBaseAction):
    """Action to switch host protection status

    :example:

    .. code-block:: yaml

        policies:
          - name: enable-hss-protection
            resource: huaweicloud.hss
            filters:
              - type: host-status
                status: unprotected
            actions:
              - type: switch-hosts-protect-status
                version: hss.version.enterprise
                charging_mode: packet_cycle
    """

    schema = type_schema(
        "switch-hosts-protect-status",
        required=["version"],
        version={
            "type": "string",
            "enum": [
                "hss.version.null",  # None, represents disabling protection
                "hss.version.basic",  # Basic edition
                "hss.version.advanced",  # Professional edition
                "hss.version.enterprise",  # Enterprise edition
                "hss.version.premium",  # Premium edition
                "hss.version.wtp",  # Web Tamper Protection edition
            ],
        },
        charging_mode={"type": "string", "enum": ["packet_cycle", "on_demand"]},
        resource_id={"type": "string"},
        tags={"type": "object"},
    )

    def process(self, resources):
        # client = local_session(self.manager.session_factory).client("hss")
        client = self.manager.get_client()
        version = self.data.get("version")
        charging_mode = self.data.get("charging_mode")
        resource_id = self.data.get("resource_id")
        tags_data = self.data.get("tags", {})
        # Process resources in batches, with at most 20 resources per batch
        for resource_set in chunks(resources, 20):
            host_ids = [r["host_id"] for r in resource_set]

            # Prepare tag data
            tags = []
            for key, value in tags_data.items():
                tags.append(TagInfo(key=key, value=value))

            # Build request body
            request_info = SwitchHostsProtectStatusRequestInfo(
                version=version, host_id_list=host_ids, tags=tags if tags else None
            )

            # Set optional parameters
            if charging_mode:
                request_info.charging_mode = charging_mode
            if resource_id:
                request_info.resource_id = resource_id

            # Create request
            request = SwitchHostsProtectStatusRequest(body=request_info)

            try:
                client.switch_hosts_protect_status(request)
                self.log.info(
                    f"Successfully switched protection status to {version} for {len(host_ids)} host"
                )
            except exceptions.ClientRequestException as e:
                self.log.error(
                    f"Failed to switch host protection status: {e.error_msg}"
                )
                raise

        return resources

    def perform_action(self, resource):
        # Individual resource processing will be handled by the process method
        pass


@Hss.action_registry.register("set-wtp-protection-status")
class SetWtpProtectionStatusAction(HuaweiCloudBaseAction):
    """Action to set web tamper protection status

    :example:

    .. code-block:: yaml

        policies:
          - name: enable-wtp-protection
            resource: huaweicloud.hss
            filters:
              - type: wtp-protection
                status: disabled
            actions:
              - type: set-wtp-protection-status
                status: enabled
    """

    schema = type_schema(
        "set-wtp-protection-status",
        required=["status"],
        status={"type": "string", "enum": ["enabled", "disabled"]},
    )

    def process(self, resources):
        client = local_session(self.manager.session_factory).client("hss")
        status = self.data.get("status")
        for resource in resources:
            host_id = resource["host_id"]
            try:
                # Create request body
                request_info = SetWtpProtectionStatusRequestInfo(
                    charging_mode="packet_cycle",
                    status=True if status == "enabled" else False,
                    host_id_list=[host_id],
                )

                # Call appropriate API based on status
                if status == "enabled":
                    # Create request
                    request = SetWtpProtectionStatusInfoRequest(
                        region="ap-southeast-1",  # Use appropriate region
                        body=request_info,
                    )

                    # Enable web tamper protection
                    client.set_wtp_protection_status_info(request)
                    self.log.info(
                        f"Successfully enabled web tamper protection for host {host_id}"
                    )
                else:
                    # Create request
                    request = SetWtpProtectionStatusInfoRequest(
                        region="ap-southeast-1",  # Use appropriate region
                        body=request_info,
                    )

                    # Disable web tamper protection
                    client.set_wtp_protection_status_info(request)
                    self.log.info(
                        f"Successfully disabled web tamper protection for host {host_id}"
                    )

            except exceptions.ClientRequestException as e:
                self.log.error(
                    f"Failed to set web tamper protection status for host {host_id}: {e.error_msg}"
                )
                continue

        return resources

    def perform_action(self, resource):
        # Individual resource processing will be handled by the process method
        pass
