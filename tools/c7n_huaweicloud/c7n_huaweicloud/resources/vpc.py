# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import json
import netaddr
import os

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkvpc.v2 import (
    ListPortsRequest,
    UpdateFlowLogReq,
    UpdateFlowLogRequest,
    UpdateFlowLogReqBody,
    DeleteFlowLogRequest,
    CreateFlowLogRequest,
    CreateFlowLogReq,
    CreateFlowLogReqBody,
    AllowedAddressPair as AllowedAddressPairV2,
    UpdatePortOption,
    UpdatePortRequest,
    UpdatePortRequestBody,
    DeleteVpcPeeringRequest,
    ListRouteTablesRequest,
    ShowRouteTableRequest
)
from huaweicloudsdkvpc.v3 import (
    ListSecurityGroupsRequest,
    ListSecurityGroupRulesRequest,
    DeleteSecurityGroupRequest,
    DeleteSecurityGroupRuleRequest,
    BatchCreateSecurityGroupRulesRequest,
    BatchCreateSecurityGroupRulesRequestBody,
    BatchCreateSecurityGroupRulesOption,
    ShowAddressGroupRequest,
    AllowedAddressPair as AllowedAddressPairV3,
    UpdateSubNetworkInterfaceOption,
    UpdateSubNetworkInterfaceRequest,
    UpdateSubNetworkInterfaceRequestBody
)

from c7n.exceptions import PolicyValidationError
from c7n.filters import Filter, ValueFilter
from c7n.utils import type_schema, local_session
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

log = logging.getLogger("custodian.huaweicloud.resources.vpc")


@resources.register('vpc')
class Vpc(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'vpc_v2'
        enum_spec = ('list_vpcs', 'vpcs', 'marker')
        id = 'id'


@resources.register('vpc-port')
class Port(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'vpc_v2'
        enum_spec = ('list_ports', 'ports', 'marker')
        id = 'id'
        tag_resource_type = ''


@Port.filter_registry.register("port-forwarding")
class PortForwarding(Filter):
    """Filter to network interfaces that have port forwarding enabled.

    :example:

    .. code-block:: yaml

        policies:
          - name: eni-port-forwarding-enabled
            resource: huaweicloud.vpc-port
            filters:
              - port-forwarding

    """

    schema = type_schema('port-forwarding')

    def process(self, resources, event=None):
        enabled_ports = []
        for r in resources:
            pairs = r.get('allowed_address_pairs')
            if pairs:
                for pair in pairs:
                    if pair.get('ip_address') == '1.1.1.1/0':
                        enabled_ports.append(r)
                        break

        return enabled_ports


@Port.action_registry.register("disable-port-forwarding")
class PortDisablePortForwarding(HuaweiCloudBaseAction):
    """Action to disable port forwarding on network interfaces.

    :example:

    .. code-block:: yaml

        policies:
          - name: eni-disable-port-forwarding
            resource: huaweicloud.vpc-port
            filters:
              - port-forwarding
            actions:
              - disable-port-forwarding
    """

    schema = type_schema("disable-port-forwarding")

    def perform_action(self, resource):
        device_owner = resource.get('device_owner', '')
        is_subeni = ('compute:subeni' == device_owner)
        client = self.manager.get_resource_manager('vpc-security-group').get_client() \
            if is_subeni else self.manager.get_client()
        raw_pairs = resource.get('allowed_address_pairs')
        new_pairs = []
        if raw_pairs:
            for pair in raw_pairs:
                pair_ip = pair.get('ip_address')
                if pair_ip == '1.1.1.1/0':
                    continue
                pair_mac = pair.get('mac_address')
                if not is_subeni:
                    new_pair = AllowedAddressPairV2(ip_address=pair_ip, mac_address=pair_mac)
                else:
                    new_pair = AllowedAddressPairV3(ip_address=pair_ip, mac_address=pair_mac)
                new_pairs.append(new_pair)
        if not is_subeni:
            port_body = UpdatePortOption(allowed_address_pairs=new_pairs)
            request = UpdatePortRequest()
            request.port_id = resource['id']
            request.body = UpdatePortRequestBody(port=port_body)
            response = client.update_port(request)
        else:
            request = UpdateSubNetworkInterfaceRequest()
            request.sub_network_interface_id = resource['id']
            subeni_body = UpdateSubNetworkInterfaceOption(allowed_address_pairs=new_pairs)
            request.body = UpdateSubNetworkInterfaceRequestBody(
                sub_network_interface=subeni_body)
            response = client.update_sub_network_interface(request)
        return response


@resources.register('vpc-security-group')
class SecurityGroup(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'vpc'
        enum_spec = ('list_security_groups', 'security_groups', 'marker')
        id = 'id'
        tag_resource_type = 'security-groups'


@SecurityGroup.action_registry.register("delete")
class SecurityGroupDelete(HuaweiCloudBaseAction):
    """Action to delete vpc security groups.

    :example:

    .. code-block:: yaml

        policies:
          - name: security-group-delete-test-name
            resource: huaweicloud.vpc-security-group
            filters:
              - type: value
                key: name
                value: "sg-test"
            actions:
              - delete
    """

    schema = type_schema("delete")

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = DeleteSecurityGroupRequest(security_group_id=resource["id"])
        response = client.delete_security_group(request)
        log.info("Delete security group %s response is: [%d] %s" %
                 (resource["id"], response.status_code, response.to_json_object()))
        return response


@SecurityGroup.filter_registry.register("unattached")
class SecurityGroupUnAttached(Filter):
    """Filter to just vpc security groups that are not attached to any ports
    and are not default one.

    :example:

    .. code-block:: yaml

            policies:
              - name: security-groups-unattached
                resource: huaweicloud.vpc-security-group
                filters:
                  - unattached

    """

    schema = type_schema('unattached')

    def process(self, resources, event=None):
        sg_ids = [r['id'] for r in resources]
        sg_ids = list(set(sg_ids))
        client = self.manager.get_resource_manager('vpc-port').get_client()
        try:
            request = ListPortsRequest(security_groups=sg_ids)
            response = client.list_ports(request)
        except exceptions.ClientRequestException as ex:
            log.exception("Unable to filter unattached security groups because query ports failed."
                          "RequestId: %s, Reason: %s." %
                          (ex.request_id, ex.error_msg))
        ports_object = response.ports
        ports = [p.to_dict() for p in ports_object]
        port_sgs = []
        for port in ports:
            port_sgs.extend(port['security_groups'])
        port_sgs = list(set(port_sgs))
        unattached = [r for r in resources if r['id'] not in port_sgs and r['name'] != 'default']

        return unattached


@SecurityGroup.filter_registry.register('without_specific_tags')
class SecurityGroupWithoutSpecificTags(Filter):
    """Filter vpc security groups unassociated with specific tags.

    If `associate_type` is `any`, it means that security groups that
    do not have any of the tags in `keys` are filtered out.

    And `associate_type` is `all`, it means that security groups that
    do not have all of the tags in `keys` are filtered out.

    :example:

    .. code-block:: yaml

            policies:
              - name: security-groups-without-specific-tags
                resource: huaweicloud.vpc-security-group
                filters:
                  - type: without_specific_tags
                    keys: ['key1', 'key2']
                    associate_type: any
    """

    schema = type_schema('without_specific_tags',
                        keys={'type': 'array',
                              'items': {'type': 'string'}},
                        associate_type={'type': 'string',
                                        'enum': ['any', 'all']},
                        required=['keys'])

    def process(self, resources, event=None):
        results = []
        keys = self.data.get('keys')
        associate_type = self.data.get('associate_type', 'any')
        num_key = len(keys)

        for r in resources:
            count = 0
            tags = r['tags']
            for tag in tags:
                if tag['key'] in keys:
                    count += 1
            if 'all' == associate_type and count != num_key:
                results.append(r)
            elif 'any' == associate_type and count == 0:
                results.append(r)

        return results


@resources.register('vpc-security-group-rule')
class SecurityGroupRule(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'vpc'
        enum_spec = ('list_security_group_rules', 'security_group_rules', 'marker')
        id = 'id'
        tag_resource_type = ''


class SecurityGroupRuleFilter(Filter):
    """Filter for verifying security group ingress and egress rules

    All attributes of a security group rule are available as
    value filters.

    If multiple attributes are specified the rule must satisfy
    all of them. Note that within an attribute match against a list value
    of a rule we default to or.

    If a group has any rules that match all conditions, then it
    matches the filter.

    Rules that match on the group are annotated onto the group and
    can subsequently be used by the remove-rules action.

    We have specialized handling for matching `AnyInPorts` or `AllInPorts`
    in ingress/egress rule `multiport`. The following example matches on ingress
    rules which allow for a range that includes all of the given ports.

    .. code-block:: yaml

      - type: ingress
        AllInPorts: [22, 443, 80]

    And the following example matches on ingress rules which allow
    for a range that includes any of the given ports.

    .. code-block:: yaml

      - type: ingress
        AnyInPorts: [22, 443, 80]

    As well for verifying that a rule not allow for a specific set of ports
    as in the following example. The delta between this and the previous
    example is that if the rule allows for any ports not specified here,
    then the rule will match. ie. `NotInPorts` is a negative assertion match,
    it matches when a rule includes ports outside of the specified set.

    .. code-block:: yaml

      - type: ingress
        NotInPorts: [22]

    The list item of `AnyInPorts`, `AllInPorts` and `NotInPorts` could be
    a integer or a port range representing by a string, like [22, '33-40'].

    If you want to filter out rules that allow all ports, please use `AllPorts`,
    which is a boolean parameter as follows.

    .. code-block:: yaml

      - type: ingress
        AllPorts: True

    We also have specialized handling for matching self-references in
    ingress/egress permissions. The following example matches on ingress
    rules which allow traffic its own same security group.

    .. code-block:: yaml

      - type: ingress
        SelfReference: True

    We can filter out the rules of the default security group using `DefaultSG`,
    as shown in the following example.

    .. code-block:: yaml

      - type: ingress
        DefaultSG: True

    If `DefaultSG` is False, this filter matches the rules of non-default
    security groups. And if you want to filter out the rules of all
    security groups, including default and non-default, do not set
    `DefaultSG` parameter.

    `SGReferenceIds` can be used to filter out security group references in rules
    by a list of security group ids.

    .. code-block:: yaml

      - type: ingress
        SGReferenceIds: ['8fcdbf49-21b5-41a2-ad0e-51402828c443']

    We can also filter address group references based on the ids of refered
    address groups by `AGReferenceIds`.

    .. code-block:: yaml

      - type: ingress
        AGReferenceIds: ['fe2850f1-9bfe-41e6-be6d-3641a387ca27']

    By default, this filter matches a security group rule if
    _all_ of its keys match. Using `or` block causes a match
    if _any_ key matches. This can help consolidate some simple
    cases that would otherwise require multiple filters. To find
    security groups that allow all inbound traffic over IPv4 or IPv6,
    for example, we can use two filters inside an `or` block:

    .. code-block:: yaml

      - or:
        - type: ingress
          RemoteIpPrefix: "0.0.0.0/0"
        - type: ingress
          RemoteIpPrefix: "::/0"

    Note that evaluating _combinations_ of factors (e.g. traffic over
    port 22 from 0.0.0.0/0) still requires separate filters.
    """

    perm_attrs = {
        'RemoteIpPrefix', 'SGRuleIds', 'SecurityGroupIds', 'Descriptions',
        'Ethertypes', 'Action', 'Priorities', 'Protocols', 'SGReferenceIds',
        'AGReferenceIds'}
    filter_attrs = {
        'AnyInPorts', 'AllInPorts', 'NotInPorts', 'AllPorts', 'SelfReference',
        'DefaultSG'}
    attrs = perm_attrs.union(filter_attrs)
    attrs.add('match-operator')

    def validate(self):
        delta = set(self.data.keys()).difference(self.attrs)
        delta.remove('type')
        if delta:
            raise PolicyValidationError("Unknown keys %s on %s" % (
                ", ".join(delta), self.manager.data))
        return self

    def process(self, resources, event=None):
        self.vfilters = []
        fattrs = list(sorted(self.perm_attrs.intersection(self.data.keys())))
        for f in fattrs:
            fv = self.data.get(f)
            if isinstance(fv, dict):
                fv['key'] = f
            else:
                fv = {f: fv}
            vf = ValueFilter(fv, self.manager)
            vf.annotate = False
            self.vfilters.append(vf)
        self.default_sg = ''
        if self.data.get('DefaultSG', None) is not None:
            client = self.manager.get_client()
            try:
                list_name = ['default']
                request = ListSecurityGroupsRequest(name=list_name)
                response = client.list_security_groups(request)
                sgs = response.security_groups
                if len(sgs) > 0:
                    sgs = [sg.to_dict() for sg in sgs]
                    self.default_sg = sgs[0].get('id')
            except exceptions.ClientRequestException as ex:
                log.exception("Unable to query defauly security group."
                              "RequestId: %s, Reason: %s." %
                              (ex.request_id, ex.error_msg))
        return super(SecurityGroupRuleFilter, self).process(resources, event)

    def process_direction(self, rule):
        return self.direction == rule['direction']

    def process_ips(self, rule):
        found = None
        if 'RemoteIpPrefix' in self.data:
            match_value = self.data['RemoteIpPrefix']
            found = ('remote_ip_prefix' in rule and match_value == rule['remote_ip_prefix']) or \
                    ('remote_ip_prefix' not in rule and str(match_value) == '-1')
        return found

    def process_protocols(self, rule):
        found = None
        if 'Protocols' in self.data:
            match_value = self.data['Protocols']
            if -1 in match_value:
                match_value.remove(-1)
                match_value.append('-1')
            protocol = rule['protocol'] if 'protocol' in rule else '-1'
            found = protocol in match_value
        return found

    def process_items(self, rule, filter_key, rule_key):
        found = None
        if filter_key in self.data:
            items = self.data[filter_key]
            if isinstance(items, list):
                found = rule_key in rule and rule[rule_key] in items
            elif isinstance(items, str):
                found = rule_key in rule and rule[rule_key] == items
        return found

    def _extend_ports(self, req_port_list):
        if not req_port_list:
            return []
        int_port_list = []
        for item in req_port_list:
            if isinstance(item, int):
                int_port_list.append(item)
            elif isinstance(item, str):
                port_range = item.split('-')
                if len(port_range) == 1:
                    int_port_list.append(port_range[0])
                elif len(port_range) == 2:
                    start = int(port_range[0])
                    end = int(port_range[1])
                    if start >= end:
                        continue
                    ports = [i for i in range(start, end + 1)]
                    int_port_list.extend(ports)
            else:
                continue
        return int_port_list

    def process_ports(self, rule):
        all_ports = self.data['AllPorts'] if 'AllPorts' in self.data else False
        # rule matches when allows all ports(1-65535)
        if all_ports is True:
            if 'multiport' not in rule:
                return True
            else:
                multiport = self._extend_ports(rule.get('multiport').split(','))
                return len(multiport) == 65535

        any_in_ports = self.data['AnyInPorts'] if 'AnyInPorts' in self.data else []
        all_in_ports = self.data['AllInPorts'] if 'AllInPorts' in self.data else []
        not_in_ports = self.data['NotInPorts'] if 'NotInPorts' in self.data else []

        any_in_ports = self._extend_ports(any_in_ports)
        all_in_ports = self._extend_ports(all_in_ports)
        not_in_ports = self._extend_ports(not_in_ports)

        if not any_in_ports and not all_in_ports and not not_in_ports:
            return True
        multiport = rule.get('multiport', '-1')
        if multiport == '-1':
            return (any_in_ports or all_in_ports) and not not_in_ports
        rule_port_list = multiport.split(',')
        single_rule_ports = []
        range_rule_ports = []
        for port_item in rule_port_list:
            if '-' in port_item:
                range_rule_ports.append(port_item)
            else:
                single_rule_ports.append(int(port_item))

        # rule matches when all ports of rule in `AllInPorts`
        all_in_found = True
        for port in all_in_ports:
            if port in single_rule_ports:
                all_in_found = True
                continue
            else:
                all_in_found = any(port >= int(port_range.split('-')[0])
                                   and port <= int(port_range.split('-')[1])
                                   for port_range in range_rule_ports)
            if not all_in_found:
                break

        # rule matches when any port of rule in `AnyInPorts`
        any_in_found = True
        for port in any_in_ports:
            if port in single_rule_ports:
                any_in_found = True
            else:
                any_in_found = any(port >= int(port_range.split('-')[0])
                                   and port <= int(port_range.split('-')[1])
                                   for port_range in range_rule_ports)
            if any_in_found:
                break

        # rule matches when all ports of rule not in `NotInPorts`
        not_in_found = True
        for port in not_in_ports:
            if port in single_rule_ports:
                not_in_found = False
                break
            else:
                not_in_found = all(port < int(port_range.split('-')[0])
                                   or port > int(port_range.split('-')[1])
                                   for port_range in range_rule_ports)

        return all_in_found and any_in_found and not_in_found

    def process_self_reference(self, rule):
        found = None
        ref_match = self.data.get('SelfReference')
        if ref_match is not None:
            found = False
        if ref_match is True and 'remote_group_id' in rule:
            found = (rule['remote_group_id'] == rule['security_group_id'])
        if ref_match is False:
            found = ('remote_group_id' not in rule) or ('remote_group_id' in rule
                    and rule['remote_group_id'] != rule['security_group_id'])
        return found

    def process_default_sg(self, rule):
        found = None
        if self.default_sg:
            rule_sg_id = rule['security_group_id']
            found = (self.default_sg == rule_sg_id)\
                if self.data.get('DefaultSG') else (self.default_sg != rule_sg_id)
        return found

    def __call__(self, resource):
        matched = []
        match_op = self.data.get('match-operator', 'and') == 'and' and all or any
        perm_matches = {}

        perm_matches['direction'] = self.process_direction(resource)
        perm_matches['ips'] = self.process_ips(resource)
        perm_matches['sg_rule_ids'] = self.process_items(resource, 'SGRuleIds', 'id')
        perm_matches['sg_ids'] = self.process_items(resource, 'SecurityGroupIds',
                                                    'security_group_id')
        perm_matches['descriptions'] = self.process_items(resource, 'Descriptions', 'description')
        perm_matches['ethertypes'] = self.process_items(resource, 'Ethertypes', 'ethertype')
        perm_matches['priorities'] = self.process_items(resource, 'Priorities', 'priority')
        perm_matches['sg_reference_ids'] = self.process_items(resource, 'SGReferenceIds',
                                                              'remote_group_id')
        perm_matches['ag_reference_ids'] = self.process_items(resource, 'AGReferenceIds',
                                                              'remote_address_group_id')
        perm_matches['protocols'] = self.process_protocols(resource)
        perm_matches['ports'] = self.process_ports(resource)
        perm_matches['self_reference'] = self.process_self_reference(resource)
        perm_matches['action'] = self.process_items(resource, 'Action', 'action')
        perm_matches['default'] = self.process_default_sg(resource)

        perm_match_values = list(filter(
            lambda x: x is not None, perm_matches.values()))
        # account for one python behavior any([]) == False, all([]) == True
        if match_op == all and not perm_match_values:
            return False

        match = match_op(perm_match_values)
        if match:
            matched.append(resource)

        if matched:
            resource.setdefault('Matched%s' % self.direction.capitalize(), [])
            # If the same rule matches multiple filters, only add it to the match annotation
            # once. Note: Because we're looking for unique dicts and those aren't hashable,
            # we can't conveniently use set() to de-duplicate rules.
            return True


SGRuleSchema = {
    'match-operator': {'type': 'string', 'enum': ['or', 'and']},
    'RemoteIpPrefix': {
        'oneOf': [
            {'enum': [-1]},
            {'type': 'string'}
        ]
    },
    'SGRuleIds': {'type': 'array', 'items': {'type': 'string'}},
    'Descriptions': {'type': 'array', 'items': {'type': 'string'}},
    'SecurityGroupIds': {'type': 'array', 'items': {'type': 'string'}},
    'SGReferenceIds': {'type': 'array', 'items': {'type': 'string'}},
    'AGReferenceIds': {'type': 'array', 'items': {'type': 'string'}},
    'Ethertypes': {'type': 'array', 'items': {'type': 'string',
                                              'enum': ['IPv4', 'IPv6', 'ipv4', 'ipv6']}},
    'Action': {'type': 'string', 'enum': ['allow', 'deny']},
    'Priorities': {'type': 'array', 'items': {'type': 'integer'}},
    'Protocols': {
        'type': 'array', 'items': {
            'oneOf': [
                {'enum': ['-1', 'tcp', 'udp', 'icmp', 'icmpv6']},
                {'type': 'integer'}
            ]
        }
    },
    'AnyInPorts': {
        'type': 'array', 'items': {
            'oneOf': [
                {'type': 'string'},
                {'type': 'integer', 'minimum': 0, 'maximum': 65535}
            ]
        }
    },
    'AllInPorts': {
        'type': 'array', 'items': {
            'oneOf': [
                {'type': 'string'},
                {'type': 'integer', 'minimum': 0, 'maximum': 65535}
            ]
        }
    },
    'NotInPorts': {
        'type': 'array', 'items': {
            'oneOf': [
                {'type': 'string'},
                {'type': 'integer', 'minimum': 0, 'maximum': 65535}
            ]
        }
    },
    'AllPorts': {'type': 'boolean'},
    'SelfReference': {'type': 'boolean'},
    'DefaultSG': {'type': 'boolean'}
}


@SecurityGroupRule.filter_registry.register("ingress")
class SecurityGroupRuleIngress(SecurityGroupRuleFilter):
    direction = "ingress"
    schema = {
        'type': 'object',
        'additionalProperties': False,
        'properties': {'type': {'enum': ['ingress']}},
        'required': ['type']}
    schema['properties'].update(SGRuleSchema)


@SecurityGroupRule.filter_registry.register("egress")
class SecurityGroupRuleEgress(SecurityGroupRuleFilter):
    direction = "egress"
    schema = {
        'type': 'object',
        'additionalProperties': False,
        'properties': {'type': {'enum': ['egress']}},
        'required': ['type']}
    schema['properties'].update(SGRuleSchema)


@SecurityGroupRule.action_registry.register("delete")
class SecurityGroupRuleDelete(HuaweiCloudBaseAction):
    """Action to delete vpc security group rules.

    :example:

    .. code-block:: yaml

        policies:
          - name: security-group-rule-delete-tcp-22
            resource: huaweicloud.vpc-security-group-rule
            filters:
              - type: ingress
                RemoteIpPrefix: '0.0.0.0/0'
                Protocols: ['tcp']
                AllInPorts: [22]
            actions:
              - delete
    """

    schema = type_schema("delete")

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = DeleteSecurityGroupRuleRequest(security_group_rule_id=resource["id"])
        response = client.delete_security_group_rule(request)
        log.info("Delete security group rule %s response is: [%d] %s" %
                 (resource["id"], response.status_code, response.to_json_object()))
        return response


@SecurityGroupRule.action_registry.register('remove-rules')
class RemoveSecurityGroupRules(HuaweiCloudBaseAction):
    """Action to remove ingress/egress rule(s) from a security group.

    :example:

    .. code-block:: yaml

            policies:
              - name: security-group-remove-tcp-8080-rules
                resource: huaweicloud.vpc-security-group-rule
                filters:
                  - type: ingress
                    Protocols: ['tcp']
                    AllInPorts: [8080]
                actions:
                  - type: remove-rules
                    ingress: matched

    """
    schema = type_schema(
        'remove-rules',
        ingress={'type': 'string', 'enum': ['matched', 'all']},
        egress={'type': 'string', 'enum': ['matched', 'all']})

    def process(self, resources):
        i_mode = self.data.get('ingress', 'matched')
        e_mode = self.data.get('egress', 'matched')

        client = self.manager.get_client()
        sg_ids = [r['security_group_id'] for r in resources]
        sg_ids = list(set(sg_ids))
        ret_rules = []
        for direction, mode in [('ingress', i_mode), ('egress', e_mode)]:
            rules = [r for r in resources if direction == r['direction']]
            # remove matched rules
            if mode == 'matched':
                self.perform_action(rules)
                ret_rules.extend(rules)
            # remove all rules in the security group of the matched rules
            elif mode == 'all':
                try:
                    request = ListSecurityGroupRulesRequest(security_group_id=sg_ids,
                                                            direction=direction)
                    response = client.list_security_group_rules(request)
                except exceptions.ClientRequestException as ex:
                    log.exception("Unable to remove all rules because query %s rules "
                                  "failed. RequestId: %s, Reason: %s." %
                                  (direction, ex.request_id, ex.error_msg))
                    continue

                all_rules_object = response.security_group_rules
                all_rules = [r.to_dict() for r in all_rules_object]
                self.perform_action(all_rules)
                ret_rules.extend(all_rules)
            # remove rules with a list of rule filter conditions
            elif isinstance(mode, list):
                for f in mode:
                    try:
                        request = ListSecurityGroupRulesRequest(security_group_id=sg_ids,
                                                                direction=direction)
                        f = dict(f)
                        for key, value in f.items():
                            setattr(request, key, value)
                        response = client.list_security_group_rules(request)
                        to_delete_rules_object = response.security_group_rules
                        to_delete_rules = [r.to_dict() for r in to_delete_rules_object]
                    except exceptions.ClientRequestException as ex:
                        log.exception("Unable to remove specified rules because query "
                                      "%s rules failed. "
                                      "RequestId: %s, Reason: %s." %
                                      (direction, ex.request_id, ex.error_msg))
                        continue
                    self.perform_action(to_delete_rules)
                    ret_rules.extend(to_delete_rules)

        return self.process_remove_result(ret_rules)

    def process_remove_result(self, resources):
        remove_result = {"remove_succeeded_rules": [], "remove_failed_rules": self.failed_resources}
        remove_result.get("remove_succeeded_rules").extend(resources)
        return remove_result

    def perform_action(self, rules):
        client = self.manager.get_client()
        for r in rules:
            try:
                request = DeleteSecurityGroupRuleRequest(security_group_rule_id=r["id"])
                client.delete_security_group_rule(request)
            except exceptions.ClientRequestException as ex:
                res = r.get("id")
                log.exception("Unable to submit action against the resource - %s "
                              "RequestId: %s, Reason: %s" %
                              (res, ex.request_id, ex.error_msg))
                self.handle_exception(r, rules)


@SecurityGroupRule.action_registry.register('set-rules')
class SetSecurityGroupRules(HuaweiCloudBaseAction):
    """Action to add/remove ingress/egress rule(s) to a security group

    :example:

    .. code-block:: yaml

       policies:
         - name: security-group-set-rules
           resource: huaweicloud.vpc-security-group-rule
           filters:
            - type: ingress
              RemoteIpPrefix: '192.168.21.0/24'
              Protocols: ['tcp']
              AllInPorts: [8080]
           actions:
            - type: set-rules
              # remove the rule matched by a previous ingress filter.
              remove-ingress: matched
              # remove rules by specifying them fully, ie remove default outbound
              # access.
              remove-egress:
                - action: allow
                  remote_ip_prefix: '0.0.0.0/0'
                - action: allow
                  remote_ip_prefix: '::/0'

              # add a list of rules to the security group.
              add-ingress:
                # full syntax/parameters to create rules can be used.
                - ethertype: ipv4
                  multiport: '22'
                  remote_ip_prefix: '192.168.22.0/24'
                  protocol: tcp
                - ethertype: ipv4
                  protocol: tcp
                  multiport: '3389'
                  remote_ip_prefix: '10.0.0.0/8'
                  action: allow
                  priotity: 1
              # add a list of egress rules to a security group
              add-egress:
                - ethertype: ipv4
                  multiport: '22'
                  remote_ip_prefix: '192.168.22.0/24'
                  protocol: tcp
    """
    schema = type_schema(
        'set-rules',
        **{'add-ingress': {'type': 'array', 'items': {'type': 'object', 'minProperties': 1}},
           'remove-ingress': {'oneOf': [
               {'enum': ['all', 'matched']},
               {'type': 'array', 'items': {'type': 'object', 'minProperties': 2}}]},
           'add-egress': {'type': 'array', 'items': {'type': 'object', 'minProperties': 1}},
           'remove-egress': {'oneOf': [
               {'enum': ['all', 'matched']},
               {'type': 'array', 'items': {'type': 'object', 'minProperties': 2}}]}}
    )

    def process(self, resources):
        i_rules = self.data.get('add-ingress', ())
        e_rules = self.data.get('add-egress', ())

        sg_ids = [r['security_group_id'] for r in resources]
        sg_ids = list(set(sg_ids))
        client = self.manager.get_client()
        ret_rules = []
        # add rules
        add_failed = False
        for sg_id in sg_ids:
            try:
                request = BatchCreateSecurityGroupRulesRequest()
                request.security_group_id = sg_id
                create_rules = []
                for direction, rules in [('ingress', i_rules), ('egress', e_rules)]:
                    for r in rules:
                        rule_option = BatchCreateSecurityGroupRulesOption(direction=direction)
                        r = dict(r)
                        for key, value in r.items():
                            setattr(rule_option, key, value)
                        create_rules.append(rule_option)
                if not create_rules:
                    continue
                request.body = \
                    BatchCreateSecurityGroupRulesRequestBody(security_group_rules=create_rules)
                response = client.batch_create_security_group_rules(request)
            except exceptions.ClientRequestException as ex:
                log.exception("Unable to add rules in security group %s. "
                              "RequestId: %s, Reason: %s" %
                              (sg_id, ex.request_id, ex.error_msg))
                add_failed = True
                break
            res_rules_object = response.security_group_rules
            res_rules = [r.to_dict() for r in res_rules_object]
            ret_rules.extend(res_rules)
        # revert added rules if add rules failed
        if add_failed:
            for rule in ret_rules:
                try:
                    request = DeleteSecurityGroupRuleRequest(security_group_rule_id=rule['id'])
                    response = client.delete_security_group_rule(request)
                except exceptions.ClientRequestException as ex:
                    log.exception("Unable to delete rule %s in security group %s. "
                                  "RequestId: %s, Reason: %s" %
                                  (rule['id'], rule['security_group_id'],
                                   ex.request_id, ex.error_msg))
            return {}

        # remove rules
        remover = RemoveSecurityGroupRules(
            {'ingress': self.data.get('remove-ingress', ()),
             'egress': self.data.get('remove-egress', ())}, self.manager)
        remove_result = remover.process(resources)

        return self.process_multi_result(ret_rules, remove_result)

    def process_multi_result(self, add_rules, remove_result):
        multi_result = {"add_succeeded_rules": [], "add_failed_rules": []}
        multi_result.get("add_succeeded_rules").extend(add_rules)
        multi_result.update(remove_result)
        return multi_result

    def perform_action(self, resource):
        return None


@SecurityGroupRule.filter_registry.register("rule-allow-risk-ports")
class SecurityGroupRuleAllowRiskPort(Filter):
    """Filter for security group rules that allow high risk ports.

    :Example:

    .. code-block:: yaml

       policies:
         - name: sg-rule-allow-high-risk-port
           resource: huaweicloud.security-group-rule
           filters:
             - type: rule-allow-risk-ports
               direction: ingress
               risk_ports_path: ""
               trust_sg_path: ""
               trust_ip_path: ""
    """

    schema = type_schema("rule-allow-risk-ports",
                         direction={'enum': ['ingress', 'egress']},
                         risk_ports_path={'type': 'string'},
                         trust_sg_path={'type': 'string'},
                         trust_ip_path={'type': 'string'},
                         required=['direction', 'risk_ports_path'])

    def process(self, resources, event=None):
        results = []
        risk_ports_path = self.data.get('risk_ports_path')
        trust_sg_path = self.data.get('trust_sg_path')
        trust_ip_path = self.data.get('trust_ip_path')
        direction = self.data.get('direction')
        if not risk_ports_path:
            log.error("risk-ports-path is required")
            return []
        risk_ports_obj = self.get_file_content(risk_ports_path)
        trust_sg_obj = self.get_file_content(trust_sg_path)
        trust_ip_obj = self.get_file_content(trust_ip_path)
        # {sg_id : deny_rules}
        deny_rule_map = {}
        extend_trust_ip_obj = {}
        if risk_ports_obj:
            if trust_ip_obj:
                extend_trust_ip_obj = self._extend_ip_map(trust_ip_obj)
            for rule in resources:
                if rule.get('direction') != direction or rule.get('action') != 'allow':
                    continue
                protocol = rule.get('protocol')
                if not protocol:
                    results.append(rule)
                    continue
                risk_ports = self._extend_ports(risk_ports_obj.get(protocol))
                ports = rule.get('multiport')
                port_list = []
                if ports:
                    ports = ports.split(',')
                    port_list = self._extend_ports(ports)
                    risk_rule_ports = [p for p in port_list if p in risk_ports]
                else:
                    risk_rule_ports = risk_ports
                if not risk_rule_ports:
                    continue
                sg = rule['security_group_id']
                if sg not in deny_rule_map:
                    deny_rules = self.get_deny_rules(sg, direction)
                    new_sg = {sg: deny_rules}
                    deny_rule_map.update(new_sg)
                deny_rules = deny_rule_map.get(sg)
                ethertype = rule.get('ethertype')
                for deny_rule in deny_rules:
                    if protocol == deny_rule.get('protocol') and \
                       ethertype == deny_rule.get('ethertype'):
                        deny_ports = deny_rule.get('multiport')
                        if not deny_ports:
                            risk_rule_ports = []
                            break
                        deny_ports = self._extend_ports(deny_ports.split(','))
                        risk_rule_ports = [p for p in risk_rule_ports if p not in deny_ports]
                # trust sg
                risk_rule_ports = self._handle_trust_port(trust_sg_obj,
                                                          protocol,
                                                          sg,
                                                          risk_rule_ports)
                if not risk_rule_ports:
                    continue
                # trust ip
                rule_ip = rule.get('remote_ip_prefix')
                rule_ag_id = rule.get('remote_address_group_id')
                if rule_ip and rule_ip != '0.0.0.0/0' and rule_ip.endswith('/32'):
                    rule_ip_int = int(netaddr.IPAddress(rule_ip[:-3]))
                    risk_rule_ports = self._handle_trust_port(extend_trust_ip_obj,
                                                              protocol,
                                                              rule_ip_int,
                                                              risk_rule_ports)
                elif rule_ag_id:
                    client = self.manager.get_client()
                    ips = []
                    try:
                        request = ShowAddressGroupRequest(address_group_id=rule_ag_id)
                        response = client.show_address_group(request)
                        ag = response.address_group.to_dict()
                        ips = ag['ip_set']
                    except exceptions.ClientRequestException as ex:
                        log.exception("Unable to show remote address group in security group "
                                      "rule %s RequestId: %s, Reason: %s." %
                                      (rule_ag_id, ex.request_id, ex.error_msg))
                    trust_all_ips = True
                    for ip in ips:
                        if '/' in ip and not ip.endswith('/32'):
                            trust_all_ips = False
                            break
                        ip = ip[:-3] if ip.endswith('/32') else ip
                        ip_int = int(netaddr.IPAddress(ip))
                        if self._handle_trust_port(extend_trust_ip_obj, protocol,
                                                   ip_int, risk_rule_ports):
                            trust_all_ips = False
                            break
                    if trust_all_ips:
                        risk_rule_ports = []

                if risk_rule_ports:
                    results.append(rule)

        return results

    def _handle_trust_port(self, trust_obj, protocol, key, risk_rule_ports):
        if key not in trust_obj:
            return risk_rule_ports
        trust_map = trust_obj.get(key)
        trust_port = []
        if protocol in trust_map:
            trust_port = trust_map.get(protocol)
        elif 'all' in trust_map:
            trust_port = trust_map.get('all')
        if trust_port:
            trust_port = self._extend_ports(trust_port)
            return [p for p in risk_rule_ports if p not in trust_port]
        return risk_rule_ports

    def get_file_content(self, obs_url):
        if not obs_url:
            return {}
        obs_client = local_session(self.manager.session_factory).client("obs")
        protocol_end = len("https://")
        path_without_protocol = obs_url[protocol_end:]
        obs_bucket_name = self.get_obs_name(path_without_protocol)
        obs_server = self.get_obs_server(path_without_protocol)
        obs_file = self.get_file_path(path_without_protocol)
        obs_client.server = obs_server
        try:
            resp = obs_client.getObject(bucketName=obs_bucket_name,
                                        objectKey=obs_file,
                                        loadStreamInMemory=True)
            if resp.status < 300:
                content = json.loads(resp.body.buffer)
                return content
            else:
                log.error(f"get obs object failed: {resp.errorCode}, {resp.errorMessage}")
                return None
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise

    def get_obs_name(self, obs_url):
        last_obs_index = obs_url.rfind(".obs")
        return obs_url[:last_obs_index]

    def get_obs_server(self, obs_url):
        last_obs_index = obs_url.rfind(".obs")
        remaining_after_obs = obs_url[last_obs_index:]
        split_res = remaining_after_obs.split("/", 1)
        return split_res[0].lstrip(".")

    def get_file_path(self, obs_url):
        last_obs_index = obs_url.rfind(".obs")
        remaining_after_obs = obs_url[last_obs_index:]
        split_res = remaining_after_obs.split("/", 1)
        return split_res[1]

    def get_multiport(self, risk_ports):
        multiport = ''
        if len(risk_ports) == 1:
            multiport = str(risk_ports[0])
            return multiport
        order_ports = risk_ports
        order_ports.sort()
        start = order_ports[0]
        end = order_ports[0]
        port_len = len(order_ports)
        for i in range(0, port_len - 1):
            if order_ports[i + 1] == order_ports[i] + 1:
                end = order_ports[i + 1]
            else:
                end = order_ports[i]
                if start == end:
                    port_item_str = str(start)
                else:
                    port_item_str = str(start) + '-' + str(end)
                multiport += port_item_str + ','
                start = order_ports[i + 1]
        if end == order_ports[-1]:
            port_item_str = str(start) + '-' + str(end)
            multiport += port_item_str
        else:
            port_item_str = str(start)
            multiport += port_item_str
        return multiport

    def get_deny_rules(self, sg_id, direction):
        client = self.manager.get_client()
        sg_ids = [sg_id]
        action = 'deny'
        ret_rules = []
        try:
            request = ListSecurityGroupRulesRequest(security_group_id=sg_ids,
                                                    action=action,
                                                    direction=direction)
            response = client.list_security_group_rules(request)
            deny_rules_object = response.security_group_rules
            deny_rules = [r.to_dict() for r in deny_rules_object]
        except exceptions.ClientRequestException as ex:
            log.exception("Unable to list deny rules in security group %s"
                          "RequestId: %s, Reason: %s." %
                          (sg_id, ex.request_id, ex.error_msg))
        for r in deny_rules:
            ip = r.get('remote_ip_prefix')
            if not ip or ip in ('0.0.0.0/0', '::/0'):
                ret_rules.append(r)
        return ret_rules

    def _extend_ports(self, req_port_list):
        if not req_port_list:
            return []
        int_port_list = []
        for item in req_port_list:
            if isinstance(item, int):
                int_port_list.append(item)
            elif isinstance(item, str):
                port_range = item.split('-')
                if len(port_range) == 1:
                    int_port_list.append(int(port_range[0]))
                elif len(port_range) == 2:
                    start = int(port_range[0])
                    end = int(port_range[1])
                    if start >= end:
                        continue
                    ports = [i for i in range(start, end + 1)]
                    int_port_list.extend(ports)
            else:
                continue
        return list(set(int_port_list))

    def _extend_ip_map(self, ip_obj):
        extended_ip_obj = {}
        for key, value in ip_obj.items():
            int_ips = []
            if ',' in key:
                ips = key.split(',')
                for ip in ips:
                    ip = ip.strip()
                    if '-' in ip:
                        ip_range = ip.split('-')
                        if ip_range[0] < ip_range[1]:
                            ip_start = int(netaddr.IPAddress(ip_range[0]))
                            ip_end = int(netaddr.IPAddress(ip_range[1]))
                            int_ips.extend([i for i in range(ip_start, ip_end + 1)])
                    else:
                        int_ips.append(int(netaddr.IPAddress(ip)))
            elif '-' in key:
                ip_range = key.split('-')
                if ip_range[0] < ip_range[1]:
                    ip_start = int(netaddr.IPAddress(ip_range[0]))
                    ip_end = int(netaddr.IPAddress(ip_range[1]))
                    int_ips.extend([i for i in range(ip_start, ip_end + 1)])
            else:
                int_ips.append(int(netaddr.IPAddress(key)))
            for int_ip in int_ips:
                extended_ip_obj[int_ip] = value
        return extended_ip_obj


@SecurityGroupRule.action_registry.register("deny-risk-ports")
class SecurityGroupRuleDenyRiskPorts(HuaweiCloudBaseAction):
    """Action to add deny rules that contain high risk ports.

    :example:

    .. code-block:: yaml

        policies:
          - name: deny-high-risk-ports
            resource: huaweicloud.vpc-security-group-rule
            filters:
              - type: rule-allow-risk-ports
                direction: ingress
                risk_ports_path: ""
                trust_sg_path: ""
                trust_ip_path: ""
            actions:
              - deny-risk-ports
    """

    schema = type_schema("deny-risk-ports")
    post_keys = ['direction', 'ethertype', 'protocol', 'multiport', 'remote_ip_prefix',
                'remote_group_id', 'remote_address_group_id', 'priority']

    def process(self, resources):
        client = self.manager.get_client()
        rule_map = {}
        for r in resources:
            sg_id = r['security_group_id']
            if sg_id not in rule_map:
                rule_map.update({sg_id: []})
            rule_map.get(sg_id).append(r)

        ret_rules = []
        for sg_id in rule_map.keys():
            try:
                request = BatchCreateSecurityGroupRulesRequest()
                request.security_group_id = sg_id
                create_rules = []
                rules = rule_map.get(sg_id)
                action = 'deny'
                for r in rules:
                    rule_option = BatchCreateSecurityGroupRulesOption(action=action)
                    for key, value in r.items():
                        if key in self.post_keys:
                            setattr(rule_option, key, value)
                    if 'protocol' not in r:
                        setattr(rule_option, 'protocol', 'tcp')
                    create_rules.append(rule_option)
                if not create_rules:
                    continue
                request.body = \
                    BatchCreateSecurityGroupRulesRequestBody(security_group_rules=create_rules,
                                                             ignore_duplicate=True)
                response = client.batch_create_security_group_rules(request)
            except exceptions.ClientRequestException as ex:
                log.exception("Unable to add rules in security group %s. "
                              "RequestId: %s, Reason: %s" %
                              (sg_id, ex.request_id, ex.error_msg))
                break
            res_rules_object = response.security_group_rules
            res_rules = [r.to_dict() for r in res_rules_object]
            ret_rules.extend(res_rules)
        return self.process_result(ret_rules)

    def perform_action(self, resource):
        return None


@resources.register('vpc-flow-log')
class FlowLog(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'vpc_v2'
        enum_spec = ('list_flow_logs', 'flow_logs', 'marker')
        id = 'id'
        tag_resource_type = ''


@FlowLog.action_registry.register("set-flow-log")
class SetFlowLog(HuaweiCloudBaseAction):
    """Action to set flow logs for a network resource.

    :example:

    .. code-block:: yaml

        policies:
          - name: vpc-enable-flow-logs
            resource: huaweicloud.vpc-flow-log
            filters:
              - type: value
                key: resource_type
                value: vpc
              - type: value
                key: resource_type
                value: DOWN
            actions:
              - type: set-flow-log
                action: enable

    `create-attrs` can be used to create flow logs of the specified
    network resources. You don't need to input `resource_type` and
    `resource_id` params, for example create a flow log to collect
    all traffic:

    .. code-block:: yaml

      - type: set-flow-log
        action: create
        create-attrs:
          - traffic_type: all
            log_group_id: '324d2393-7d89-4262-88b1-c5d3497d5f54'
            log_topic_id: '2fa117ad-3452-4367-b360-88cb89f8a561'

    """

    schema = type_schema(
        'set-flow-log',
        required=['action'],
        **{'action': {'enum': ['enable', 'disable', 'create', 'delete']},
           'create-attrs': {'type': 'array', 'items': {'type': 'object'}}})

    def process(self, resources):
        action = self.data['action']
        client = self.manager.get_client()
        ret_fls = []
        if action in ['enable', 'disable']:
            admin_state = True if action == 'enable' else False
            for fl in resources:
                try:
                    request = UpdateFlowLogRequest(flowlog_id=fl['id'])
                    fl_body = UpdateFlowLogReq(admin_state=admin_state)
                    request.body = UpdateFlowLogReqBody(flow_log=fl_body)
                    response = client.update_flow_log(request)
                    resp_fl = response.flow_log
                    ret_fls.append(resp_fl.to_dict())
                except exceptions.ClientRequestException as ex:
                    log.exception("Failed to %s flow log. "
                                  "RequestId: %s, Reason: %s." %
                                  (action, ex.request_id, ex.error_msg))
                    self.handle_exception(fl, resources)
        elif action == 'delete':
            for fl in resources:
                try:
                    request = DeleteFlowLogRequest(flowlog_id=fl['id'])
                    response = client.delete_flow_log(request)
                    ret_fls.append(fl)
                except exceptions.ClientRequestException as ex:
                    log.exception("Failed to %s flow log. "
                                  "RequestId: %s, Reason: %s." %
                                  (action, ex.request_id, ex.error_msg))
                    self.handle_exception(fl, resources)
        elif action == 'create':
            req_fls = self.data.get('create-attrs', ())
            resource_ids = [f['resource_id'] for f in resources]
            resource_ids = list(set(resource_ids))
            if not resource_ids:
                return self.process_fl_result(ret_fls, action)
            resource_type = resources[0]['resource_type']
            for r in resource_ids:
                for fl in req_fls:
                    try:
                        request = CreateFlowLogRequest()
                        fl_body = CreateFlowLogReq(resource_type=resource_type, resource_id=r)
                        fl = dict(fl)
                        for key, value in fl.items():
                            setattr(fl_body, key, value)
                        request.body = CreateFlowLogReqBody(flow_log=fl_body)
                        response = client.create_flow_log(request)
                        resp_fl = response.flow_log
                        ret_fls.append(resp_fl.to_dict())
                    except exceptions.ClientRequestException as ex:
                        log.exception("Failed to %s flow log. "
                                      "RequestId: %s, Reason: %s." %
                                      (action, ex.request_id, ex.error_msg))

        return self.process_fl_result(ret_fls, action)

    def perform_action(self, resource):
        return None

    def process_fl_result(self, resources, action):
        action_result = {"action": action}
        self.result.get("succeeded_resources").extend(resources)
        self.result.update(action_result)
        return self.result


@resources.register('vpc-peering')
class Peering(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'vpc_v2'
        enum_spec = ('list_vpc_peerings', 'peerings', 'marker')
        id = 'id'


@Peering.filter_registry.register("cross-account")
class PeeringCrossAccount(Filter):
    """Filter to query VPC peering connections across accounts.

    :example:

    .. code-block:: yaml

            policies:
              - name: peering-cross-account
                resource: huaweicloud.vpc-peering
                filters:
                  - cross-account

    """

    schema = type_schema('cross-account')

    def process(self, resources, event=None):
        res = []
        for r in resources:
            if 'request_vpc_info' not in r or 'accept_vpc_info' not in r:
                continue
            request_tenant = r['request_vpc_info']['tenant_id']
            accept_tenant = r['accept_vpc_info']['tenant_id']
            if request_tenant != accept_tenant:
                res.append(r)

        return res


@Peering.filter_registry.register("missing-route")
class PeeringMissingRoute(Filter):
    """Return active VPC peering connections which are missing a route
    in route tables.

    If the peering connection is between two vpcs in the same account,
    the connection is returned unless it is in present route tables in
    each vpc.

    If the peering connection is between accounts, then the local vpc's
    route table is checked.

    :example:

    .. code-block:: yaml

            policies:
              - name: peering-missing-route
                resource: huaweicloud.vpc-peering
                filters:
                  - missing-route

    """

    schema = type_schema('missing-route')

    def process(self, resources, event=None):
        res = []
        current_tenant = os.getenv('HUAWEI_PROJECT_ID')
        for r in resources:
            if r['status'] != 'ACTIVE':
                continue
            is_across_accounts = False
            request_tenant = r['request_vpc_info']['tenant_id']
            accept_tenant = r['accept_vpc_info']['tenant_id']
            if request_tenant != accept_tenant:
                is_across_accounts = True
            request_vpc = r['request_vpc_info']['vpc_id']
            accept_vpc = r['accept_vpc_info']['vpc_id']
            peering_id = r['id']
            if is_across_accounts:
                for vpc, tenant in [(request_vpc, request_tenant), (accept_vpc, accept_tenant)]:
                    if tenant == current_tenant and self._is_missing_route(vpc, peering_id):
                        res.append(r)
            else:
                if self._is_missing_route(request_vpc, peering_id) or \
                    self._is_missing_route(accept_vpc, peering_id):
                    res.append(r)

        return res

    def _is_missing_route(self, vpc_id, peering_id):
        client = self.manager.get_client()
        try:
            request = ListRouteTablesRequest(vpc_id=vpc_id)
            response = client.list_route_tables(request)
            rtbs = response.routetables
            if len(rtbs) == 0:
                return True
            rtb_ids = [rtb.to_dict()['id'] for rtb in rtbs]

            is_route_exist = False
            for rtb_id in rtb_ids:
                request = ShowRouteTableRequest(routetable_id=rtb_id)
                response = client.show_route_table(request)
                routes = response.routetable.to_dict().get('routes')
                is_route_exist = any(route['type'] == 'peering'
                                    and route['nexthop'] == peering_id
                                    for route in routes)
                if is_route_exist:
                    return False
        except exceptions.ClientRequestException as ex:
            log.exception("Failed to check missing route because "
                        "query routetables of %s failed. "
                        "RequestId: %s, Reason: %s." %
                        (vpc_id, ex.request_id, ex.error_msg))
        return not is_route_exist


@Peering.action_registry.register("delete")
class PeeringDelete(HuaweiCloudBaseAction):
    """Action to delete vpc peering connections.

    :example:

    .. code-block:: yaml

        policies:
          - name: peering-delete-rejected
            resource: huaweicloud.vpc-peering
            filters:
              - type: value
                key: status
                value: "REJECTED"
            actions:
              - delete
    """

    schema = type_schema("delete")

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = DeleteVpcPeeringRequest(peering_id=resource["id"])
        response = client.delete_vpc_peering(request)
        log.info("Delete vpc peering %s response is: [%d] %s" %
                (resource["id"], response.status_code, response.to_json_object()))
        return response
