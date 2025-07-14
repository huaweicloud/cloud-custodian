# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import json
import logging

from huaweicloudsdksmn.v2 import DeleteTopicRequest, \
    CreateLogtankRequest, CreateLogtankRequestBody, ListLogtankRequest, DeleteLogtankRequest, \
    UpdateTopicAttributeRequest, UpdateTopicAttributeRequestBody, DeleteTopicAttributesRequest, \
    ListTopicAttributesRequest, ListResourceTagsRequest

from c7n.filters import Filter
from c7n.utils import local_session
from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

log = logging.getLogger("custodian.huaweicloud.resources.smn")


@resources.register('smn-topic')
class Topic(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'smn'
        enum_spec = ('list_topics', 'topics', 'offset')
        id = 'topic_id'
        tag = True
        tag_resource_type = 'smn_topic'

    def get_resources(self, resource_ids):
        resources = self.augment(self.source.get_resources(self.get_resource_query())) or []
        result = []
        for resource in resources:
            if resource["id"] in resource_ids or resource["topic_urn"] in resource_ids:
                result.append(resource)
        return result

    def augment(self, resources):
        if not resources:
            return resources

        client = local_session(self.session_factory).client('smn')
        resource_type = 'smn_topic'
        for resource in resources:
            resource_id = resource["id"]
            try:
                tags = resource.get('tags')
                if tags is None:
                    request = ListResourceTagsRequest(resource_type=resource_type,
                                                      resource_id=resource_id)
                    response = client.list_resource_tags(request)
                    log.debug(
                        f"[resource]-[smn-topic] query the service:[GET /v2/{{project_id}}"
                        f"/{resource_type}/{resource_id}/tags] is success.")
                    tags = response.to_dict().get('tags')
                    resource['tags'] = {item['key']: item['value'] for item in tags}
            except Exception as e:
                log.error(
                    f"[resource]-[smn-topic] query tags resource:[{resource_id}] is failed, "
                    f"cause:{e}")
        return resources


@Topic.filter_registry.register('topic-lts')
class TopicLtsFilter(Filter):
    """Filters whether the SMN topic is bound to LTS.

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-smn-topic-not-lts
            resource: huaweicloud.smn-topic
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
        'required': ['type'],
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
        for resource in resources:
            resource_id = resource["id"]
            topic_urn = resource["topic_urn"]
            try:
                lts = resource.get('lts')
                if lts is None:
                    request = ListLogtankRequest(topic_urn=resource["topic_urn"])
                    response = client.list_logtank(request)
                    log.debug(
                        f"[filters]-[topic-lts] query the service:[GET /v2/{{project_id}}"
                        f"/notifications/topics/{topic_urn}/logtanks] is success.")
                    lts = response.to_dict().get('logtanks')
                    resource['lts'] = lts
                if self.check(enabled, lts) is False:
                    continue
                resources_valid.append(resource)
            except Exception as e:
                log.error(
                    f"[filters]-[topic-lts] get lts resource:[{resource_id}] is failed, cause:{e}")
        return resources_valid

    def check(self, enabled, lts):
        res = len(lts)
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
    """Filters for SMN topic access policy. The relationship between the filter fields is and.

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-smn-topic
            resource: huaweicloud.smn-topic
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
            resource: huaweicloud.smn-topic
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
        'required': ['type'],
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
        for resource in resources:
            resource_id = resource["id"]
            topic_urn = resource["topic_urn"]
            try:
                access_policy = resource.get('access_policy')
                if access_policy is None:
                    request = ListTopicAttributesRequest(topic_urn=topic_urn,
                                                         name='access_policy')
                    response = client.list_topic_attributes(request)
                    log.debug(
                        f"[filters]-[topic-access] query the service:[GET /v2/{{project_id}}"
                        f"/notifications/topics/{topic_urn}/attributes] is success.")
                    access_policy = response.attributes.access_policy
                    resource['access_policy'] = access_policy
                if self.check(access_policy) is False:
                    continue
                resources_valid.append(resource)
            except Exception as e:
                log.error(
                    f"[filters]-[topic-access] resource:[{resource_id}] is failed, cause:{e}")
        return resources_valid

    def check(self, access_policy):
        return self.check_user(access_policy) and self.check_organization(
            access_policy) and self.check_service(access_policy)

    def check_user(self, access_policy):
        user = self.data.get('user')
        if user is None or len(user) == 0:
            return True

        if access_policy is None or len(access_policy) == 0:
            return False

        access_policy_dict = json.loads(access_policy)

        effect = self.data.get('effect')
        if user == '*':
            for statement in access_policy_dict.get('Statement'):
                if not statement.get('Effect') == effect:
                    continue
                csp = statement.get('Principal').get('CSP')
                if csp is None or len(csp) == 0:
                    continue
                if csp.__contains__('*'):
                    return True
        else:
            for statement in access_policy_dict.get('Statement'):
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

        if access_policy is None or len(access_policy) == 0:
            return False

        access_policy_dict = json.loads(access_policy)

        effect = self.data.get('effect')
        for statement in access_policy_dict.get('Statement'):
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

        if access_policy is None or len(access_policy) == 0:
            return False

        access_policy_dict = json.loads(access_policy)

        effect = self.data.get('effect')
        for statement in access_policy_dict.get('Statement'):
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
            resource: huaweicloud.smn-topic
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
        resource_id = resource["id"]
        topic_urn = resource["topic_urn"]
        response = None
        try:
            request = DeleteTopicRequest(topic_urn=topic_urn)
            response = client.delete_topic(request)
            log.debug(
                f"[actions]-[delete] query the service:[DELETE /v2/{{project_id}}"
                f"/notifications/topics/{topic_urn}] is success.")
            log.info(
                f"[actions]-[delete]-The resource:[smn-topic] with id:[{resource_id}] "
                f"Delete SMN Topics is success")
        except Exception as e:
            log.error(
                f"[actions]-[delete]-The resource:[smn-topic] with id:[{resource_id}] "
                f"Delete SMN Topics is failed, cause:{e}")
        return response


@Topic.action_registry.register("create-lts")
class TopicCreateLts(HuaweiCloudBaseAction):
    """Create LTS for SMN Topics.

    :Example:

    .. code-block:: yaml

        policies:
          - name: create-lts-to-smn-topic
            resource: huaweicloud.smn-topic
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
        resource_id = resource["id"]
        topic_urn = resource["topic_urn"]
        response = None
        try:
            request = CreateLogtankRequest(topic_urn=topic_urn,
                                           body=CreateLogtankRequestBody(
                                               log_group_id=self.data.get('log_group_id'),
                                               log_stream_id=self.data.get('log_stream_id')))
            response = client.create_logtank(request)
            log.debug(
                f"[actions]-[create-lts] query the service:[POST /v2/{{project_id}}"
                f"/notifications/topics/{topic_urn}/logtanks] is success.")
            log.info(
                f"[actions]-[create-lts]-The resource:[smn-topic] with id:[{resource_id}] "
                f"Create LTS to SMN Topics is success.")
        except Exception as e:
            log.error(
                f"[actions]-[create-lts]-The resource:[smn-topic] with id:[{resource_id}] "
                f"Create LTS to SMN Topics is failed, cause:{e}")
        return response


@Topic.action_registry.register("delete-lts")
class TopicDeleteLts(HuaweiCloudBaseAction):
    """Delete LTS from SMN Topics.

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-lts-to-smn-topic
            resource: huaweicloud.smn-topic
            filters:
              - type: topic-lts
                enabled: true
            actions:
              - delete-lts
    """

    schema = type_schema("delete-lts")

    def perform_action(self, resource):
        client = self.manager.get_client()
        resource_id = resource["id"]
        topic_urn = resource["topic_urn"]
        response = None
        try:
            lts = resource.get('lts')
            if lts is None:
                request = ListLogtankRequest(topic_urn=topic_urn)
                response = client.list_logtank(request)
                log.debug(
                    f"[actions]-[delete-lts] query the service:[GET /v2/{{project_id}}"
                    f"/notifications/topics/{topic_urn}/logtanks] is success.")
                lts = response.to_dict().get('logtanks')
            for logtanks in lts:
                logtanks_id = logtanks["id"]
                request = DeleteLogtankRequest(topic_urn=topic_urn,
                                               logtank_id=logtanks_id)
                response = client.delete_logtank(request)
                log.debug(
                    f"[actions]-[delete-lts] query the service:[DELETE /v2/{{project_id}}"
                    f"/notifications/topics/{topic_urn}/logtanks/{logtanks_id}] is success.")
            log.info(
                f"[actions]-[delete-lts]-The resource:[smn-topic] with id:[{resource_id}] "
                f"Delete LTS to SMN Topics is success.")
            resource["lts"] = None
        except Exception as e:
            log.error(
                f"[actions]-[delete-lts]-The resource:[smn-topic] with id:[{resource_id}] "
                f"Delete LTS to SMN Topics is failed, cause:{e}")
        return response


@Topic.action_registry.register("update-access")
class TopicUpdateAccessPolicy(HuaweiCloudBaseAction):
    """Update access for SMN Topics.

    :Example:

    .. code-block:: yaml

        policies:
          - name: update-access-to-smn-topic
            resource: huaweicloud.smn-topic
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
        resource_id = resource["id"]
        topic_urn = resource["topic_urn"]
        response = None
        try:
            request = UpdateTopicAttributeRequest(topic_urn=topic_urn,
                                                  name='access_policy',
                                                  body=UpdateTopicAttributeRequestBody(
                                                      value=self.data.get('value')))
            response = client.update_topic_attribute(request)
            log.debug(
                f"[actions]-[update-access] query the service:[PUT /v2/{{project_id}}"
                f"/notifications/topics/{topic_urn}/attributes/access_policy] is success.")
            log.info(
                f"[actions]-[update-access] The resource:[smn-topic] with id:[{resource_id}] "
                f"Update access policy to SMN Topics is success.")
            resource['access_policy'] = self.data.get('value')
        except Exception as e:
            log.error(
                f"[actions]-[update-access] The resource:[smn-topic] with id:[{resource_id}] "
                f"Update access policy to SMN Topics is failed, cause:{e}")
        return response


@Topic.action_registry.register("delete-allow-all-user-access")
class TopicDeleteAllowAllUserAccessPolicy(HuaweiCloudBaseAction):
    """Delete all user access form SMN Topics.

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-allow-all-user-access-to-smn-topic
            resource: huaweicloud.smn-topic
            filters:
              - type: value
                key: name
                value: "111"
            actions:
              - delete-allow-all-user-access
    """

    schema = type_schema("delete-allow-all-user-access")

    def perform_action(self, resource):
        client = self.manager.get_client()
        resource_id = resource["id"]
        topic_urn = resource["topic_urn"]
        response = None
        try:
            access_policy = resource.get('access_policy')
            if access_policy is None:
                request = ListTopicAttributesRequest(topic_urn=topic_urn,
                                                     name='access_policy')
                response = client.list_topic_attributes(request)
                log.debug(
                    f"[actions]-[delete-allow-all-user-access] query the service:[GET /v2/"
                    f"{{project_id}}/notifications/topics/{topic_urn}/attributes] is success.")
                access_policy = response.attributes.access_policy
                resource['access_policy'] = access_policy
            if access_policy is None or len(access_policy) == 0:
                return response

            access_policy_dict = json.loads(access_policy)
            statements = access_policy_dict.get('Statement')
            for statement in statements:
                if statement.get('Effect') != "Allow":
                    continue
                csp = statement.get('Principal').get('CSP')
                if csp is None or len(csp) == 0:
                    continue
                csp.remove("*")
                if len(csp) == 0:
                    statements.remove(statement)
            value = None
            if len(statements) > 0:
                value = json.dumps(access_policy_dict)

            request = UpdateTopicAttributeRequest(topic_urn=topic_urn,
                                                  name='access_policy',
                                                  body=UpdateTopicAttributeRequestBody(
                                                      value=value))
            response = client.update_topic_attribute(request)
            log.debug(
                f"[actions]-[delete-allow-all-user-access] query the service:[PUT /v2/"
                f"{{project_id}}/notifications/topics/{topic_urn}/attributes/access_policy] is "
                f"success.")
            log.info(
                f"[actions]-[delete-allow-all-user-access] The resource:smn-topic with id:"
                f"[{resource_id}] Delete allow all user access policy to SMN Topics is success.")
            resource['access_policy'] = value
        except Exception as e:
            log.error(
                f"[actions]-[delete-allow-all-user-access] The resource:smn-topic with id:"
                f"[{resource_id}] Delete allow all user access policy to SMN Topics is failed, "
                f"cause:{e}")
        return response


@Topic.action_registry.register("delete-access")
class TopicDeleteAccessPolicy(HuaweiCloudBaseAction):
    """Delete access form SMN Topics.

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-access-to-smn-topic
            resource: huaweicloud.smn-topic
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
        resource_id = resource["id"]
        topic_urn = resource["topic_urn"]
        response = None
        try:
            request = DeleteTopicAttributesRequest(topic_urn=topic_urn)
            response = client.delete_topic_attributes(request)
            log.debug(
                f"[actions]-[delete-access] query the service:[DELETE /v2/{{project_id}}"
                f"/notifications/topics/{topic_urn}/attributes] is success.")
            log.info(
                f"[actions]-[delete-access] The resource:[smn-topic] with id:[{resource_id}] "
                f"Delete access policy to SMN Topics is success.")
            resource['access_policy'] = None
        except Exception as e:
            log.error(
                f"[actions]-[delete-access] The resource:[smn-topic] with id:[{resource_id}] "
                f"Delete access policy to SMN Topics is failed, cause:{e}")
        return response
