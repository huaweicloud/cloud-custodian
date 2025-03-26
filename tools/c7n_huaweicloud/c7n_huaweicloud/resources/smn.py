# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import json
import logging
import jmespath

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdksmn.v2 import DeleteTopicRequest, \
    CreateLogtankRequest, CreateLogtankRequestBody, ListLogtankRequest, DeleteLogtankRequest, \
    UpdateTopicAttributeRequest, UpdateTopicAttributeRequestBody, DeleteTopicAttributesRequest, \
    ListTopicAttributesRequest

from c7n.filters import Filter
from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

log = logging.getLogger("custodian.huaweicloud.resources.smn")


@resources.register('topic')
class Topic(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'smn'
        enum_spec = ('list_topics', 'topics', 'offset')
        id = 'topic_id'
        tag = True
        tag_resource_type = 'smn_topic'


@Topic.filter_registry.register('topic-lts')
class TopicLtsFilter(Filter):
    """Filters SMN Topics by whether to bind topic to LTS.

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-smn-topic-not-lts
            resource: huaweicloud.topic
            filters:
              - type: topic-lts
                enabled: false
            actions:
              - delete
    """

    schema_alias = False
    schema = type_schema('topic-lts', rinherit={
        'type': 'object',
        'additionalProperties': False,
        'required': ['type', 'enabled'],
        'properties': {
            'type': {'enum': ['topic-lts']},
            'enabled': {'type': 'boolean'}
        }
    })
    RelatedResource = "c7n_huaweicloud.resources.smn.Topic"
    AnnotationKey = "matched-topic-lts"
    RelatedIdsExpression = "topic-lts"
    FetchThreshold = 10

    def process(self, resources, event=None):
        client = self.manager.get_client()
        enabled = self.data.get('enabled')
        resources_valid = []
        for data in resources:
            print(data)
            request = ListLogtankRequest(topic_urn=data["topic_urn"])
            response = client.list_logtank(request)
            res = jmespath.search('count', eval(
                str(response).replace('null', 'None').replace('false', 'False').replace('true',
                                                                                        'True')))
            if self.check(enabled, res) is False:
                continue
            data['lts'] = str(response)
            resources_valid.append(data)
        return resources_valid

    def check(self, enabled, res):
        check = False
        if enabled is True:
            if res > 0:
                check = True
        else:
            if res == 0:
                check = True
        return check


@Topic.filter_registry.register('topic-access')
class TopicAccessFilter(Filter):
    """Filters SMN Topics by access.

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-smn-topic
            resource: huaweicloud.topic
            filters:
              - type: topic-access
                effect: Allow
                user: *
                organization: 'o-bf966fe82ebb4d35d68b791729228788/r-001ebf32880a13eabfc8e1c37eee3ae9
                /ou-0dbfffe92fd92ddb35feff9b4079459c'
                service: obs
            actions:
              - delete
          - name: delete-smn-topic
            resource: huaweicloud.topic
            filters:
              - type: topic-access
                effect: Allow
                user: 2284f67d00db4d5896511837ef2f7366
                organization: 'o-bf966fe82ebb4d35d68b791729228788/r-001ebf32880a13eabfc8e1c37eee3ae9
                /ou-0dbfffe92fd92ddb35feff9b4079459c'
                service: obs
            actions:
              - delete
    """

    schema_alias = False
    schema = type_schema('topic-access', rinherit={
        'type': 'object',
        'additionalProperties': False,
        'required': ['type', 'effect'],
        'properties': {
            'type': {'enum': ['topic-access']},
            'effect': {'enum': ['Allow', 'Deny']},
            'user': {'type': 'string'},
            'organization': {'type': 'string'},
            'service': {'type': 'string'}
        }
    })
    RelatedResource = "c7n_huaweicloud.resources.smn.Topic"
    AnnotationKey = "matched-topic-access"
    RelatedIdsExpression = "topic-access"
    FetchThreshold = 10

    def process(self, resources, event=None):
        client = self.manager.get_client()
        resources_valid = []
        for data in resources:
            request = ListTopicAttributesRequest(topic_urn=data["topic_urn"], name='access_policy')
            response = client.list_topic_attributes(request)
            access_policy = response.attributes.access_policy
            log.info(f"access_policy:{access_policy}")
            if self.check(access_policy) is False:
                continue
            data['access_policy'] = access_policy
            resources_valid.append(data)
        return resources_valid

    def check(self, access_policy):
        if access_policy is None or len(access_policy) == 0:
            return False

        access_policy_dict = json.loads(access_policy)
        return self.check_user(access_policy_dict) and self.check_organization(
            access_policy_dict) and self.check_service(access_policy_dict)

    def check_user(self, access_policy):
        user = self.data.get('user')
        if user is None or len(user) == 0:
            return True

        effect = self.data.get('effect')
        if user == '*':
            for statement in access_policy.get('Statement'):
                if not statement.get('Effect') == effect:
                    continue
                csp = statement.get('Principal').get('CSP')
                if csp is None or len(csp) == 0:
                    continue
                if csp.__contains__('*'):
                    return True
        else:
            for statement in access_policy.get('Statement'):
                if not statement.get('Effect') == effect:
                    continue
                csp = statement.get('Principal').get('CSP')
                if csp is None or len(csp) == 0:
                    continue
                if csp.__contains__(f'urn:csp:iam::{user}:root'):
                    return True

        return False

    def check_organization(self, access_policy):
        organization = self.data.get('organization')
        if organization is None or len(organization) == 0:
            return True

        effect = self.data.get('effect')
        for statement in access_policy.get('Statement'):
            if not statement.get('Effect') == effect:
                continue
            org_path = statement.get('Principal').get('OrgPath')
            if org_path is None or len(org_path) == 0:
                continue
            if org_path.__contains__(organization):
                return True

        return False

    def check_service(self, access_policy):
        service = self.data.get('service')
        if service is None or len(service) == 0:
            return True
        effect = self.data.get('effect')
        for statement in access_policy.get('Statement'):
            if not statement.get('Effect') == effect:
                continue
            Service_path = statement.get('Principal').get('Service')
            if Service_path is None or len(Service_path) == 0:
                continue
            if Service_path.__contains__(service):
                return True

        return False


@Topic.action_registry.register("delete")
class TopicDelete(HuaweiCloudBaseAction):
    """Delete SMN Topics.

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-smn-topic
            resource: huaweicloud.topic
            filters:
              - type: value
                key: name
                value: "111"
            actions:
              - delete
    """

    schema = type_schema("delete")

    def perform_action(self, resource):
        client = self.manager.get_client()
        response = None
        try:
            request = DeleteTopicRequest(topic_urn=resource["topic_urn"])
            response = client.delete_topic(request)
        except exceptions.ClientRequestException as e:
            log.error(f"TopicDelete failed, resource :{resource}, exceptions:{e}")
        return response


@Topic.action_registry.register("create-lts")
class TopicCreateLts(HuaweiCloudBaseAction):
    """Create LTS to SMN Topics.

    :Example:

    .. code-block:: yaml

        policies:
          - name: create-lts-to-smn-topic
            resource: huaweicloud.topic
            filters:
              - type: topic-lts
                enabled: false
            actions:
              - type: create-lts
                log_group_id: 46aa012f-d143-464e-8192-05c644c022bf
                log_stream_id: 26319d9d-af15-4207-9797-e63aa0b6c4e7
    """

    schema = type_schema("create-lts", rinherit={
        'type': 'object',
        'additionalProperties': False,
        'required': ['type', 'log_group_id', 'log_stream_id'],
        'properties': {
            'type': {'enum': ['create-lts']},
            'log_group_id': {'type': 'string'},
            'log_stream_id': {'type': 'string'}
        }
    })

    def perform_action(self, resource):
        client = self.manager.get_client()
        response = None
        try:
            request = CreateLogtankRequest(topic_urn=resource["topic_urn"],
                                           body=CreateLogtankRequestBody(
                                               log_group_id=self.data.get('log_group_id'),
                                               log_stream_id=self.data.get('log_stream_id')))
            response = client.create_logtank(request)
        except exceptions.ClientRequestException as e:
            log.error(f"Create LTS to SMN Topics failed, resource :{resource}, exceptions:{e}")
        return response


@Topic.action_registry.register("delete-lts")
class TopicDeleteLts(HuaweiCloudBaseAction):
    """Delete LTS to SMN Topics.

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-lts-to-smn-topic
            resource: huaweicloud.topic
            filters:
              - type: topic-lts
                enabled: true
            actions:
              - delete-lts
    """

    schema = type_schema("delete-lts")

    def perform_action(self, resource):
        client = self.manager.get_client()
        response = None
        try:
            request = ListLogtankRequest(topic_urn=resource["topic_urn"])
            ltsResponse = client.list_logtank(request)
            if ltsResponse.count > 0:
                request = DeleteLogtankRequest(topic_urn=resource["topic_urn"],
                                               logtank_id=ltsResponse.logtanks[0].id)
                response = client.delete_logtank(request)
        except exceptions.ClientRequestException as e:
            log.error(f"Delete LTS to SMN Topics failed, resource :{resource}, exceptions:{e}")
        return response


@Topic.action_registry.register("update-access")
class TopicUpdateAccessPolicy(HuaweiCloudBaseAction):
    """Update access to SMN Topics.

    :Example:

    .. code-block:: yaml

        policies:
          - name: update-access-to-smn-topic
            resource: huaweicloud.topic
            filters:
              - type: value
                key: name
                value: "111"
            actions:
              - type: update-access
                value: "{\"Version\":\"2016-09-07\",\"Id\":\"__default_policy_ID\",
                \"Statement\":[{\"Sid\":\"__user_pub_0\",\"Effect\":\"Allow\",
                \"Principal\":{\"CSP\":[\"urn:csp:iam::{domainID}:root\"]},
                \"Action\":[\"SMN:Publish\",\"SMN:QueryTopicDetail\"],
                \"Resource\":\"{topic_urn}\"},
                {\"Sid\":\"__org_path_pub_0\",\"Effect\":\"Allow\",
                \"Principal\":{\"OrgPath\":[\"o-bf966fe82ebb4d35d68b791729228788
                /r-001ebf32880a13eabfc8e1c37eee3ae9/ou-0dbfffe92fd92ddb35feff9b4079459c\"]},
                \"Action\":[\"SMN:Publish\",\"SMN:QueryTopicDetail\"],
                \"Resource\":\"{topic_urn}\"},
                {\"Sid\":\"__service_pub_0\",\"Effect\":\"Allow\",
                \"Principal\":{\"Service\":[\"obs\"]},
                \"Action\":[\"SMN:Publish\",\"SMN:QueryTopicDetail\"],
                \"Resource\":\"{topic_urn}\"}]}"
    """

    schema = type_schema("update-access", rinherit={
        'type': 'object',
        'additionalProperties': False,
        'required': ['type', 'value'],
        'properties': {
            'type': {'enum': ['update-access']},
            'value': {'type': 'string'}
        }
    })

    def perform_action(self, resource):
        client = self.manager.get_client()
        response = None
        try:
            request = UpdateTopicAttributeRequest(topic_urn=resource["topic_urn"],
                                                  name='access_policy',
                                                  body=UpdateTopicAttributeRequestBody(
                                                      value=self.data.get('value')))
            response = client.update_topic_attribute(request)
        except exceptions.ClientRequestException as e:
            log.error(
                f"Update access policy to SMN Topics failed, resource :{resource}, exceptions:{e}")
        return response


@Topic.action_registry.register("delete-access")
class TopicDeleteAccessPolicy(HuaweiCloudBaseAction):
    """Delete access to SMN Topics.

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-access-to-smn-topic
            resource: huaweicloud.topic
            filters:
              - type: value
                key: name
                value: "111"
            actions:
              - delete-access
    """

    schema = type_schema("delete-access")

    def perform_action(self, resource):
        client = self.manager.get_client()
        response = None
        try:
            request = DeleteTopicAttributesRequest(topic_urn=resource["topic_urn"])
            response = client.delete_topic_attributes(request)
        except exceptions.ClientRequestException as e:
            log.error(
                f"Delete access policy to SMN Topics failed, resource :{resource}, exceptions:{e}")
        return response


@Topic.action_registry.register("get-access")
class TopicGetAccessPolicy(HuaweiCloudBaseAction):
    """Get access to SMN Topics.

    :Example:

    .. code-block:: yaml

        policies:
          - name: get-access-to-smn-topic
            resource: huaweicloud.topic
            filters:
              - type: value
                key: name
                value: "111"
            actions:
              - get-access
    """

    schema = type_schema("get-access")

    def perform_action(self, resource):
        client = self.manager.get_client()
        response = None
        try:
            request = ListTopicAttributesRequest(topic_urn=resource["topic_urn"],
                                                 name='access_policy')
            response = client.list_topic_attributes(request)
            access_policy = response.attributes.access_policy
            resource['access_policy'] = access_policy
        except exceptions.ClientRequestException as e:
            log.error(f"Get topic access policy failed, resource :{resource}, exceptions:{e}")
        return response
