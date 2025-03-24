# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import jmespath

from dateutil.parser import parse

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkelb.v3 import *

from c7n.filters import ValueFilter, AgeFilter, OPERATORS, Filter
from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo


log = logging.getLogger("custodian.huaweicloud.resources.elb")


@resources.register('elb_loadbalancer')
class Loadbalancer(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'elb'
        resource = 'loadbalancer'
        enum_spec = ("list_load_balancers", 'loadbalancers', 'marker')
        id = 'id'
        tag = True


@Loadbalancer.action_registry.register("delete")
class LoadbalancerDelete(HuaweiCloudBaseAction):
    """Deletes ELB Loadbalancers.

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-loadbalancer
            resource: huaweicloud.elb_loadbalancer
            flters:
              - type: value
                key: protocol
                value: "http"
            actions:
              - delete
    """

    schema = type_schema("delete")

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = DeleteLoadBalancerForceRequest(loadbalancer_id=resource["id"])
        response = client.delete_load_balancer_force(request)
        return response


@Loadbalancer.action_registry.register("enable-logging")
class LoadbalancerEnableLogging(HuaweiCloudBaseAction):
    """Enable ELB logging for loadbalancers.

    :Example:

    .. code-block:: yaml

        policies:
          - name: enable-loadbalancers-logging
            resource: huaweicloud.elb_loadbalancer
            flters:
              - or:
                  - type: attribute
                    key: log_topic_id
                    value: 0
                    value_type: size
                    op: le
                  - type: attribute
                    key: log_group_id
                    value: 0
                    value_type: size
                    op: le
            actions:
              - type: enable-logging
                log_group_id: xxx
                log_topic_id: xxxx
    """

    schema = type_schema(type_name="enable-logging",
                         log_group_id={'type': 'string'},
                         log_topic_id={'type': 'string'},
                         required=['log_group_id', 'log_topic_id'],)

    def perform_action(self, resource):
        loadbalancer_id = resource['id']
        log_group_id = self.data.get("log_group_id")
        log_topic_id = self.data.get("log_topic_id")

        client = self.manager.get_client()
        logtank = CreateLogtankOption()
        logtank.loadbalancer_id = loadbalancer_id
        logtank.log_group_id = log_group_id
        logtank.log_topic_id = log_topic_id
        body =  CreateLogtankRequestBody(logtank)
        request = CreateLogtankRequest(body)
        log.info(f"enable logging request: {str(request)}")
        response = client.create_logtank(request)
        log.info(f"enable logging for loadbalancer: {response}")
        return response


@Loadbalancer.filter_registry.register('backend-server-count')
class ELBBackendServerCountFilter(Filter):
    """Backends Filter that allows filtering on ELB backends count.

    :example:

    .. code-block:: yaml
        policies:
          - name: no-backends-loadbalancer
            resource: huaweicloud.elb_loadbalancer
            filters:
              - type: backend-server-count
                count: 0
                op: le

    """
    schema = type_schema(
        'backend-server-count',
        op={'enum': list(OPERATORS.keys())},
        count={'type': 'integer', 'minimum': 0})

    def __call__(self, resource):
        count = self.data.get('count', 0)
        op_name = self.data.get('op', 'gte')
        op = OPERATORS.get(op_name)

        client = self.manager.get_client()
        backend_count = 0
        request = ListAllMembersRequest(loadbalancer_id=resource["id"])
        members_response = client.list_all_members(request)
        if members_response.members:
            backend_count = len(members_response.members)
        return op(backend_count, count)


@Loadbalancer.filter_registry.register('publicip-count')
class ELBBackendsFilter(Filter):
    """Publicip Filter that allows filtering on ELB.

    :example:

    .. code-block:: yaml
        policies:
          - name: no-backends-loadbalancer
            resource: huaweicloud.elb_loadbalancer
            filters:
              - type: publicip-count
                count: 0
                op: le

    """
    schema = type_schema(
        'publicip-count',
        op={'enum': list(OPERATORS.keys())},
        count={'type': 'integer', 'minimum': 0})

    def __call__(self, resource):
        count = self.data.get('count', 0)
        op_name = self.data.get('op', 'gte')
        op = OPERATORS.get(op_name)

        eip_count = len(resource.eips) if resource.eips else 0
        ipv6bandwidth_count = len(resource.ipv6_bandwidth) if resource.ipv6_bandwidth else 0
        geip_count = len(resource.global_eips) if resource.global_eips else 0

        return op(eip_count+ipv6bandwidth_count+geip_count, count)


@Loadbalancer.filter_registry.register('is-logging-enable')
class ELBBackendsFilter(Filter):
    """Publicip Filter that allows filtering on ELB.

    :example:

    .. code-block:: yaml
        policies:
          - name: elb-enable-logging
            resource: huaweicloud.elb_loadbalancer
            filters:
              - type: is-logginng-enable
                enable: false

    """
    schema = type_schema(
        'is-logging-enable',
        enable={'type': 'boolean'})

    def __call__(self, resource):
        logging_enable = self.data.get('enable', False)
        log_group_id = resource['log_group_id'] if 'log_group_id' in resource else None
        log_topic_id = resource['log_topic_id'] if 'log_topic_id' in resource else None
        if (log_group_id is None or log_group_id.strip() == ""
                or log_topic_id is None or log_topic_id.strip() == ""):
            return False == logging_enable
        return True == logging_enable


@resources.register('elb_listener')
class Listener(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'elb'
        resource = 'listener'
        enum_spec = ("list_listeners", 'listeners', 'marker')
        id = 'id'
        tag = True


@Listener.action_registry.register("delete")
class ListenerDelete(HuaweiCloudBaseAction):
    """Deletes ELB Listeners.

    :Example:

    .. code-block:: yaml

        policies:
          - name: ensure-elb-https-only
            resource: huaweicloud.elb_listener
            filters:
              - or:
                - type: value
                  key: protocol
                  value: "HTTPS"
                  op: ne
                - type: value
                  key: port
                  value: 443
                  op: ne
            actions:
              - type: delete
                loadbalancers: ['94c11c75-e3de-48b7-a5a2-28202ada60b1']
    """

    schema = type_schema(type_name="delete",
                         loadbalancers={'type': 'array'})

    def perform_action(self, resource):
        # type_schema -> loadbalancers: lbIDs = ['94c11c75-e3de-48b7-a5a2-28202ada60b1']
        lb_from_schema = self.data.get("loadbalancers")
        # resource['loadbalancers'] = [{'id': '94c11c75-e3de-48b7-a5a2-28202ada60b1'}]
        if lb_from_schema and len(lb_from_schema) > 0 and resource['loadbalancers'][0]['id'] not in lb_from_schema:
            return

        client = self.manager.get_client()
        request = DeleteListenerForceRequest(listener_id=resource["id"])
        response = client.delete_listener_force(request)
        log.info(f"delete listener: {resource['id']}")
        return response


@Listener.filter_registry.register('ipgroup-id')
class ELBBackendsFilter(Filter):
    """Publicip Filter that allows filtering on ELB.

    :example:

    .. code-block:: yaml
        policies:
          - name: elb-enable-logging
            resource: huaweicloud.elb_loadbalancer
            filters:
              - type: is-logginng-enable
                enable: false

    """
    schema = type_schema(
        'is-logging-enable',
        enable={'type': 'boolean'})

    def __call__(self, resource):
        logging_enable = self.data.get('enable', False)
        log_group_id = resource['log_group_id'] if 'log_group_id' in resource else None
        log_topic_id = resource['log_topic_id'] if 'log_topic_id' in resource else None
        if (log_group_id is None or log_group_id.strip() == ""
                or log_topic_id is None or log_topic_id.strip() == ""):
            return False == logging_enable
        return True == logging_enable


@Loadbalancer.filter_registry.register('attributes')
@Listener.filter_registry.register('attributes')
class ELBAttributesFilter(ValueFilter):
    """Value Filter that allows filtering on ELB attributes

    :example:

    .. code-block:: yaml
        policies:
          - name: list-autoscaling-loadbalancer
            resource: huaweicloud.elb_loadbalancer
            filters:
              - type: attributes
                key: autoscaling.enable
                value: true

    """
    annotate = False  # no annotation from value filter
    schema = type_schema('attributes', rinherit=ValueFilter.schema)
    schema_alias = False

    def process(self, resources, event=None):
        return super().process(resources, event)

    def __call__(self, r):
        return super().__call__(r)



@Loadbalancer.filter_registry.register('age')
@Listener.filter_registry.register('age')
class ELBAgeFilter(AgeFilter):
    """Filter elb by age.

    :example:

    .. code-block:: yaml

            policies:
              - name: list-older-loadbalancer
                resource: huaweicloud.elb_loadbalancer
                filters:
                  - type: age
                    days: 90
                    op: ge
    """

    date_attribute = "created_at"
    schema = type_schema(
        'age',
        op={'$ref': '#/definitions/filters_common/comparison_operators'},
        days={'type': 'number'},
        hours={'type': 'number'},
        minutes={'type': 'number'})

    def get_resource_date(self, resource):
        return parse(resource.get(
            self.date_attribute, "2000-01-01T01:01:01.000Z"))


# @Loadbalancer.filter_registry.register('attributes')
# @Listener.filter_registry.register('attributes')
# class ELBAttributesFilter(ValueFilter):
#     """Value Filter that allows filtering on ELB attributes
#
#     :example:
#
#     .. code-block:: yaml
#         policies:
#           - name: list-autoscaling-loadbalancer
#             resource: huaweicloud.elb_loadbalancer
#             filters:
#               - type: attributes
#                 key: autoscaling.enable
#                 value: true
#
#     """
#     annotate = False  # no annotation from value filter
#     schema = type_schema('attributes', rinherit=ValueFilter.schema,
#                          len={'type': 'integer', 'minimum': -1})
#     schema_alias = False
#
#     def __call__(self, r):
#         exists = self.data.get('exists', 0)
#         if exists != None:
#             response = eval(str(r).replace('null', 'None').
#                             replace('false', 'False').replace('true', 'True'))
#             key = self.data.get('key')
#             attr = jmespath.search(key, response)
#             if exists == True:
#
#             elif exists == False:
#
#         return super().__call__(r)
#
#         count = self.data.get('count', 0)
#         op_name = self.data.get('op', 'gte')
#         op = OPERATORS.get(op_name)
#
#         client = self.manager.get_client()
#         backend_count = 0
#         request = ListAllMembersRequest(loadbalancer_id=resource["id"])
#         members_response = client.list_all_members(request)
#         if members_response.members:
#             backend_count = len(members_response.members)
#         return op(backend_count, count)