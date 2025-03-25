# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import jmespath

from dateutil.parser import parse

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkelb.v3 import *
from huaweicloudsdkeip.v3 import *
from huaweicloudsdkgeip.v3 import *

from c7n.filters import ValueFilter, AgeFilter, OPERATORS, Filter
from c7n.utils import type_schema, local_session
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo


log = logging.getLogger("custodian.huaweicloud.resources.elb")


@resources.register('elb.loadbalancer')
class Loadbalancer(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'elb'
        resource = 'loadbalancer'
        enum_spec = ("list_load_balancers", 'loadbalancers', 'marker')
        id = 'id'
        tag = True
        tag_resource_type = 'elb'


@Loadbalancer.action_registry.register("delete")
class LoadbalancerDeleteAction(HuaweiCloudBaseAction):
    """Deletes ELB Loadbalancers.

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-has-publicip-loadbalancers
            filters:
              - type: publicip-count
                count: 0
                op: gt
            actions:
              - type: delete
    """

    schema = type_schema("delete")

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = DeleteLoadBalancerForceRequest(loadbalancer_id=resource["id"])
        response = client.delete_load_balancer_force(request)
        return response


@Loadbalancer.action_registry.register("enable-logging")
class LoadbalancerEnableLoggingAction(HuaweiCloudBaseAction):
    """Enable logging for loadbalancers.

    :Example:

    .. code-block:: yaml

        policies:
          - name: enable-logging-for-loadbalancer
            filters:
              - type: is-logging-enable
                enable: false
            actions:
              - type: enable-logging
                log_group_id: "c5c89263-cfce-45cf-ac08-78cf537ba6c5"
                log_topic_id: "328abfed-ab1a-4484-b2c1-031c0d06ea66"
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
        response = client.create_logtank(request)
        return response


@Loadbalancer.action_registry.register("unbind-publicips")
class LoadbalancerEnableLoggingAction(HuaweiCloudBaseAction):
    """Unbind all public IP of loadbalancers.

    :Example:

    .. code-block:: yaml

        policies:
          - name: elb-policy-3
            resource: huaweicloud.elb.loadbalancer
            filters:
              - type: publicip-count
                count: 0
                op: gt
            actions:
              - type: unbind-publicips
    """

    schema = type_schema(type_name="unbind-publicips",
                         publicip_types={'type': 'array', 'enum': ['eip', 'ipv6_bandwidth', 'global_eip']},)

    def perform_action(self, resource):
        loadbalancer_id = resource['id']

        publicip_types = self.data.get("publicip_types")
        if not publicip_types or len(publicip_types) == 0:
            publicip_types = ['eip', 'ipv6_bandwidth', 'global_eip']

        eip_count = len(resource['eips']) if resource['eips'] else 0
        geip_count = len(resource['global_eips']) \
            if 'global_eips' in resource and resource['global_eips'] else 0

        response = None
        # 解绑公网ipv6：从eips中获取ip_version为6的eip_id；调用elb更新接口，传入ipv6_bandwidth=null
        if 'ipv6_bandwidth' in publicip_types and eip_count > 0:
            elb_client = self.manager.get_client()
            for eip in resource['eips']:
                if eip['ip_version'] == 6:
                    request = UpdateLoadBalancerRequest(loadbalancer_id=loadbalancer_id)
                    request.body = UpdateLoadBalancerRequestBody()
                    request.body.loadbalancer = {'ipv6_bandwidth': None}
                    response = elb_client.update_load_balancer(request)

        # 解绑公网ipv4：从eips中获取ip_version为4的eip_id；调用eip的解绑接口
        if 'eip' in publicip_types and eip_count > 0:
            eip_client = local_session(self.manager.session_factory).client('eip')
            for eip in resource['eips']:
                if eip['ip_version'] == 4:
                    request = DisassociatePublicipsRequest(publicip_id=eip['eip_id'])
                    response = eip_client.disassociate_publicips(request)

        # 解绑global eip：从global_eips中获取global_eip id；调用geip的解绑接口
        if 'global_eip' in publicip_types and geip_count > 0:
            geip_client = local_session(self.manager.session_factory).client('geip')
            for geip in resource['global_eips']:
                request = DisassociateInstanceRequest(global_eip_id=geip['global_eip_id'])
                response = geip_client.disassociate_instance(request)

        return response


@Loadbalancer.filter_registry.register('backend-server-count')
class LoadbalancerBackendServerCountFilter(Filter):
    """Allows filtering on ELB backend servers count.

    :example:

    .. code-block:: yaml

        policies:
          - name: delete-no-backend-loadbalancer
            resource: huaweicloud.elb.loadbalancer
            filters:
              - type: backend-server-count
                count: 0
                op: le
            actions:
              - type: delete
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
        request = ListAllMembersRequest(loadbalancer_id=[resource["id"]])
        members_response = client.list_all_members(request)
        if members_response.members:
            backend_count = len(members_response.members)
        return op(backend_count, count)


@Loadbalancer.filter_registry.register('publicip-count')
class LoadbalancerPublicipCountFilter(Filter):
    """Allows filtering on ELB public IP counts.

    :example:

    .. code-block:: yaml
        policies:
          - name: delete-loadbalancer-has-eip
            resource: huaweicloud.elb.loadbalancer
            filters:
              - type: publicip-count
                count: 0
                op: gt
            actions:
              - type: delete
    """
    schema = type_schema(
        'publicip-count',
        op={'enum': list(OPERATORS.keys())},
        count={'type': 'integer', 'minimum': 0})

    def __call__(self, resource):
        count = self.data.get('count', 0)
        op_name = self.data.get('op', 'gte')
        op = OPERATORS.get(op_name)

        log.info(f"resource: {resource}")
        eip_count = len(resource['eips']) if resource['eips'] else 0
        ipv6bandwidth_count = len(resource['ipv6_bandwidth']) \
            if 'ipv6_bandwidth' in resource and resource['ipv6_bandwidth'] else 0
        geip_count = len(resource['global_eips']) \
            if 'global_eips' in resource and resource['global_eips'] else 0

        return op(eip_count+ipv6bandwidth_count+geip_count, count)


@Loadbalancer.filter_registry.register('is-logging-enable')
class LoadbalancerIsLoggingEnableFilter(Filter):
    """Check if logging enable on ELB.

    :example:

    .. code-block:: yaml

        policies:
          - name: enable-logging-for-loadbalancer
            filters:
              - type: is-logging-enable
                enable: false
            actions:
              - type: enable-logging
                log_group_id: "c5c89263-cfce-45cf-ac08-78cf537ba6c5"
                log_topic_id: "328abfed-ab1a-4484-b2c1-031c0d06ea66"
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


@resources.register('elb.listener')
class Listener(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'elb'
        resource = 'listener'
        enum_spec = ("list_listeners", 'listeners', 'marker')
        id = 'id'
        tag = True
        tag_resource_type = 'elb'


@Listener.action_registry.register("delete")
class ListenerDeleteAction(HuaweiCloudBaseAction):
    """Deletes ELB Listeners.

    :Example:

    .. code-block:: yaml

        policies:
          - name: ensure-elb-https-only
            resource: huaweicloud.elb.listener
            filters:
              - type: value
                key: protocol
                value: "HTTPS"
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



@Listener.action_registry.register("set-ipgroup")
class ListenerSetIpgroupAction(HuaweiCloudBaseAction):
    """Set Ipgroup for ELB Listeners.

    :Example:

    .. code-block:: yaml

        policies:
          - name: set-ipgroup-for-listeners
            resource: huaweicloud.elb.listener
            filters:
              - type: attributes
                key: loadbalancers[0].id
                value: "4cce9bb7-57b1-43be-b156-108d41c69b2b"
              - not:
                - type: attributes
                  key: ipgroup.ipgroup_id
                  value: "a5fe56db-4894-416d-a9a7-684c78f5897c"
                  op: eq
                - type: attributes
                  key: ipgroup.enable_ipgroup
                  value: true
                - type: attributes
                  key: ipgroup.type
                  value: "white"
            actions:
              - type: set-ipgroup
                ipgroup_id: ["a5fe56db-4894-416d-a9a7-684c78f5897c"]
                enable: true
                ipgroup_type: white
    """

    schema = type_schema(type_name="set-ipgroup",
                         ipgroup_id={'type': 'array'},
                         enable={'type': 'boolean'},
                         ipgroup_type={'type': 'string', 'enum': ['white', 'black']})

    def perform_action(self, resource):
        ipgroup_id = ",".join(self.data.get("ipgroup_id"))
        enable = self.data.get("enable")
        ipgroup_type = self.data.get("ipgroup_type")

        client = self.manager.get_client()
        request = UpdateListenerRequest(listener_id=resource["id"])
        request.body = UpdateListenerRequestBody()
        request.body.listener = UpdateListenerOption()
        request.body.listener.ipgroup = UpdateListenerIpGroupOption(ipgroup_id=ipgroup_id, enable_ipgroup=enable, type=ipgroup_type)
        log.info(f"set ipgroup: {resource['id']}")

        response = client.update_listener(request)
        log.info(f"update listener ipgroup: {response}")
        return response


@Loadbalancer.filter_registry.register('attributes')
@Listener.filter_registry.register('attributes')
class ELBAttributesFilter(ValueFilter):
    """Filter by ELB resources attributes

    :example:

    .. code-block:: yaml
        policies:
          - name: list-autoscaling-loadbalancer
            resource: huaweicloud.elb.loadbalancer or huaweicloud.elb.listener
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
    """Filter elb resources by age.

    :example:

    .. code-block:: yaml

        policies:
          - name: list-latest-loadbalancer
            resource: huaweicloud.elb.loadbalancer or huaweicloud.elb.listener
            filters:
              - type: age
                days: 7
                op: le
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
