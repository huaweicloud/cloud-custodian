# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from c7n_huaweicloud.actions.elb import (ListenerRedirectAction, LoadbalancerDeleteAction,
                                         LoadbalancerEnableLoggingAction,
                                         LoadbalancerUnbindPublicipsAction,
                                         LoadbalancerCreateLTSLogTransferAction,
                                         ListenerDeleteAction,
                                         ListenerSetAclIpgroupAction)
from c7n_huaweicloud.filters.elb import (ELBAgeFilter,
                                         LoadbalancerBackendServerCountFilter,
                                         ELBAttributesFilter,
                                         LoadbalancerIsNotLoggingFilter,
                                         LoadbalancerIsLoggingFilter,
                                         LoadbalancerPublicipCountFilter,
                                         LoadbalancerIsLTSLogTransferFilter,
                                         LoadbalancerIsNotLTSLogTransferFilter,
                                         ListenerRedirectListenerFilter)
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo


@resources.register('elb-loadbalancer')
class Loadbalancer(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'elb_loadbalancer'
        enum_spec = ("list_load_balancers", 'loadbalancers', 'marker')
        id = 'id'
        tag = True
        tag_resource_type = 'loadbalancers'


Loadbalancer.action_registry.register('delete', LoadbalancerDeleteAction)
Loadbalancer.action_registry.register('enable-logging', LoadbalancerEnableLoggingAction)
Loadbalancer.action_registry.register('unbind-publicips', LoadbalancerUnbindPublicipsAction)
Loadbalancer.action_registry.register('create-lts-log-transfer',
                                      LoadbalancerCreateLTSLogTransferAction)

Loadbalancer.filter_registry.register('backend-server-count', LoadbalancerBackendServerCountFilter)
Loadbalancer.filter_registry.register('publicip-count', LoadbalancerPublicipCountFilter)
Loadbalancer.filter_registry.register('is-logging', LoadbalancerIsLoggingFilter)
Loadbalancer.filter_registry.register('is-not-logging', LoadbalancerIsNotLoggingFilter)
Loadbalancer.filter_registry.register('is-lts-log-transfer', LoadbalancerIsLTSLogTransferFilter)
Loadbalancer.filter_registry.register('is-not-lts-log-transfer',
                                      LoadbalancerIsNotLTSLogTransferFilter)
Loadbalancer.filter_registry.register('attributes', ELBAttributesFilter)
Loadbalancer.filter_registry.register('age', ELBAgeFilter)


@resources.register('elb-listener')
class Listener(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'elb_listener'
        enum_spec = ("list_listeners", 'listeners', 'marker')
        id = 'id'
        tag = True
        tag_resource_type = 'listeners'


Listener.action_registry.register('delete', ListenerDeleteAction)
Listener.action_registry.register('set-acl-ipgroup', ListenerSetAclIpgroupAction)
Listener.action_registry.register('redirect-to-https-listener', ListenerRedirectAction)

Listener.filter_registry.register('attributes', ELBAttributesFilter)
Listener.filter_registry.register('age', ELBAgeFilter)
Listener.filter_registry.register('is-redirect-to-https-listener', ListenerRedirectListenerFilter)
