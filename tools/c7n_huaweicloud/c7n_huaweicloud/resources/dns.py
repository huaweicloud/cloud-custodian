# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkdns.v2 import (
    # Public Zone Management
    ShowPublicZoneRequest,
    DeletePublicZoneRequest,
    UpdatePublicZoneStatusRequest,
    UpdatePublicZoneStatusRequestBody,
    UpdatePublicZoneRequest,
    UpdatePublicZoneInfo,

    # Private Zone Management
    ShowPrivateZoneRequest,
    DeletePrivateZoneRequest,
    UpdatePrivateZoneRequest,
    UpdatePrivateZoneInfoReq,
    AssociateRouterRequest,
    AssociateRouterRequestBody,
    DisassociateRouterRequest,
    DisassociaterouterRequestBody,
    Router,

    # Record Set Management
    ShowRecordSetRequest,
    DeleteRecordSetRequest,
    UpdateRecordSetRequest,
    UpdateRecordSetReq,
    SetRecordSetsStatusRequest,
    SetRecordSetsStatusRequestBody,

    # Batch Interface Management
    BatchSetRecordSetsStatusRequest,
    BatchSetRecordSetsStatusRequestBody,
)

from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n.utils import type_schema
from c7n.filters import Filter, ValueFilter
from c7n.filters.core import AgeFilter

log = logging.getLogger('custodian.huaweicloud.dns')


# Public DNS Zone Resource Management
@resources.register('dns-publiczone')
class PublicZone(QueryResourceManager):
    """Huawei Cloud Public DNS Hosted Zone Resource Manager.

    :example:

    .. code-block:: yaml

        policies:
          - name: dns-publiczone-active
            resource: huaweicloud.dns-publiczone
            filters:
              - type: value
                key: status
                value: ACTIVE
    """

    class resource_type(TypeInfo):
        service = 'dns-publiczone'
        enum_spec = ('list_public_zones', 'zones', 'marker')
        id = 'id'
        name = 'name'
        filter_name = 'name'
        filter_type = 'scalar'
        taggable = True
        tag_resource_type = 'DNS-public_zone'

    def augment(self, resources):
        """Augment resource information, add tags, etc."""
        client = self.get_client()

        for r in resources:
            try:
                request = ShowPublicZoneRequest(zone_id=r['id'])
                response = client.show_public_zone(request)
                zone_info = response.to_dict()
                r.update(zone_info)
            except exceptions.ClientRequestException as e:
                log.warning(
                    "Failed to get public zone details "
                    f"({r.get('name', r.get('id', 'unknown'))}): {e}"
                )

        return resources


@PublicZone.filter_registry.register('age')
class PublicZoneAgeFilter(AgeFilter):
    """Public DNS Zone creation time filter.

    :example:

    .. code-block:: yaml

        policies:
          - name: dns-publiczone-old
            resource: huaweicloud.dns-publiczone
            filters:
              - type: age
                days: 90
                op: gt
    """

    schema = type_schema(
        'age',
        op={
            '$ref': '#/definitions/filters_common/comparison_operators'
        },
        days={'type': 'number'},
        hours={'type': 'number'},
        minutes={'type': 'number'}
    )
    date_attribute = "created_at"


@PublicZone.action_registry.register('delete')
class DeletePublicZoneAction(HuaweiCloudBaseAction):
    """Delete Public DNS Zone operation.

    :example:

    .. code-block:: yaml

        policies:
          - name: dns-publiczone-delete
            resource: huaweicloud.dns-publiczone
            filters:
              - type: value
                key: name
                value: example.com.
            actions:
              - delete
    """

    schema = type_schema('delete')

    def perform_action(self, resource):
        client = self.manager.get_client()
        zone_id = resource['id']
        try:
            request = DeletePublicZoneRequest(zone_id=zone_id)
            client.delete_public_zone(request)
            self.log.info(
                f"Successfully deleted public zone: {resource.get('name')} (ID: {zone_id})"
            )
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to delete public zone {resource.get('name')} (ID: {zone_id}): {e}")
            raise


@PublicZone.action_registry.register('update')
class UpdatePublicZoneAction(HuaweiCloudBaseAction):
    """Update Public DNS Zone properties operation.

    :example:

    .. code-block:: yaml

        policies:
          - name: dns-publiczone-update
            resource: huaweicloud.dns-publiczone
            filters:
              - type: value
                key: name
                value: example.com.
            actions:
              - type: update
                email: new-admin@example.com
                ttl: 7200
                description: "Updated by Cloud Custodian"
    """

    schema = type_schema(
        'update',
        email={'type': 'string'},
        ttl={'type': 'integer'},
        description={'type': 'string'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        zone_id = resource['id']

        email = self.data.get('email')
        ttl = self.data.get('ttl')
        description = self.data.get('description')

        if not any([email, ttl, description]):
            self.log.info(
                "No need to update public zone, update parameters not provided: "
                f"{resource.get('name')} (ID: {zone_id})"
            )
            return

        try:
            update_info = UpdatePublicZoneInfo()
            if email is not None:
                update_info.email = email
            if ttl is not None:
                update_info.ttl = ttl
            if description is not None:
                update_info.description = description

            request = UpdatePublicZoneRequest(zone_id=zone_id, body=update_info)
            client.update_public_zone(request)
            self.log.info(
                f"Successfully updated public zone: {resource.get('name')} (ID: {zone_id})"
            )
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to update public zone {resource.get('name')} (ID: {zone_id}): {e}")
            raise


@PublicZone.action_registry.register('set-status')
class SetPublicZoneStatusAction(HuaweiCloudBaseAction):
    """Set Public DNS Zone status operation.

    :example:

    .. code-block:: yaml

        policies:
          - name: dns-publiczone-disable
            resource: huaweicloud.dns-publiczone
            filters:
              - type: value
                key: name
                value: example.com.
            actions:
              - type: set-status
                status: DISABLE
    """

    schema = type_schema(
        'set-status',
        required=['status'],
        status={'type': 'string', 'enum': ['ENABLE', 'DISABLE']}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        zone_id = resource['id']
        status = self.data.get('status')

        try:
            request_body = UpdatePublicZoneStatusRequestBody(status=status)
            request = UpdatePublicZoneStatusRequest(zone_id=zone_id, body=request_body)
            client.update_public_zone_status(request)
            self.log.info(
                f"Successfully set public zone status to {status}: "
                f"{resource.get('name')} (ID: {zone_id})"
            )
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to set public zone status {resource.get('name')} (ID: {zone_id}): {e}"
            )
            raise


# Private DNS Zone Resource Management
@resources.register('dns-privatezone')
class PrivateZone(QueryResourceManager):
    """Huawei Cloud Private DNS Hosted Zone Resource Manager.

    :example:

    .. code-block:: yaml

        policies:
          - name: dns-privatezone-active
            resource: huaweicloud.dns-privatezone
            filters:
              - type: status
                key: status
                value: ACTIVE
    """

    class resource_type(TypeInfo):
        service = 'dns-privatezone'
        enum_spec = ('list_private_zones', 'zones', 'marker')
        id = 'id'
        name = 'name'
        filter_name = 'name'
        filter_type = 'scalar'
        taggable = True
        tag_resource_type = 'DNS-private_zone'

    def augment(self, resources):
        """Augment resource information, add tags, etc."""
        client = self.get_client()
        for r in resources:
            try:
                request = ShowPrivateZoneRequest(zone_id=r['id'])
                response = client.show_private_zone(request)
                zone_info = response.to_dict()
                r.update(zone_info)
            except exceptions.ClientRequestException as e:
                log.warning(
                    "Failed to get private zone details "
                    f"({r.get('name', r.get('id', 'unknown'))}): {e}"
                )

        return resources


@PrivateZone.filter_registry.register('vpc-associated')
class PrivateZoneVpcAssociatedFilter(Filter):
    """Private DNS Zone associated VPC filter.

    :example:

    .. code-block:: yaml

        policies:
          - name: dns-privatezone-vpc
            resource: huaweicloud.dns-privatezone
            filters:
              - type: vpc-associated
                vpc_id: vpc-12345678
    """

    schema = type_schema(
        'vpc-associated',
        vpc_id={'type': 'string'}
    )

    def process(self, resources, event=None):
        vpc_id = self.data.get('vpc_id')
        if not vpc_id:
            return resources
        result = []
        for r in resources:
            routers = r.get('routers', [])
            for router in routers:
                if router.get('router_id') == vpc_id:
                    result.append(r)
                    break

        return result


@PrivateZone.filter_registry.register('age')
class PrivateZoneAgeFilter(AgeFilter):
    """Private DNS Zone creation time filter.

    :example:

    .. code-block:: yaml

        policies:
          - name: dns-privatezone-old
            resource: huaweicloud.dns-privatezone
            filters:
              - type: age
                days: 90
                op: gt
    """

    schema = type_schema(
        'age',
        op={
            '$ref': '#/definitions/filters_common/comparison_operators'
        },
        days={'type': 'number'},
        hours={'type': 'number'},
        minutes={'type': 'number'}
    )
    date_attribute = "created_at"


@PrivateZone.action_registry.register('delete')
class DeletePrivateZoneAction(HuaweiCloudBaseAction):
    """Delete Private DNS Zone operation.

    :example:

    .. code-block:: yaml

        policies:
          - name: dns-privatezone-delete
            resource: huaweicloud.dns-privatezone
            filters:
              - type: value
                key: name
                value: example.com.
            actions:
              - delete
    """

    schema = type_schema('delete')

    def perform_action(self, resource):
        client = self.manager.get_client()
        zone_id = resource['id']
        try:
            request = DeletePrivateZoneRequest(zone_id=zone_id)
            client.delete_private_zone(request)
            self.log.info(
                f"Successfully deleted private zone: {resource.get('name')} (ID: {zone_id})"
            )
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to delete private zone {resource.get('name')} (ID: {zone_id}): {e}"
            )
            raise


@PrivateZone.action_registry.register('update')
class UpdatePrivateZoneAction(HuaweiCloudBaseAction):
    """Update Private DNS Zone properties operation.

    :example:

    .. code-block:: yaml

        policies:
          - name: dns-privatezone-update
            resource: huaweicloud.dns-privatezone
            filters:
              - type: value
                key: name
                value: example.com.
            actions:
              - type: update
                email: new-admin@example.com
                ttl: 7200
                description: "Updated by Cloud Custodian"
    """

    schema = type_schema(
        'update',
        email={'type': 'string'},
        ttl={'type': 'integer'},
        description={'type': 'string'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        zone_id = resource['id']

        email = self.data.get('email')
        ttl = self.data.get('ttl')
        description = self.data.get('description')

        if not any([email, ttl, description]):
            self.log.info(
                "No need to update private zone, update parameters not provided: "
                f"{resource.get('name')} (ID: {zone_id})"
            )
            return

        try:
            update_info = UpdatePrivateZoneInfoReq()
            if email is not None:
                update_info.email = email
            if ttl is not None:
                update_info.ttl = ttl
            if description is not None:
                update_info.description = description

            request = UpdatePrivateZoneRequest(zone_id=zone_id, body=update_info)
            client.update_private_zone(request)
            self.log.info(
                f"Successfully updated private zone: {resource.get('name')} (ID: {zone_id})"
            )
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to update private zone {resource.get('name')} (ID: {zone_id}): {e}"
            )
            raise


@PrivateZone.action_registry.register('associate-vpc')
class AssociateVpcAction(HuaweiCloudBaseAction):
    """Associate VPC to Private DNS Zone operation.

    :example:

    .. code-block:: yaml

        policies:
          - name: dns-privatezone-associate-vpc
            resource: huaweicloud.dns-privatezone
            filters:
              - type: value
                key: name
                value: example.com.
            actions:
              - type: associate-vpc
                vpc_id: vpc-12345678
                region: cn-north-4
    """

    schema = type_schema(
        'associate-vpc',
        required=['vpc_id'],
        vpc_id={'type': 'string'},
        region={'type': 'string'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        zone_id = resource['id']
        vpc_id = self.data.get('vpc_id')
        region = self.data.get('region', None)

        try:
            router = Router(router_id=vpc_id, router_region=region)
            request_body = AssociateRouterRequestBody(router=router)
            request = AssociateRouterRequest(zone_id=zone_id, body=request_body)
            client.associate_router(request)
            self.log.info(
                f"Successfully associated VPC {vpc_id} to private zone: "
                f"{resource.get('name')} (ID: {zone_id})"
            )
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to associate VPC to private zone {resource.get('name')} "
                f"(ID: {zone_id}): {e}"
            )
            raise


@PrivateZone.action_registry.register('disassociate-vpc')
class DisassociateVpcAction(HuaweiCloudBaseAction):
    """Disassociate VPC from Private DNS Zone operation.

    :example:

    .. code-block:: yaml

        policies:
          - name: dns-privatezone-disassociate-vpc
            resource: huaweicloud.dns-privatezone
            filters:
              - type: value
                key: name
                value: example.com.
              - type: vpc-associated
                vpc_id: vpc-12345678
            actions:
              - type: disassociate-vpc
                vpc_id: vpc-12345678
                region: cn-north-4
    """

    schema = type_schema(
        'disassociate-vpc',
        required=['vpc_id'],
        vpc_id={'type': 'string'},
        region={'type': 'string'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        zone_id = resource['id']
        vpc_id = self.data.get('vpc_id')
        region = self.data.get('region', None)

        try:
            router = Router(router_id=vpc_id, router_region=region)
            request_body = DisassociaterouterRequestBody(router=router)
            request = DisassociateRouterRequest(zone_id=zone_id, body=request_body)
            client.disassociate_router(request)
            self.log.info(
                f"Successfully disassociated VPC {vpc_id} from private zone: "
                f"{resource.get('name')} (ID: {zone_id})"
            )
        except exceptions.ClientRequestException as e:
            self.log.error(
                "Failed to disassociate VPC from private zone "
                f"{resource.get('name')} (ID: {zone_id}): {e}"
            )
            raise


# Record Set Resource Management
@resources.register('dns-recordset')
class RecordSet(QueryResourceManager):
    """Huawei Cloud DNS Record Set Resource Manager.

    :example:

    .. code-block:: yaml

        policies:
          - name: dns-recordset-a-records
            resource: huaweicloud.dns-recordset
            filters:
              - type: value
                key: type
                value: A
    """

    class resource_type(TypeInfo):
        service = 'dns-recordset'
        enum_spec = ('list_record_sets_with_line', 'recordsets', 'marker')
        id = 'id'
        name = 'name'
        filter_name = 'name'
        filter_type = 'scalar'
        taggable = True
        tag_resource_type = 'DNS-public_recordset'

    def augment(self, resources):
        """Augment resource information, add tags, etc."""
        client = self.get_client()

        for r in resources:
            try:
                if 'zone_id' in r:
                    request = ShowRecordSetRequest(
                        zone_id=r['zone_id'], recordset_id=r['id']
                    )
                    response = client.show_record_set(request)
                    record_info = response.to_dict()
                    r.update(record_info)
            except exceptions.ClientRequestException as e:
                log.warning(
                    "Failed to get record set details "
                    f"({r.get('name', r.get('id', 'unknown'))}): {e}"
                )

        return resources


@RecordSet.filter_registry.register('record-type')
class RecordTypeFilter(ValueFilter):
    """DNS Record Set type filter.

    :example:

    .. code-block:: yaml

        policies:
          - name: dns-recordset-a-records
            resource: huaweicloud.dns-recordset
            filters:
              - type: record-type
                value: A
    """

    schema = type_schema('record-type', rinherit=ValueFilter.schema)
    schema_alias = True

    def process(self, resources, event=None):
        return [r for r in resources if self.match(r.get('type'))]


@RecordSet.filter_registry.register('zone-id')
class ZoneIdFilter(ValueFilter):
    """DNS Record Set belonging Zone ID filter.

    :example:

    .. code-block:: yaml

        policies:
          - name: dns-recordset-by-zone
            resource: huaweicloud.dns-recordset
            filters:
              - type: zone-id
                value: ff8080825b8fc86c015b94bc6f8712c3
    """

    schema = type_schema('zone-id', rinherit=ValueFilter.schema)
    schema_alias = True

    def process(self, resources, event=None):
        return [r for r in resources if self.match(r.get('zone_id'))]


@RecordSet.filter_registry.register('line-id')
class LineIdFilter(ValueFilter):
    """DNS Record Set line ID filter.

    :example:

    .. code-block:: yaml

        policies:
          - name: dns-recordset-by-line
            resource: huaweicloud.dns-recordset
            filters:
              - type: line-id
                value: default_view
    """

    schema = type_schema('line-id', rinherit=ValueFilter.schema)
    schema_alias = True

    def process(self, resources, event=None):
        return [r for r in resources if self.match(r.get('line') or r.get('line_id'))]


@RecordSet.filter_registry.register('age')
class RecordSetAgeFilter(AgeFilter):
    """DNS Record Set creation time filter.

    :example:

    .. code-block:: yaml

        policies:
          - name: dns-recordset-old
            resource: huaweicloud.dns-recordset
            filters:
              - type: age
                days: 90
                op: gt
    """

    schema = type_schema(
        'age',
        op={
            '$ref': '#/definitions/filters_common/comparison_operators'
        },
        days={'type': 'number'},
        hours={'type': 'number'},
        minutes={'type': 'number'}
    )
    date_attribute = "created_at"


@RecordSet.action_registry.register('delete')
class DeleteRecordSetAction(HuaweiCloudBaseAction):
    """Delete DNS Record Set operation.

    :example:

    .. code-block:: yaml

        policies:
          - name: dns-recordset-delete
            resource: huaweicloud.dns-recordset
            filters:
              - type: record-type
                value: TXT
            actions:
              - delete
    """

    schema = type_schema('delete')

    def perform_action(self, resource):
        client = self.manager.get_client()
        recordset_id = resource['id']
        zone_id = resource.get('zone_id')

        if not zone_id:
            self.log.warning(
                "Cannot delete record set, missing zone_id: "
                f"{resource.get('name')} (ID: {recordset_id})"
            )
            return

        try:
            request = DeleteRecordSetRequest(zone_id=zone_id, recordset_id=recordset_id)
            client.delete_record_set(request)
            self.log.info(
                f"Successfully deleted record set: {resource.get('name')} (ID: {recordset_id})"
            )
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to delete record set {resource.get('name')} (ID: {recordset_id}): {e}"
            )
            raise


@RecordSet.action_registry.register('update')
class UpdateRecordSetAction(HuaweiCloudBaseAction):
    """Update DNS Record Set operation.

    :example:

    .. code-block:: yaml

        policies:
          - name: dns-recordset-update-ttl
            resource: huaweicloud.dns-recordset
            filters:
              - type: record-type
                value: A
              - type: value
                key: ttl
                op: lt
                value: 300
    """

    schema = type_schema(
        'update',
        ttl={'type': 'integer'},
        records={'type': 'array', 'items': {'type': 'string'}},
        description={'type': 'string'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        recordset_id = resource['id']
        zone_id = resource.get('zone_id')

        if not zone_id:
            self.log.warning(
                "Cannot update record set, missing zone_id: "
                f"{resource.get('name')} (ID: {recordset_id})"
            )
            return

        ttl = self.data.get('ttl')
        records = self.data.get('records')
        description = self.data.get('description')

        if not any([ttl, records, description]):
            self.log.info(
                "No need to update record set, update parameters not provided: "
                f"{resource.get('name')} (ID: {recordset_id})"
            )
            return

        try:
            update_info = UpdateRecordSetReq()
            if ttl is not None:
                update_info.ttl = ttl
            if records is not None:
                update_info.records = records
            if description is not None:
                update_info.description = description

            request = UpdateRecordSetRequest(
                zone_id=zone_id, recordset_id=recordset_id, body=update_info
            )
            client.update_record_set(request)
            self.log.info(
                f"Successfully updated record set: {resource.get('name')} (ID: {recordset_id})"
            )
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to update record set {resource.get('name')} (ID: {recordset_id}): {e}"
            )
            raise


@RecordSet.action_registry.register('set-status')
class SetRecordSetStatusAction(HuaweiCloudBaseAction):
    """Set DNS Record Set status operation.

    :example:

    .. code-block:: yaml

        policies:
          - name: dns-recordset-disable
            resource: huaweicloud.dns-recordset
            filters:
              - type: record-type
                value: A
            actions:
              - type: set-status
                status: DISABLE
    """

    schema = type_schema(
        'set-status',
        required=['status'],
        status={'type': 'string', 'enum': ['ENABLE', 'DISABLE']}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        recordset_id = resource['id']
        status = self.data.get('status')

        try:
            request_body = SetRecordSetsStatusRequestBody(status=status)
            request = SetRecordSetsStatusRequest(recordset_id=recordset_id, body=request_body)
            client.set_record_sets_status(request)
            self.log.info(
                f"Successfully set record set status to {status}: "
                f"{resource.get('name')} (ID: {recordset_id})"
            )
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to set record set status {resource.get('name')} (ID: {recordset_id}): {e}"
            )
            raise


@RecordSet.action_registry.register('batch-set-status')
class BatchSetRecordSetStatusAction(HuaweiCloudBaseAction):
    """Batch set DNS Record Set status operation.

    :example:

    .. code-block:: yaml

        policies:
          - name: dns-recordset-batch-disable
            resource: huaweicloud.dns-recordset
            filters:
              - type: record-type
                value: A
              - type: zone-id
                value: ff8080825b8fc86c015b94bc6f8712c3
            actions:
              - type: batch-set-status
                status: DISABLE
    """

    schema = type_schema(
        'batch-set-status',
        required=['status'],
        status={'type': 'string', 'enum': ['ENABLE', 'DISABLE']}
    )

    def process(self, resources):
        """Process batch record set status settings.

        According to the SDK definition, BatchSetRecordSetsStatusRequest
        only needs a body parameter, which contains status and recordset_ids.
        We don't need the zone_id parameter.
        The API path is /v2.1/recordsets/statuses.
        """
        if not resources:
            return resources

        client = self.manager.get_client()
        status = self.data.get('status')

        recordset_ids = [r.get('id') for r in resources if r.get('id')]
        if not recordset_ids:
            self.log.warning("No record set IDs found to set status for")
            return resources

        try:
            request_body = BatchSetRecordSetsStatusRequestBody(
                status=status, recordset_ids=recordset_ids
            )
            request = BatchSetRecordSetsStatusRequest(body=request_body)
            client.batch_set_record_sets_status(request)
            self.log.info(
                f"Successfully batch set status for {len(recordset_ids)} record sets to {status}"
            )
        except exceptions.ClientRequestException as e:
            self.log.error(f"Batch setting record set status failed: {e}")
            raise

        return resources

    def perform_action(self, resource):
        pass
