# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import logging

from huaweicloudsdkconfig.v1 import ListPolicyAssignmentsRequest, \
    ListPolicyStatesByAssignmentIdRequest

from c7n.filters import ValueFilter
from c7n.utils import local_session, type_schema

from c7n.filters import Filter
from c7n_huaweicloud.provider import resources


class ConfigCompliance(Filter):
    """Filter resources by their compliance with one or more Huawei config rules.

    An example of using the filter to find all resources that have
    been registered as non compliant in the last 30 days against two
    custom Huawei Config rules.

    :example:

    .. code-block:: yaml

       policies:
         - name: non-compliant-ec2
           resource: ec2
           filters:
            - type: config-compliance
              eval_filters:
               - type: value
                 key: ResultRecordedTime
                 value_type: age
                 value: 30
                 op: less-than
              rules:
               - custodian-ec2-encryption-required
               - custodian-ec2-tags-required

    """
    log = logging.getLogger("custodian.huaweicloud.actions.filters.ConfigCompliance")

    schema = type_schema(
        'config-compliance',
        required=('rules',),
        op={'enum': ['or', 'and']},
        eval_filters={'type': 'array', 'items': {
            'oneOf': [
                {'$ref': '#/definitions/filters/valuekv'},
                {'$ref': '#/definitions/filters/value'}]}},
        states={'type': 'array', 'items': {'enum': [
            'Compliant', 'NonCompliant']}},
        rules={'type': 'array', 'items': {'type': 'string'}})
    annotation_key = 'huaweicloud:config-compliance'

    def get_resource_map(self, filters):
        rule_names = self.data.get('rules')
        states = self.data.get('states', ['NonCompliant'])
        if len(states) == 1:
            state = states[0]
        else:
            state = None

        op = self.data.get('op', 'or') == 'or' and any or all

        client = local_session(self.manager.session_factory).client('config')
        resource_map = {}

        for rule_name in rule_names:
            policy_request = ListPolicyAssignmentsRequest(policy_assignment_name=rule_name)
            policy_response = client.list_policy_assignments(request=policy_request)
            policy_id = policy_response.value and policy_response.value[0].id or None
            if not policy_id:
                self.log.error("Can not find config rules of %s", rule_name)
                continue

            state_request = ListPolicyStatesByAssignmentIdRequest(policy_assignment_id=policy_id,
                                                                  compliance_state=state)
            state_response = client.list_policy_states_by_assignment_id(request=state_request)
            state_items = state_response.value

            for state_item in state_items:
                if not filters:
                    resource_map.setdefault(
                        state_item.resource_id, []).append(state_item.to_dict())
                    continue
                if op([f.match(state_item.to_dict()) for f in filters]):
                    resource_map.setdefault(
                        state_item.resource_id, []).append(state_item.to_dict())

        return resource_map

    def process(self, resources, event=None):
        filters = []
        for f in self.data.get('eval_filters', ()):
            vf = ValueFilter(f)
            vf.annotate = False
            filters.append(vf)

        resource_map = self.get_resource_map(filters)

        results = []
        for resource in resources:
            resource_id = resource["id"]
            if resource_id in resource_map:
                resource[self.annotation_key] = resource_map[resource_id]
                results.append(resource)
        return results

    @classmethod
    def register_resources(klass, registry, resource_class):
        """model resource subscriber on resource registration.

        Watch for new resource types being registered if they are
        supported by aws config, automatically, register the
        config-compliance filter.
        """
        resource_type = resource_class.resource_type
        config_resource_support = getattr(resource_type, 'config_resource_support', None)
        if config_resource_support:
            resource_class.filter_registry.register('config-compliance', klass)


resources.subscribe(ConfigCompliance.register_resources)
