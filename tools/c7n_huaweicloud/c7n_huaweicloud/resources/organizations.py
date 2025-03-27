# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import json

from huaweicloudsdkorganizations.v1 import (
    PolicyTachReqBody,
    AttachPolicyRequest,
    TagDto,
    CreatePolicyRequest,
    CreatePolicyReqBody,
    ListEntitiesRequest,
    PolicySummaryDto,
    ListPoliciesRequest,
    ListRootsRequest,
)
from c7n.utils import type_schema
from c7n.filters import Filter, ValueFilter, ListItemFilter
from c7n.actions import Action
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import DefaultMarkerPagination, QueryResourceManager, TypeInfo
from c7n.exceptions import PolicyValidationError
from c7n.utils import local_session

log = logging.getLogger("custodian.huaweicloud.resources.organizations")
DEFAULT_LIMIT_SIZE = 200


@resources.register('org-policy')
class OrgPolicy(QueryResourceManager):
    policy_types = (
        "service_control_policy",
        "tag_policy",
    )

    class resource_type(TypeInfo):
        service = 'org-policy'
        enum_spec = ("list_policies", 'policies', 'marker')
        id = 'id'


@resources.register('org-account')
class OrgAccount(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'org-account'
        enum_spec = ("list_accounts", 'accounts', 'marker')
        id = 'id'


@resources.register('org-unit')
class OrgUnit(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'org-unit'
        enum_spec = ("list_organizational_units", 'organizational_units', 'marker')
        id = 'id'
        permissions_augment = (
            "organizations:ListChildren",
            "organizations:DescribeOrganizationalUnit",
            "organizations:ListTagsForResource",
        )


@OrgAccount.action_registry.register("set-policy")
@OrgUnit.action_registry.register("set-policy")
class SetPolicy(Action):
    """Set a policy on an org unit or account

    .. code-block:: yaml

        policies:
            - name: create-and-attach-scp
                resource: huaweicloud.org-unit
                filters:
                - type: value
                    key: id
                    value: ^ou-[0-9a-z]{8,32}$
                    op: regex
                actions:
                - type: set-policy
                    policy-type: service_control_policy
                    name: RestrictedForOU
                    contents:
                    Version: "5.0"
                    Statement:
                        - Sid: RestrictedForOU
                          Effect: Deny
                          Action:
                            - "ecs:*"
                          Resource:
                            - "*"

    .. code-block:: yaml

        policies:
            - name: create-and-attach-scp-for-account
                resource: huaweicloud.org-account
                filters:
                - type: value
                    key: status
                    value: active
                actions:
                - type: set-policy
                    policy-type: service_control_policy
                    name: RestrictedForAccount
                    contents:
                    Version: "5.0"
                    Statement:
                        - Sid: RestrictedForAccount
                        Effect: Deny
                        Action:
                            - "ecs:*"
                        Resource:
                            - "*"
    """

    schema = type_schema(
        "set-policy",
        required=["name", "policy-type"],
        **{
            "name": {"type": "string"},
            "description": {"type": "string"},
            "policy-type": {"enum": OrgPolicy.policy_types},
            "contents": {"type": "object"},
            "tags": {"$ref": "#/definitions/string_dict"},
        },
    )
    permissions = ("organizations:AttachPolicy", "organizations:CreatePolicy")

    def process(self, resources):
        client = local_session(self.manager.session_factory).client("org-policy")
        pid = self.ensure_scp(client)
        for r in resources:
            request = AttachPolicyRequest(policy_id=pid)
            request.body = PolicyTachReqBody(entity_id=r["id"])
            client.attach_policy(request)

    def ensure_scp(self, client):
        pmanager = self.manager.get_resource_manager(
            "org-policy", {"query": [{"filter": self.data["policy-type"]}]}
        )
        policies = pmanager.resources()
        found = False
        for p in policies:
            if p["name"] == self.data["name"]:
                found = p
                break
        if found:
            return found["id"]
        elif not self.data.get("contents"):
            raise PolicyValidationError(
                "Policy references not existent org policy " "without specifying contents"
            )
        ptags = [TagDto(key=k, value=v) for k, v in self.data.get("tags", {}).items()]
        ptags.append(TagDto(key="managed-by", value="CloudCustodian"))
        request = CreatePolicyRequest()
        request.body = CreatePolicyReqBody(
            name=self.data["name"],
            description=self.data.get("description", "%s (custodian managed)" % self.data["name"]),
            type=self.data["policy-type"],
            content=json.dumps(self.data["contents"]),
            tags=ptags,
        )
        response = client.create_policy(request)
        return response.policy.policy_summary.id


@OrgUnit.filter_registry.register("org-unit")
@OrgAccount.filter_registry.register("org-unit")
class OrgUnitFilter(ValueFilter):
    """Filter resources by their containment within an ou.

    .. code-block:: yaml

        policies:
          - name: org-units-by-parent-ou
            resource: huaweicloud.org-unit
            filters:
              - type: org-unit
                key: Name
                value: dev

          - name: org-accounts-by-parent-ou
            resource: huaweicloud.org-unit
            filters:
              - type: org-unit
                key: Name
                value: dev
    """

    schema = type_schema("org-unit", rinherit=ValueFilter.schema)
    targetCache = {}

    def process(self, resources, event={'debug': True}):
        res = super().process(resources, event)
        return res

    def __call__(self, r):
        client = local_session(self.manager.session_factory).client("org-unit")
        return self.process_entity(r['id'], client)

    def process_entity(self, entityId, client):
        request = ListEntitiesRequest(child_id=entityId)
        client.list_entities(request)
        parent_info = client.list_entities(request).entities
        if len(parent_info) == 0:
            return False

        if parent_info[0].id == self.data['value'] or (
            self.targetCache.get(parent_info[0].id, None) is not None
            and self.targetCache[parent_info[0].id]
        ):
            self.targetCache[parent_info[0].id] = True
            return True
        else:
            self.targetCache[parent_info[0].id] = self.process_entity(parent_info[0].id, client)
            return self.targetCache[parent_info[0].id]


class AccountHierarchy:
    def get_accounts_for_ous(self, client, ous):
        """get a set of accounts for the given ous ids"""
        account_ids = set()
        for ou_id in ous:
            for child in self._list_children_pagination(client, ou_id):
                if child.type == 'account':
                    account_ids.add(child.id)
                else:
                    for c in self.get_accounts_for_ous(client, [child.id]):
                        account_ids.add(c)
        return account_ids

    def _list_children_pagination(self, client, entityId):
        client = local_session(self.manager.session_factory).client("org-unit")
        resources = []
        request = ListEntitiesRequest(parent_id=entityId)
        while 1:
            response = client.list_entities(request)
            children_info = response.entities

            if children_info is None or len(children_info) == 0:
                return resources
            # merge result
            resources = resources + children_info
            next_page_params = DefaultMarkerPagination(DEFAULT_LIMIT_SIZE).get_next_page_params(
                response
            )
            if next_page_params:
                request.limit = next_page_params['limit']
                request.marker = next_page_params['marker']
            else:
                return resources


@OrgAccount.filter_registry.register("ou")
class OrganizationUnit(Filter, AccountHierarchy):
    schema = type_schema("ou", units={"type": "array", "items": {"type": "string"}})
    permissions = ("organizations:ListChildren",)

    def process(self, resources, event=None):
        client = local_session(self.manager.session_factory).client("org-account")
        account_ids = self.get_accounts_for_ous(client, self.data["units"])
        results = []
        for r in resources:
            if r["id"] not in account_ids:
                continue
            results.append(r)
        return results


@OrgUnit.filter_registry.register("policy")
@OrgAccount.filter_registry.register("policy")
class PolicyFilter(ListItemFilter):
    schema = type_schema(
        "policy",
        required=["policy-type"],
        **{
            "policy-type": {"enum": OrgPolicy.policy_types},
            "inherited": {"type": "boolean"},
            "attrs": {"$ref": "#/definitions/filters_common/list_item_attrs"},
            "count": {"type": "number"},
            "count_op": {"$ref": "#/definitions/filters_common/comparison_operators"},
        },
    )

    permissions = ("organizations:ListRoots", "organizations:ListPoliciesForTarget")

    annotate_items = True
    item_annotation_key = "c7n:PolicyMatches"
    target_policies = None
    ou_root = None
    client = None

    def process(self, resources, event):
        self.client = local_session(self.manager.session_factory).client("org-policy")
        if self.data.get("inherited") and self.manager.type == "org-account":
            # Get ou account hierarchy / parents
            hierarchy_manager = self.manager.get_resource_manager(
                "org-account", {"filters": ["org-unit"]}
            )
            ou_assembly = hierarchy_manager.filters[0]
            ou_assembly.ou_map = {
                ou["id"]: ou for ou in self.manager.get_resource_manager("org-unit").resources()
            }
            # ou_assembly.process_accounts(resources, event)
            # also initialize root for accounts as we dont store it as a parent.
            request = ListRootsRequest()
            self.ou_root = self.client.list_roots(request).roots[0]
        self.target_policies = {}
        return super().process(resources, event)

    def get_targets(self, resource):
        if not self.data.get("inherited"):
            yield resource["id"]
            return

        # handle ous
        if self.manager.type == "org-unit":
            yield resource["id"]
            for p in self.get_paraent_ids(resource["id"]):
                yield p
            return

        # handle accounts
        yield resource["id"]
        for p in self.get_paraent_ids(resource["id"]):
            yield p

        # finally the root
        yield self.ou_root.id

    def get_paraent_ids(self, entityId):
        request = ListEntitiesRequest(child_id=entityId)
        self.client.list_entities(request)
        paraent_ids = set()
        parent_info = self.client.list_entities(request).entities

        if len(parent_info) == 0:
            return paraent_ids
        else:
            paraent_ids.add(parent_info[0].id)
            paraent_ids.union(self.get_paraent_ids(parent_info[0].id))
            return paraent_ids

    def get_item_values(self, resource):
        rpolicies = {}
        for tgt_id in self.get_targets(resource):
            if tgt_id not in self.target_policies:
                request = ListPoliciesRequest(attached_entity_id=tgt_id)
                PolicySummaryDto
                policies = self.client.list_policies(request).policies
                self.target_policies[tgt_id] = policies
            for p in self.target_policies[tgt_id]:
                rpolicies[p.id] = p.to_dict()

        return list(rpolicies.values())
