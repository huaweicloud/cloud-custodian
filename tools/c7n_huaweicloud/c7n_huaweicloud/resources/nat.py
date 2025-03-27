# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdknat.v2 import (
    DeleteNatGatewayRequest,
    DeleteNatGatewaySnatRuleRequest,
    DeleteNatGatewayDnatRuleRequest
)

log = logging.getLogger("custodian.huaweicloud.resources.nat")


@resources.register('nat-gateway')
class NatGateway(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'nat_gateway'
        enum_spec = ("list_nat_gateways", 'nat_gateways', 'marker')
        id = 'id'
        tag = True


@resources.register('nat-snat-rule')
class NatSnatRule(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'nat_snat_rule'
        enum_spec = ("list_nat_gateway_snat_rules", 'snat_rules', 'marker')
        id = 'id'
        tag = True


@resources.register('nat-dnat-rule')
class NatDnatRule(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'nat_dnat_rule'
        enum_spec = ("list_nat_gateway_dnat_rules", 'dnat_rules', 'marker')
        id = 'id'
        tag = True


@NatGateway.action_registry.register("delete")
class NatGatewayDelete(HuaweiCloudBaseAction):
    """Delete NAT Gateways.

    :Example:

    . code-block:: yaml

        policies:
          - name: delete-nat-gateway
            resource: huaweicloud.nat_gateway
            filters:
              - type: value
                key: name
                value: "nat_gateway"
            actions:
              - delete
    """

    schema = type_schema("delete")

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = DeleteNatGatewayRequest(nat_gateway_id=resource["id"])
        try:
            response = client.delete_nat_gateway(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        log.info("Delete NAT Gateway %s succeeded.", resource["id"])
        return response


@NatSnatRule.action_registry.register("delete")
class NatSnatRuleDelete(HuaweiCloudBaseAction):
    """Delete NAT SNAT RULE.

    :Example:

    . code-block:: yaml

        policies:
          - name: delete-nat-snat-rule
            resource: huaweicloud.nat_snat_rule
            filters:
              - type: value
                key: name
                value: "nat_snat_rule"
            actions:
              - delete
    """

    schema = type_schema("delete")

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = DeleteNatGatewaySnatRuleRequest(nat_gateway_id=resource["nat_gateway_id"],
                                                  snat_rule_id=resource["id"])
        try:
            response = client.delete_nat_gateway_snat_rule(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        log.info("Delete NAT Snat Rule %s succeeded.", resource["id"])
        return response


@NatDnatRule.action_registry.register("delete")
class NatDnatRuleDelete(HuaweiCloudBaseAction):
    """Delete NAT DNAT RULE.

    :Example:

    . code-block:: yaml

        policies:
          - name: delete-nat-dnat-rule
            resource: huaweicloud.nat_dnat_rule
            filters:
              - type: value
                key: name
                value: "nat_dnat_rule"
            actions:
              - delete
    """

    schema = type_schema("delete")

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = DeleteNatGatewayDnatRuleRequest(nat_gateway_id=resource["nat_gateway_id"],
                                                  dnat_rule_id=resource["id"])
        try:
            response = client.delete_nat_gateway_dnat_rule(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        log.info("Delete NAT Dnat Rule %s succeeded.", resource["id"])
        return response
