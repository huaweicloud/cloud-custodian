import logging
from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from huaweicloudsdkdns.v2 import DeletePublicZoneRequest

log = logging.getLogger("custodian.huaweicloud.dns")


@resources.register("dns-publiczone")
class DNS(QueryResourceManager):
    class resource_type(TypeInfo):
        service = "dns"
        enum_spec = ("list_public_zones", "zones", "offset")
        id = "id"
        tag_resource_type = "DNS-public_zone"


@DNS.action_registry.register("delete_public_zones")
class PubLicZoneDelete(HuaweiCloudBaseAction):
    """Delete Public Zone.

    :Example:

    .. code-block:: yaml

        # Example 1: Monitor the event of createpublicZone, and delete zones in real-time
        policies:
          - name: delete_public_zones_event
            resource: dns-publiczone
            mode:
              type: cloudtrace
              xrole: custodian
              eg_agency: EG_TARGET_AGENCY
              enable_lts_log: true
              events:
                - source: "DNS.publicZone"
                    event: "createpublicZone"
                    ids: "resource_id"
            filters:
              - type: exempted
                field: tags
                exempted_values: ["DNS_exempted"]
            actions:
              - type: delete_public_zones

        # Example 2: Delete all public zones periodically
        policies:
          - name: delete_public_zones_timer
            resource: dns-publiczone
            mode:
              type: huaweicloud-periodic
              xrole: custodian
              enable_lts_log: true
              schedule: "1m"
              schedule_type: Rate
            filters:
              - type: exempted
                field: tags
                exempted_values: ["DNS_exempted"]
            actions:
              - type: delete_public_zones
    """

    schema = type_schema("delete_public_zones", xrole={"type": "string"})

    def perform_action(self, resource):
        try:
            client = self.manager.get_client()
            request = DeletePublicZoneRequest()
            request.zone_id = resource["id"]
            response = client.delete_public_zone(request)
            return response
        except Exception as e:
            log.error(
                f"Error occurred while deleting public zone: {str(e)}")
            raise e
