# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkeip.v2 import DeletePublicipRequest
from huaweicloudsdkeip.v3 import DisassociatePublicipsRequest

from c7n.utils import type_schema, local_session
from c7n.filters import Filter
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

log = logging.getLogger("custodian.huaweicloud.resources.eip")


@resources.register("eip")
class EIP(QueryResourceManager):
    """HuaweiCloud Elastic IP Resource
    """

    class resource_type(TypeInfo):
        service = "eip"
        enum_spec = ("list_publicips", "publicips", "marker")
        id = "id"
        tag_resource_type = "eip"


@EIP.filter_registry.register("associate-instance-type")
class AssociateInstanceTypeFilter(Filter):
    """EIP Associated Instance Type Filter

    Filter EIPs based on associated instance type (e.g., PORT, NATGW, ELB, ELBV1, VPN, etc.)

    :example:

    .. code-block:: yaml

        policies:
          - name: eip-associated-with-elb
            resource: huaweicloud.eip
            filters:
              - type: associate-instance-type
                instance_type: ELB
    """
    schema = type_schema(
        "associate-instance-type",
        instance_type={"type": "string", "enum": ["PORT", "NATGW", "ELB", "ELBV1", "VPN", "NONE"]},
        required=["instance_type"]
    )

    def process(self, resources, event=None):
        instance_type = self.data.get("instance_type")
        results = []

        for resource in resources:
            # Check if associate_instance_type is empty (not associated with any instance)
            resource_instance_type = resource.get("associate_instance_type", "")

            if not resource_instance_type:
                # Not associated with any instance
                if instance_type == "NONE":
                    results.append(resource)
                continue

            # Match based on associate_instance_type returned by API
            if resource_instance_type == instance_type:
                results.append(resource)

        return results


@EIP.action_registry.register("delete")
class EIPDelete(HuaweiCloudBaseAction):
    """Delete Elastic IP

    Automatically disassociates the EIP before deletion if it's bound to an instance

    Note: If the EIP is associated with a NATGW instance, please use nat-snat-rule or nat-dnat-rule
    delete actions instead

    :example:

    .. code-block:: yaml

        policies:
          - name: delete-unassociated-eips
            resource: huaweicloud.eip
            filters:
              - type: value
                key: status
                value: DOWN
            actions:
              - delete
    """
    schema = type_schema("delete")

    def process(self, resources):
        session = local_session(self.manager.session_factory)
        # Use eip_v3 client for disassociation
        client_v3 = self.manager.get_client()
        # Use eip_v2 client for deletion
        client_v2 = session.client('eip_v2')
        processed_resources = []

        for resource in resources:
            try:
                # Check if EIP is associated with NATGW instance
                if resource.get("associate_instance_type") == "NATGW":
                    self.log.error(
                        f"Cannot delete EIP {resource['id']} associated with NATGW, "
                        f"please use nat-snat-rule or nat-dnat-rule delete action instead."
                    )
                    self.failed_resources.append(resource)
                    continue

                # If EIP status is ACTIVE (bound), disassociate it first
                if resource.get("status") == "ACTIVE":
                    try:
                        request = DisassociatePublicipsRequest()
                        request.publicip_id = resource["id"]
                        client_v3.disassociate_publicips(request)
                        self.log.info(f"Successfully disassociated EIP {resource['id']}")
                    except exceptions.ClientRequestException as e:
                        self.log.error(
                            f"Failed to disassociate EIP {resource['id']}, "
                            f"Request ID: {e.request_id},"
                            f" Error Code: {e.error_code}, Error Message: {e.error_msg}"
                        )
                        self.failed_resources.append(resource)
                        continue

                # Perform deletion
                request = DeletePublicipRequest(publicip_id=resource["id"])
                client_v2.delete_publicip(request)
                self.log.info(f"Successfully deleted EIP {resource['id']}")
                processed_resources.append(resource)
            except exceptions.ClientRequestException as e:
                self.log.error(
                    f"Failed to delete EIP {resource['id']}, "
                    f"Request ID: {e.request_id}, Error Code: {e.error_code}"
                    f", Error Message: {e.error_msg}"
                )
                self.failed_resources.append(resource)

        # Add successfully processed resources to the result
        self.result.get("succeeded_resources").extend(processed_resources)
        return self.result

    def perform_action(self, resource):
        # No additional operation needed as we have
        # already processed each resource in the process method
        pass


@EIP.action_registry.register("disassociate")
class EIPDisassociate(HuaweiCloudBaseAction):
    """Disassociate Elastic IP

    Disassociates an EIP from the instance it is bound to

    Note: If the EIP is associated with a NATGW instance,
     please use nat-snat-rule or nat-dnat-rule
    delete actions instead

    :example:

    .. code-block:: yaml

        policies:
          - name: disassociate-eips-from-instances
            resource: huaweicloud.eip
            filters:
              - type: value
                key: status
                value: ACTIVE
            actions:
              - disassociate
    """
    schema = type_schema("disassociate")

    def process(self, resources):
        client = self.manager.get_client()
        # Filter EIPs with ACTIVE status (bound to instances)
        active_resources = [r for r in resources if r.get("status") == "ACTIVE"]
        processed_resources = []

        for resource in active_resources:
            try:
                # Check if EIP is associated with NATGW instance
                if resource.get("associate_instance_type") == "NATGW":
                    self.log.error(
                        f"Cannot disassociate EIP {resource['id']} associated with NATGW, "
                        f"please use nat-snat-rule or nat-dnat-rule delete action instead."
                    )
                    self.failed_resources.append(resource)
                    continue

                request = DisassociatePublicipsRequest()
                request.publicip_id = resource["id"]
                client.disassociate_publicips(request)
                self.log.info(f"Successfully disassociated EIP {resource['id']}")
                processed_resources.append(resource)
            except exceptions.ClientRequestException as e:
                self.log.error(
                    f"Failed to disassociate EIP {resource['id']}, "
                    f"Request ID: {e.request_id}, Error Code: {e.error_code},"
                    f" Error Message: {e.error_msg}"
                )
                self.failed_resources.append(resource)

        # Add successfully processed resources to the result
        self.result.get("succeeded_resources").extend(processed_resources)
        return self.result

    def perform_action(self, resource):
        # No additional operation needed as we have already
        # processed each resource in the process method
        pass
