# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import time

from requests.exceptions import HTTPError

from c7n.utils import type_schema, local_session
from c7n.filters import Filter
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction

from huaweicloudsdksmn.v2 import (
    PublishMessageRequest,
    PublishMessageRequestBody,
)
from huaweicloudsdkvpc.v3 import ListVpcsRequest
from huaweicloudsdkcore.exceptions import exceptions

from huaweicloudsdkvpcep.v1 import (
    UpdateEndpointPolicyRequest,
    UpdateEndpointPolicyRequestBody,
    UpdateEndpointServiceRequest,
    UpdateEndpointServiceRequestBody,
    PolicyStatement,
    ListServiceDescribeDetailsRequest,
    ListEndpointInfoDetailsRequest
)

from huaweicloudsdkorganizations.v1 import ShowOrganizationRequest

log = logging.getLogger('custodian.huaweicloud.resources.vpcep')


@resources.register('vpcep-ep')
class VpcEndpoint(QueryResourceManager):
    """Huawei Cloud VPC Endpoint Resource Manager

    :example:

    .. code-block:: yaml

        policies:
          - name: list-vpc-endpoints
            resource: huaweicloud.vpcep-ep
    """

    class resource_type(TypeInfo):
        service = 'vpcep-ep'
        enum_spec = ('list_endpoints', 'endpoints', 'offset')
        id = 'id'
        name = 'endpoint_service_name'
        filter_name = 'endpoint_service_name'
        filter_type = 'scalar'
        taggable = True
        tag_resource_type = 'endpoint'

    def augment(self, resources):
        if not resources:
            # Return a fake resource
            return [{"fake-resource": True}]
        return resources


@resources.register('vpcep-eps')
class VpcEndpointService(QueryResourceManager):
    """Huawei Cloud VPC Endpoint Service Resource Manager

    :example:

    .. code-block:: yaml

        policies:
          - name: list-vpc-endpoint-services
            resource: huaweicloud.vpcep-eps
    """

    class resource_type(TypeInfo):
        service = 'vpcep-eps'
        enum_spec = ('list_endpoint_service', 'endpoint_services', 'offset')
        id = 'id'
        taggable = True
        tag_resource_type = 'endpoint_service'

    def augment(self, resources):
        if not resources:
            # Return a fake resource
            return [{"fake-resource": True}]
        return resources


@VpcEndpoint.filter_registry.register('by-service-and-vpc-check')
class VpcEndpointServiceAndVpcFilter(Filter):
    """Check endpoints with a specific service name and verify their VPC IDs

    This filter requires the endpoint_service_name parameter and optionally accepts a vpc_ids list.

    If no endpoint matching the service name is found, it will return a single item list containing
    only the service name.

    If vpc_ids is provided, it will return a list of VPC IDs that do not exist in the endpoints
    that match the service name. If all VPC IDs exist, it returns an empty list.

    :example:

    .. code-block:: yaml

        policies:
          - name: check-vpc-endpoints-for-service
            resource: huaweicloud.vpcep-ep
            filters:
              - type: by-service-and-vpc-check
                endpoint_service_name: "com.huaweicloud.service.test"
                vpc_ids: ['vpc-12345678', 'vpc-87654321']
                all_vpc: True, take effect only when vpc_ids is not configured, default false.
    """
    schema = type_schema(
        'by-service-and-vpc-check',
        endpoint_service_name={'type': 'string'},
        vpc_ids={'type': 'array', 'items': {'type': 'string'}},
        all_vpc={'type': 'boolean'},
        required=['endpoint_service_name']
    )

    def process(self, resources, event=None):
        endpoint_service_name = self.data.get('endpoint_service_name')
        vpc_ids = self.data.get('vpc_ids', [])
        all_vpc = self.data.get('all_vpc', False)

        # need check all vpcs are configured with EP
        if len(vpc_ids) <= 0 and all_vpc:
            client = local_session(self.manager.session_factory).client('vpc')
            try:
                marker = None
                limit = 200
                while True:
                    request = ListVpcsRequest()
                    request.limit = limit
                    if marker:
                        request.marker = marker
                    vpcs = client.list_vpcs(request).vpcs
                    if vpcs:
                        vpc_ids.extend([v.id for v in vpcs])
                    marker = self.get_next_marker(vpcs, limit)
                    if marker is None:
                        break
                log.debug("[filters]-The filter:[by-service-and-vpc-check] query the service:"
                          f"[/v3/{{project_id}}/vpc/vpcs] has successed. Get all vpcs:{vpc_ids}")
            except exceptions.ClientRequestException as e:
                log.error("[filters]-The filter:[by-service-and-vpc-check] query the service:"
                          f"[/v3/{{project_id}}/vpc/vpcs] failed.cause: {e}")
                raise e

        # Validate if endpoint_service_name is valid
        if not endpoint_service_name:
            return []

        # Find endpoints that match the service name
        matching_endpoints = [
            r for r in resources
            if r.get('endpoint_service_name') == endpoint_service_name
        ]

        # If no matching endpoints found, return a list containing only the service name
        if not matching_endpoints:
            log.debug("[filters]-[by-service-and-vpc-check]-"
                      f"No endpoints found with service name {endpoint_service_name}")
            return [{"endpoint_service_name": endpoint_service_name}]

        # If vpc_ids not provided, return empty list (no need to check VPCs)
        if not vpc_ids:
            return []

        # Get all vpc_ids that exist in matching endpoints
        existing_vpc_ids = {r.get('vpc_id')
                            for r in matching_endpoints if r.get('vpc_id')}

        # Find vpc_ids that don't exist in matching endpoints
        missing_vpc_ids = [
            vpc_id for vpc_id in vpc_ids if vpc_id not in existing_vpc_ids]

        # If there are missing vpc_ids, return result with missing VPC IDs
        if missing_vpc_ids:
            log.debug("[filters]-[by-service-and-vpc-check]-"
                      f"Missing VPC IDs found in service {endpoint_service_name}: "
                      f"{', '.join(missing_vpc_ids)}")
            ids_str = ', '.join(missing_vpc_ids)
            # the id here represents the id of vpc
            return [{"endpoint_service_name": endpoint_service_name, "vpc_ids": missing_vpc_ids,
                     "id": ids_str}]

        # If all vpc_ids exist, return empty list (no issues found)
        return []

    def get_next_marker(self, vpcs, limit):
        '''get the marker for pargination'''
        if len(vpcs) < limit:
            return None
        # get the last vpc_id as marker
        return vpcs[limit - 1].id


@VpcEndpoint.action_registry.register('eps-check-ep-msg')
class VpcEndpointSendMsg(HuaweiCloudBaseAction):
    """VPC Endpoint message notification action.

    Used to send notification messages about VPC endpoint configuration, including
    endpoint service name and VPC ID information.

    :example:

    .. code-block:: yaml

        policies:
          - name: vpc-endpoint-notification
            resource: huaweicloud.vpcep-ep
            filters:
              - type: by-service-and-vpc-check
                endpoint_service_name: "com.huaweicloud.service.test"
            actions:
              - type: eps-check-ep-msg
                topic_urn_list:
                  - "urn:smn:region:account-id:topic-name"
                message: "alert: xxxxx"
    """

    schema = type_schema(
        'eps-check-ep-msg',
        required=['topic_urn_list'],
        topic_urn_list={'type': 'array', 'items': {'type': 'string'}},
        message={'type': 'string'}
    )

    def process(self, resources):
        """Process message sending logic"""
        if not resources:
            return resources

        topic_urn_list = self.data.get('topic_urn_list', [])
        user_message = self.data.get(
            'message', 'Notification: VPC Endpoint Configuration Check')

        for resource in resources:
            self.perform_action(resource, topic_urn_list, user_message)

        return resources

    def perform_action(self, resource, topic_urn_list=None, user_message=None):
        """Execute message sending operation for a single resource"""
        if topic_urn_list is None:
            topic_urn_list = self.data.get('topic_urn_list', [])

        if user_message is None:
            user_message = self.data.get(
                'message', 'Notification: VPC Endpoint Configuration Check')

        endpoint_service_name = resource.get('endpoint_service_name', '')

        vpc_ids = resource.get('vpc_ids', [])
        if vpc_ids:
            vpc_id_str = ", ".join(vpc_ids)
            # Build message content for multiple VPC IDs
            message = (
                f"{user_message} Please check whether VPC ({vpc_id_str}) "
                "has VPC endpoints configured, "
                f"and whether the endpoint service name is {endpoint_service_name}."
            )
        else:
            message = (
                f"{user_message} Please check whether VPC "
                "has a VPC endpoint configured, "
                f"and whether the endpoint service name is {endpoint_service_name}."
            )

        subject = "VPC Endpoint Configuration Notification"
        body = PublishMessageRequestBody(subject=subject, message=message)

        results = []
        for topic_urn in topic_urn_list:
            publish_message_request = PublishMessageRequest(
                topic_urn=topic_urn, body=body
            )
            try:
                client = local_session(
                    self.manager.session_factory).client('smn')
                publish_message_response = client.publish_message(
                    publish_message_request)
                results.append({
                    'status': 'success',
                    'topic_urn': topic_urn,
                    'message_id': getattr(publish_message_response, 'message_id', None)
                })
                log.info("[actions]-[eps-check-ep-msg]-The resource:[vpcep-ep] "
                         f"send message to {topic_urn} has succeeded.")
            except Exception as e:
                log.error("[actions]-[eps-check-ep-msg]-The resource:[vpcep-ep] "
                          f"send message to {topic_urn} failed.cause:{e}")
                raise e
        return results


class VpcEndpointUtils():
    """Provide utils
    """

    def __init__(self, manager):
        self.manager = manager

    def get_account(self, account_list, my_account=None):
        results = account_list
        if my_account:
            results.append(my_account)
        return list(set(results))

    def generate_new_accounts(self, account_list, my_account=None):
        accounts_strip = [account.strip() for account in account_list]
        domain_ids = self.get_account(accounts_strip, my_account)
        results = []
        for d in domain_ids:
            results.append(f"domain/{d}:root")
        return results

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
            if resp.status == 200:
                return json.loads(resp.body.buffer)
            else:
                log.error(f"get obs object from {obs_url} failed:"
                          f"{resp.errorCode}, {resp.errorMessage}")
                raise HTTPError(resp.status, resp.body)
        except exceptions.ClientRequestException as e:
            log.error(f'get obs object from {obs_url} error, '
                      f'request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            raise e

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

    def get_ep_detail(self, ep_id):
        ep_client = local_session(self.manager.session_factory).client("vpcep-ep")
        request = ListEndpointInfoDetailsRequest()
        request.vpc_endpoint_id = ep_id

        try:
            response = ep_client.list_endpoint_info_details(request)
            log.info(f"get ep {ep_id} detail has succeeded.")
            return response
        except exceptions as e:
            log.error(f"get ep {ep_id} detail failed. cause:{e}")
            raise e

    def wait_ep_can_processed(self, resource):
        for i in range(20):
            if resource.get('status') not in ('creating', 'deleting'):
                return True
            time.sleep(5)
            ep_resource = self.get_ep_detail(resource.get('id'))
            if ep_resource.status not in ('creating', 'deleting'):
                return True
            log.info(f"The resource:[vpcep-ep] "
                     f"with id:[{resource.get('id')}] status {ep_resource.status}, "
                     f"is not available, wait: {i}")
            time.sleep(25)
        raise ValueError("Ep status is creating or deleting, can not update, please retry")


@VpcEndpoint.filter_registry.register('is-not-default-org-policy')
class VpcEndpointObsCheckDefultOrgPolicyFilter(Filter):
    """Check if then endpoint is configrured with default organization policy.

    This filter requires the org_accounts_obs_url parameter and optionally accepts a my_account.

    Return a list of endpoints that do not have the default organization policy configured.

    :example:

    .. code-block:: yaml

        policies:
            - name: is-not-default-org-policy
            resource: huaweicloud.vpcep-ep
            filters:
                - type: is-not-default-org-policy
                  my_account: "{my_account}"
                  org_accounts_obs_url: {accounts_obs_url}
                  org_resources_obs_url: {resources_obs_url}
    """

    schema = type_schema(
        'is-not-default-org-policy',
        my_account={'type': 'string'},
        org_accounts_obs_url={'type': 'string'},
        org_resources_obs_url={'type': 'string'}
    )

    def process(self, resources, event=None):
        if not resources:
            return []
        if not self.data.get('org_accounts_obs_url'):
            log.error("[filters]-The filter[is-not-default-org-policy] "
                      "org_accounts_obs_url is a required parameter and cannot be empty")
            raise ValueError("org_accounts_obs_url cannot be empty")
        if not self.data.get('org_resources_obs_url'):
            log.error("[filters]-The filter[is-not-default-org-policy] "
                      "org_resources_obs_url is a required parameter and cannot be empty")
            raise ValueError("org_resources_obs_url cannot be empty")
        ep_util = VpcEndpointUtils(self.manager)
        try:
            account_list = ep_util.get_file_content(self.data.get('org_accounts_obs_url'))
            if not account_list.get('accounts', []):
                log.error("[filters]-The filter[is-not-default-org-policy] "
                          "the accounts of org_accounts_obs_url cannot be empty")
                raise ValueError("accounts cannot be empty")
            resource_list = ep_util.get_file_content(self.data.get('org_resources_obs_url'))
            if not resource_list.get('resources', []):
                log.error("[filters]-The filter[is-not-default-org-policy] "
                          "the resources of org_resources_obs_url cannot be empty")
                raise ValueError("resources cannot be empty")
        except json.JSONDecodeError as e:
            log.error('[filters]-The filter[is-not-default-org-policy] '
                      'the content of org_accounts_obs_url or org_resources_obs_url is invalid, '
                      'please check format: the content of org_accounts_obs_url should be: '
                      '{"accounts": ["account_id1", "account_id2"]}, the content of '
                      'org_resources_obs_url should be: {"resources": ["resource1", "resource2"]}')
            raise e

        results = []
        new_accounts = ep_util.generate_new_accounts(account_list.get('accounts', []),
                                                     self.data.get('my_account'))
        resources_list = resource_list.get('resources', [])
        resources_strip = [resource.strip() for resource in resources_list]
        new_resources = list(set(resources_strip))

        for res in resources:
            if res.get('service_type', '') not in ['gateway', 'cvs_gateway']:
                continue

            if len(res.get('policy_statement', [])) == 2 \
                    and self._default_policy_contains_same_accounts(
                res.get('id'), res.get('policy_statement', []), new_accounts) \
                    and self._default_policy_contains_same_resources(
                res.get('id'), res.get('policy_statement', []), new_resources):
                continue
            results.append(res)
        return results

    def _default_policy_contains_same_accounts(self, ep_id, policy_statements, new_accounts):
        global default_account_policy
        if not policy_statements:
            log.info(f"[filters]-[is-not-default-org-policy]-"
                     f"The resource:[vpcep-ep] "
                     f"with id:[{ep_id}] current policies are empty,"
                     f"expect:[{new_accounts}]")
            return False
        contain_default_account_policy = False
        for policy_statement in policy_statements:
            if policy_statement.get('Sid', '') == 'allow-trusted-account-resources':
                contain_default_account_policy = True
                default_account_policy = policy_statement
        if not contain_default_account_policy:
            log.info(f"[filters]-[is-not-default-org-policy]-"
                     f"The resource:[vpcep-ep] "
                     f"with id:[{ep_id}] policies do not contain default account policy,"
                     f"expect:[{new_accounts}]")
            return False

        current_accounts = default_account_policy.get('Condition', {}).get(
            'StringEquals', {}).get('ResourceOwner', [])
        if not current_accounts:
            log.info(f"[filters]-[is-not-default-org-policy]-"
                     f"The resource:[vpcep-ep] "
                     f"with id:[{ep_id}] policiess contain default account policy, "
                     f"but account is empty,"
                     f"current:[{current_accounts}], expect:[{new_accounts}]")
            return False

        current_accounts.sort()
        new_accounts.sort()
        result = current_accounts == new_accounts
        if not result:
            log.info(f"[filters]-[is-not-default-org-policy]-"
                     f"The resource:[vpcep-ep] "
                     f"with id:[{ep_id}] policy account is invalid,"
                     f"current:[{current_accounts}], expect:[{new_accounts}]")
        return result

    def _default_policy_contains_same_resources(self, ep_id, policy_statements, new_resources):
        global default_resource_policy
        if not policy_statements:
            return False
        contain_default_resource_policy = False
        for policy_statement in policy_statements:
            if policy_statement.get('Sid', '') == 'allow-huaweicloud-public-data':
                contain_default_resource_policy = True
                default_resource_policy = policy_statement
        if not contain_default_resource_policy:
            log.info(f"[filters]-[is-not-default-org-policy]-"
                     f"The resource:[vpcep-ep] "
                     f"with id:[{ep_id}] policies do not contain default resource policy,"
                     f"expect:[{new_resources}]")
            return False

        current_resources = default_resource_policy.get('Resource', [])
        if not current_resources:
            log.info(f"[filters]-[is-not-default-org-policy]-"
                     f"The resource:[vpcep-ep] "
                     f"with id:[{ep_id}] policies contain default resource policy, "
                     f"but resource is empty,"
                     f"current:[{current_resources}], expect:[{new_resources}]")
            return False

        current_resources.sort()
        new_resources.sort()
        result = current_resources == new_resources
        if not result:
            log.info(f"[filters]-[is-not-default-org-policy]-"
                     f"The resource:[vpcep-ep] "
                     f"with id:[{ep_id}] policy resource is invalid,"
                     f"current:[{current_resources}], expect:[{new_resources}]")
        return result


@VpcEndpoint.action_registry.register('update-default-org-policy')
class VpcEndpointUpdateObsEpPolicy(HuaweiCloudBaseAction):
    """Update the endpoint policy to default organization policy.

    :example:

    .. code-block:: yaml

        policies:
          - name: update-default-org-policy
            resource: huaweicloud.vpcep-ep
            actions:
              - type: update-default-org-policy
                my_account: "{my_account}"
                org_accounts_obs_url: {accounts_obs_url}
                org_resources_obs_url: {resources_obs_url}
    """

    schema = type_schema('update-default-org-policy',
                         my_account={'type': 'string'},
                         org_accounts_obs_url={'type': 'string'},
                         org_resources_obs_url={'type': 'string'}
                         )

    def process(self, resources):
        if not resources:
            return []
        ep_util = VpcEndpointUtils(self.manager)
        account_list = ep_util.get_file_content(self.data.get('org_accounts_obs_url'))
        new_accounts = ep_util.generate_new_accounts(account_list.get('accounts', []),
                                                     self.data.get('my_account'))
        resource_list = ep_util.get_file_content(self.data.get('org_resources_obs_url'))
        resources_list = resource_list.get('resources', [])
        resources_strip = [resource.strip() for resource in resources_list]
        new_resources = list(set(resources_strip))

        for resource in resources:
            if ep_util.wait_ep_can_processed(resource):
                self.process_resource(resource, new_accounts, new_resources)

        return resources

    def process_resource(self, resource, new_accounts, new_resources):
        """Execute update policy for a single resource"""
        if resource.get('service_type', '') not in ['gateway', 'cvs_gateway']:
            return

        ep_id = resource.get("id", "")
        log.info(f"[actions]-[update-default-org-policy]-The resource:[vpcep-ep] "
                 f"with id:[{ep_id}] policy is invalid.")
        self._update_policy(resource, new_accounts, new_resources)

    def perform_action(self, resource):
        return None

    def _update_policy(self, resource, resource_owner, new_resources):
        ep_id = resource.get("id", "")
        policy_statements = [
            PolicyStatement(sid="allow-trusted-account-resources",
                            effect="Allow", action=["*"], resource=["*", "*/*"],
                            condition={"StringEquals": {"ResourceOwner": resource_owner}}),
            PolicyStatement(sid="allow-huaweicloud-public-data",
                            effect="Allow",
                            action=["HeadBucket", "ListBucket", "GetBucketLocation",
                                    "GetObject", "GetObjectVersion"],
                            resource=new_resources)
        ]

        request = UpdateEndpointPolicyRequest(vpc_endpoint_id=ep_id)
        body = UpdateEndpointPolicyRequestBody(policy_statement=policy_statements)
        request.body = body
        log.debug(f"[actions]-update-default-org-policy update policy request body: {request}")

        client = self.manager.get_client()
        try:
            client.update_endpoint_policy(request)
            log.info(f"[actions]-[update-default-org-policy]-The resource:[vpcep-ep] "
                     f"with id:[{ep_id}] updating the policy has succeeded.")
        except exceptions.ClientRequestException as e:
            log.error(f"[actions]-[update-default-org-policy]-The resource:[vpcep-ep] "
                      f"with id:[{ep_id}] update policy is failed.cause:{e}")
            raise e


def _is_principal_wildcards(statement):
    wildcards = '*'
    principal = statement.get('Principal', '')
    if not principal or principal == wildcards:
        return True
    if isinstance(principal, dict):
        for iam in principal.get('IAM', []):
            if iam == wildcards:
                return True
        for ser in principal.get('Service', []):
            if ser == wildcards:
                return True
    return False


def isSameOrgId(condition, org_id):
    string_equals = False
    string_equals_if_exists = False
    if condition.get('StringEquals') and condition.get('StringEquals').get("g:PrincipalOrgID"):
        if condition.get('StringEquals').get("g:PrincipalOrgID") == org_id:
            string_equals = True
    if condition.get('StringEqualsIfExists') \
            and condition.get('StringEqualsIfExists').get("g:ResourceOrgID"):
        if condition.get('StringEqualsIfExists').get("g:ResourceOrgID") == org_id:
            string_equals_if_exists = True
    return string_equals and string_equals_if_exists


@VpcEndpoint.filter_registry.register('policy-principal-wildcards')
class VpcEndpointPolicyPrincipalWildcardsFilter(Filter):
    """Check if endpoint policy has explicitly principal or use '*' with conditions.

    Filters ep use principal:'*' without conditions

    :example:

    .. code-block:: yaml

        policies:
          - name: policy-principal-wildcards
            resource: huaweicloud.vpcep-ep
            filters:
              - type: policy-principal-wildcards
    """
    schema = type_schema(
        'policy-principal-wildcards',
    )

    def process(self, resources, event=None):
        result = []
        eps_ids = self._get_need_check_policy_eps_ids(resources)
        for resource in resources:
            if not resource.get('service_type', '') == 'interface':
                continue
            if resource.get('endpoint_service_id') not in eps_ids:
                continue
            if not self._check_policy_document(resource.get('policy_document', {})):
                result.append(resource)
        ids = [r.get('id') for r in result]
        log.info(f"[filters]-[policy-principal-wildcards]-The resource:[vpcep-ep] "
                 f"invalid policy list:{ids}")
        return result

    def _check_policy_document(self, policy_document):
        statement = policy_document.get('Statement', [])
        if not statement:
            return False
        if len(statement) != 1:
            return False
        for item in statement:
            if _is_principal_wildcards(item) and \
                    (not item.get('Condition')
                     or not isSameOrgId(item.get('Condition'), self._get_org_id())):
                return False
        return True

    def _get_org_id(self):
        client = local_session(self.manager.session_factory).client("org-account")
        try:
            resp = client.show_organization(ShowOrganizationRequest())
            log.info(f"[filters]-[policy-principal-wildcards]-query the service:"
                      f"[/v1/organizations] has successed. Get org is: {resp}")
            return resp.organization.id
        except exceptions as e:
            log.error(f"[filters]-[policy-principal-wildcards]-query the service:"
                      f"[/v1/organizations] is failed.cause:{e}")
            raise e

    def _get_need_check_policy_eps_ids(self, resources):
        huawei_eps_ids = []
        for resource in resources:
            if resource.get('endpoint_service_name').startswith('com.myhuaweicloud'):
                huawei_eps_ids.append(resource.get('endpoint_service_id'))
        return self._get_enable_policy_eps(list(set(huawei_eps_ids)))

    def _get_enable_policy_eps(self, eps_ids):
        result = []
        for eps_id in eps_ids:
            eps_detail = self._get_eps_detail(eps_id)
            if eps_detail.enable_policy:
                result.append(eps_detail.id)
        return result

    def _get_eps_detail(self, eps_id):
        eps_client = local_session(self.manager.session_factory).client("vpcep-eps")
        request = ListServiceDescribeDetailsRequest()
        request.id = eps_id

        try:
            response = eps_client.list_service_describe_details(request)
            log.debug(f"[actions]-[policy-principal-wildcards]-The resource:[vpcep-ep] "
                      f"get eps [{eps_id}] details has succeeded.")
            return response
        except exceptions.ClientRequestException as e:
            log.error(f"[actions]-[policy-principal-wildcards]-The resource:[vpcep-ep] "
                      f"get eps [{eps_id}] details is failed.cause:{e}")
            raise e


@VpcEndpoint.action_registry.register('update-policy-document')
class VpcEndpointUpdatePolicyDocument(HuaweiCloudBaseAction):
    """Update the endpoint policy.

    :example:

    .. code-block:: yaml

        policies:
          - name: update-policy-document
            resource: huaweicloud.vpcep-ep
            actions:
              - type: update-interface-policy
    """

    schema = type_schema('update-policy-document')

    def process(self, resources):
        if not resources:
            return []
        ep_util = VpcEndpointUtils(self.manager)
        expect_condition = self._get_expect_condition()
        for resource in resources:
            if ep_util.wait_ep_can_processed(resource):
                self.process_resource(resource, expect_condition)

        return resources

    def process_resource(self, resource, expect_condition):
        expect_statements = []
        ep_id = resource.get("id", "")
        policy_document = resource.get('policy_document', {})
        statements = policy_document.get('Statement', [])
        expect_statements.append(
            {
                "Action": ["*"],
                "Condition": expect_condition,
                "Effect": "Allow", "Principal": "*", "Resource": ["*"]
            })

        expect_policy_document = {
            "Statement": expect_statements,
            "Version": "5.0"
        }
        log.info(f"[actions]-[update-policy-document]-The resource:[vpcep-ep] "
                 f"with id:[{ep_id}] policy is invalid, "
                 f"cur: {statements}, expect: {expect_statements}")
        self._update_policy(ep_id, expect_policy_document)

    def perform_action(self, resource):
        return None

    def _get_expect_condition(self):
        org_id = self._get_org_id()
        expect_condition = {"StringEquals": {"g:PrincipalOrgID": org_id},
                            "StringEqualsIfExists": {"g:ResourceOrgID": org_id}
                            }
        log.info(f"[actions]-[update-policy-document]-Get org is: {org_id}")
        return expect_condition

    def _get_org_id(self):
        client = local_session(self.manager.session_factory).client("org-account")
        try:
            resp = client.show_organization(ShowOrganizationRequest())
            log.debug(f"[actions]-[update-policy-document]-query the service:"
                      f"[/v1/organizations] has successed. Get org is: {resp}")
            return resp.organization.id
        except exceptions.ClientRequestException as e:
            log.error(f"[actions]-[update-policy-document]-query the service:"
                      f"[/v1/organizations] is failed.cause:{e}")
            raise e

    def _update_policy(self, ep_id, policy_document):
        request = UpdateEndpointPolicyRequest(vpc_endpoint_id=ep_id)
        body = UpdateEndpointPolicyRequestBody(policy_document=policy_document)
        request.body = body
        log.debug(f"[actions]-[update-policy-document] update policy request body: {request}")

        client = self.manager.get_client()
        try:
            client.update_endpoint_policy(request)
            log.info(f"[actions]-[update-policy-document]-The resource:[vpcep-ep] "
                     f"with id:[{ep_id}] updating the policy has succeeded.")
        except exceptions.ClientRequestException as e:
            log.error(f"[actions]-[update-policy-document]-The resource:[vpcep-ep] "
                      f"with id:[{ep_id}] update policy is failed.cause:{e}")
            raise e


@VpcEndpointService.action_registry.register('enable-eps-approval-enabled')
class VpcEndpointEnableEpsApprovalEnabled(HuaweiCloudBaseAction):
    """Enable the eps approval enabled.

    :example:

    .. code-block:: yaml

        policies:
          - name: enable-eps-approval-enabled
            resource: huaweicloud.vpcep-eps
            actions:
              - type: enable-eps-approval-enabled
    """

    schema = type_schema('enable-eps-approval-enabled')

    def process(self, resources):
        if not resources:
            return []
        for resource in resources:
            if self._wait_eps_can_processed(resource):
                self.process_resource(resource)

        return resources

    def process_resource(self, resource):
        eps_id = resource.get("id", "")
        log.info(f"[actions]-[enable-eps-approval-enabled]-The resource:[vpcep-eps] "
                 f"with id:[{eps_id}] approval-enabled is False.")
        self._enable_eps_approval_enabled(eps_id)

    def perform_action(self, resource):
        return None

    def _wait_eps_can_processed(self, resource):
        for i in range(12):
            if resource.get('status') not in ('creating', 'deleting'):
                return True
            log.debug(f"[actions]-[enable-eps-approval-enabled] The resource:[vpcep-eps] "
                      f"with id:[{resource.get('id')}] status {resource.get('status')} "
                      f"is not available, wait: {i}")
            time.sleep(5)
        return False

    def _enable_eps_approval_enabled(self, eps_id):
        request = UpdateEndpointServiceRequest(vpc_endpoint_service_id=eps_id)
        body = UpdateEndpointServiceRequestBody(approval_enabled=True)
        request.body = body
        log.debug(f"[actions]-[enable-eps-approval-enabled] update request body: {request}")

        client = self.manager.get_client()
        try:
            client.update_endpoint_service(request)
            log.info(f"[actions]-[enable-eps-approval-enabled]-The resource:[vpcep-eps] "
                     f"with id:[{eps_id}] enable the approval enabled has succeeded.")
        except exceptions.ClientRequestException as e:
            log.error(f"[actions]-[enable-eps-approval-enabled]-The resource:[vpcep-eps] "
                      f"with id:[{eps_id}] enable the approval enabled is failed.cause:{e}")
            raise e
