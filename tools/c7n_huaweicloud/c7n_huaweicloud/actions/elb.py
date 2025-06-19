# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.resources.transfer import LtsCreateTransferLog
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkeip.v3 import DisassociatePublicipsRequest
from huaweicloudsdkelb.v3 import (DeleteLoadBalancerCascadeRequest,
                                  DeleteLoadBalancerCascadeRequestBody,
                                  DeleteLoadBalancerCascadeOption, CreateLogtankOption,
                                  CreateLogtankRequestBody, CreateLogtankRequest,
                                  UpdateLoadBalancerRequest, UpdateLoadBalancerRequestBody,
                                  DeleteListenerForceRequest, DeletePoolCascadeRequest,
                                  UpdateListenerRequest, UpdateListenerRequestBody,
                                  UpdateListenerOption, UpdateListenerIpGroupOption,
                                  CreateL7PolicyRequest, CreateL7PolicyRequestBody,
                                  CreateL7PolicyOption, ListListenersRequest,
                                  ListIpGroupsRequest)
from huaweicloudsdkgeip.v3 import DisassociateInstanceRequest
from huaweicloudsdklts.v2 import CreateTransferRequestBodyLogTransferInfo, TransferDetail, \
    CreateTransferRequestBodyLogStreams, CreateTransferRequestBody, CreateTransferRequest, \
    ListLogGroupsRequest, ListLogStreamRequest

from c7n.utils import type_schema, local_session

log = logging.getLogger("custodian.huaweicloud.resources.elb")


class LoadbalancerDeleteAction(HuaweiCloudBaseAction):
    """Delete ELB Loadbalancers.

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-public-loadbalancers
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
        request = DeleteLoadBalancerCascadeRequest(loadbalancer_id=resource["id"])
        request.body = DeleteLoadBalancerCascadeRequestBody()
        request.body.loadbalancer = (
            DeleteLoadBalancerCascadeOption(unbounded_pool=True, public_ip=False))
        response = client.delete_load_balancer_cascade(request)
        check_response(response)
        log.info(f"Successfully deleted loadbalancer: {resource['id']}")


class LoadbalancerUnbindPublicipsAction(HuaweiCloudBaseAction):
    """Unbind all public IP of loadbalancers.

    :Example:

    .. code-block:: yaml

        policies:
          - name: unbind-publicips-from-loadbalancers
            resource: huaweicloud.elb-loadbalancer
            filters:
              - type: publicip-count
                count: 0
                op: gt
            actions:
              - type: unbind-publicips
    """

    schema = type_schema(type_name="unbind-publicips",
                         publicip_types={'type': 'array'})

    def perform_action(self, resource):
        loadbalancer_id = resource['id']

        publicip_types = self.data.get("publicip_types")
        if not publicip_types or len(publicip_types) == 0:
            publicip_types = ['eip', 'ipv6_bandwidth', 'global_eip']

        eip_count = len(resource['eips']) if resource['eips'] else 0
        geip_count = len(resource['global_eips']) \
            if 'global_eips' in resource and resource['global_eips'] else 0

        response = None
        # unbind public ipv6
        if 'ipv6_bandwidth' in publicip_types and eip_count > 0:
            elb_client = self.manager.get_client()
            for eip in resource['eips']:
                if eip['ip_version'] == 6:
                    request = UpdateLoadBalancerRequest(loadbalancer_id=loadbalancer_id)
                    request.body = UpdateLoadBalancerRequestBody()
                    request.body.loadbalancer = {'ipv6_bandwidth': None}
                    response = elb_client.update_load_balancer(request)
                    check_response(response)
                    log.info(
                        f"Successfully unbind ipv6_bandwidth for loadbalancer: {loadbalancer_id}"
                    )

        # unbind public ipv4
        if 'eip' in publicip_types and eip_count > 0:
            eip_client = local_session(self.manager.session_factory).client('eip')
            for eip in resource['eips']:
                if eip['ip_version'] == 4:
                    request = DisassociatePublicipsRequest(publicip_id=eip['eip_id'])
                    response = eip_client.disassociate_publicips(request)
                    check_response(response)
                    log.info(f"Successfully unbind eip: {eip['eip_address']} for loadbalancer: "
                             f"{loadbalancer_id}")

        # unbind geip
        if 'global_eip' in publicip_types and geip_count > 0:
            geip_client = local_session(self.manager.session_factory).client('geip')
            for geip in resource['global_eips']:
                request = DisassociateInstanceRequest(global_eip_id=geip['global_eip_id'])
                response = geip_client.disassociate_instance(request)
                check_response(response)
                log.info(f"Successfully unbind global eip: {geip['eip_address']} for loadbalancer: "
                         f"{loadbalancer_id}")


class LoadbalancerEnableLoggingAction(HuaweiCloudBaseAction):
    """Enable logging for loadbalancers.

    :Example:

    .. code-block:: yaml

        policies:
          - name: enable-logging-for-loadbalancers
            filters:
              - type: is-not-logging
            actions:
              - type: enable-logging
                log_group_name: "{my-log-group}  # Replace with your log group name"
                log_topic_name: "{my-log-topic}  # Replace with your log topic name"
    """

    schema = type_schema(type_name="enable-logging",
                         log_group_id={'type': 'string'},
                         log_group_name={'type': 'string'},
                         log_topic_id={'type': 'string'},
                         log_topic_name={'type': 'string'})

    def perform_action(self, resource):
        loadbalancer_id = resource['id']
        log_group_id = self.data.get("log_group_id")
        log_topic_id = self.data.get("log_topic_id")
        log_group_name = self.data.get("log_group_name")
        log_topic_name = self.data.get("log_topic_name")

        if not log_group_id and not log_group_name:
            log.error("log_group_id or log_group_name must be provided.")
            raise Exception("log_group_id or log_group_name must be provided.")
        if not log_topic_id and not log_topic_name:
            log.error("log_topic_id or log_topic_name must be provided.")
            raise Exception("log_topic_id or log_topic_name must be provided.")

        lts_client = local_session(self.manager.session_factory).client('lts-stream')
        log_group_response = lts_client.list_log_groups(ListLogGroupsRequest())
        check_response(log_group_response)
        resp_log_group_id = None
        if log_group_id:
            for group in log_group_response.log_groups:
                if group.log_group_id == log_group_id:
                    if log_group_name and group.log_group_name != log_group_name:
                        log.error(f"Log group name '{log_group_name}' does not"
                                  f" match log group id '{log_group_id}'")
                        raise Exception(f"Log group name '{log_group_name}' "
                                        f"does not match log group id '{log_group_id}'")
                    resp_log_group_id = group.log_group_id
                    break
        elif log_group_name:
            for group in log_group_response.log_groups:
                if group.log_group_name == log_group_name:
                    resp_log_group_id = group.log_group_id
                    break
        if not resp_log_group_id:
            log.error("Log group with specified 'log_group_name' "
                      "or 'log_group_id' not found.")
            raise Exception("Log group with specified"
                " 'log_group_name' or 'log_group_id' not found.")

        log_stream_response = lts_client.list_log_stream(
            ListLogStreamRequest(log_group_id=resp_log_group_id)
        )
        check_response(log_stream_response, f"log_group_id={resp_log_group_id}")
        resp_log_stream_id = None
        if log_topic_id:
            for topic in log_stream_response.log_streams:
                if topic.log_stream_id == log_topic_id:
                    if log_topic_name and topic.log_stream_name != log_topic_name:
                        log.error(
                            f"Log topic name '{log_topic_name}' does not match "
                            f"log topic id '{log_topic_id}'"
                        )
                        raise Exception(
                            f"Log topic name '{log_topic_name}' does not match "
                            f"log topic id '{log_topic_id}'"
                        )
                    resp_log_stream_id = topic.log_stream_id
                    break
        elif log_topic_name:
            for topic in log_stream_response.log_streams:
                if topic.log_stream_name == log_topic_name:
                    resp_log_stream_id = topic.log_stream_id
                    break
        if not resp_log_stream_id:
            log.error("Log topic with specified 'log_topic_name' or 'log_topic_id' not found.")
            raise Exception(
                "Log topic with specified 'log_topic_name' or 'log_topic_id' not found."
            )

        client = self.manager.get_client()
        logtank = CreateLogtankOption(loadbalancer_id=loadbalancer_id,
                                      log_group_id=resp_log_group_id,
                                      log_topic_id=resp_log_stream_id)
        request = CreateLogtankRequest(CreateLogtankRequestBody(logtank))
        response = client.create_logtank(request)
        check_response(response, params=logtank)
        resource['log_group_id'] = resp_log_group_id
        resource['log_topic_id'] = resp_log_stream_id
        log.info(f"Successfully enabled logging for loadbalancer: {loadbalancer_id}")


class LoadbalancerCreateLTSLogTransferAction(LtsCreateTransferLog):
    """Enable logging transfer for loadbalancers.

    :Example:

    .. code-block:: yaml

        policies:
          - name: enable-lts-log-transfer-for-loadbalancers
            resource: huaweicloud.elb-loadbalancer
            filters:
              - type: is-logging
              - type: is-not-lts-log-transfer
            actions:
              - type: create-lts-log-transfer
                log_transfer_type: "OBS"
                log_transfer_mode: "cycle"
                log_transfer_status: "ENABLE"
                log_storage_format: "JSON"
                obs_period: 2
                obs_period_unit: "min"
                obs_bucket_name: "{my_obs_bucket_name   # Replace with your OBS bucket name}"
    """

    schema = type_schema(type_name="create-lts-log-transfer",
                         rinherit=LtsCreateTransferLog.schema,
                         exclude=['log_group_id', 'log_streams'],
                         required=['obs_bucket_name'])

    def process(self, resources):
        if "log_transfer_type" not in self.data or not self.data["log_transfer_type"]:
            self.data["log_transfer_type"] = "OBS"
        if "log_transfer_mode" not in self.data or not self.data["log_transfer_mode"]:
            self.data["log_transfer_mode"] = "cycle"
        if "log_transfer_status" not in self.data or not self.data["log_transfer_status"]:
            self.data["log_transfer_status"] = "ENABLE"
        if "log_storage_format" not in self.data or not self.data["log_storage_format"]:
            self.data["log_storage_format"] = "JSON"
        if "obs_period" not in self.data or not self.data["obs_period"]:
            self.data["obs_period"] = 2
        if "obs_period_unit" not in self.data or not self.data["obs_period_unit"]:
            self.data["obs_period_unit"] = "min"

        log_topic_id_set = []
        for resource in resources:
            log_group_id = resource['log_group_id']
            log_topic_id = resource['log_topic_id']
            if log_topic_id in log_topic_id_set:
                continue
            self.data["log_group_id"] = log_group_id
            self.data["log_streams"] = [log_topic_id]
            self.perform_action(resource)
            log_topic_id_set.append(log_topic_id)
        return super().process_result(resources)

    def perform_action(self, resource):
        client = local_session(self.manager.session_factory).client("lts-transfer")
        request = CreateTransferRequest()
        logTransferDetailLogTransferInfo = TransferDetail(
            obs_period=self.data.get('obs_period'),
            obs_period_unit=self.data.get('obs_period_unit'),
            obs_bucket_name=self.data.get('obs_bucket_name')
        )
        logTransferInfobody = CreateTransferRequestBodyLogTransferInfo(
            log_transfer_type=self.data.get('log_transfer_type'),
            log_transfer_mode=self.data.get('log_transfer_mode'),
            log_storage_format=self.data.get('log_storage_format'),
            log_transfer_status=self.data.get('log_transfer_status'),
            log_transfer_detail=logTransferDetailLogTransferInfo
        )
        listLogStreamsbody = []
        for log_stream_id in self.data.get("log_streams"):
            listLogStreamsbody.append(CreateTransferRequestBodyLogStreams(
                log_stream_id=log_stream_id
            ))
        request.body = CreateTransferRequestBody(
            log_transfer_info=logTransferInfobody,
            log_streams=listLogStreamsbody,
            log_group_id=self.data.get("log_group_id"),
        )
        log.warning(request.body)
        response = client.create_transfer(request)
        check_response(response, service_name="LTS Transfer", params=request.body)


class ListenerDeleteAction(HuaweiCloudBaseAction):
    """Delete ELB Listeners.

    :Example:

    .. code-block:: yaml

        policies:
          - name: ensure-elb-https-only
            resource: huaweicloud.elb-listener
            filters:
              - type: value
                key: protocol
                value: "HTTPS"
                op: ne
            actions:
              - type: delete
    """

    schema = type_schema(type_name="delete",
                         loadbalancers={'type': 'array'})

    def perform_action(self, resource):
        lb_from_schema = self.data.get("loadbalancers")
        if (lb_from_schema and len(lb_from_schema) > 0
                and resource['loadbalancers'][0]['id'] not in lb_from_schema):
            return

        client = self.manager.get_client()

        if ('default_pool_id' in resource and resource['default_pool_id'] and
                len(resource['default_pool_id']) > 0):
            pool_request = DeletePoolCascadeRequest(pool_id=resource['default_pool_id'])
            pool_response = client.delete_pool_cascade(pool_request)
            check_response(pool_response)
            log.info(f"Successfully deleted listener default pool: {resource['default_pool_id']}")

        request = DeleteListenerForceRequest(listener_id=resource["id"])
        response = client.delete_listener_force(request)
        check_response(response)
        log.info(f"Successfully deleted listener: {resource['id']}")


class ListenerSetAclIpgroupAction(HuaweiCloudBaseAction):
    """Enable Ipgroup for ELB Listeners.

    :Example:

    .. code-block:: yaml

        policies:
          - name: set-acl-ipgroup-for-listeners
            resource: huaweicloud.elb-listener
            filters:
              - not:
                - type: attributes
                  key: ipgroup.enable_ipgroup
                  value: true
                - type: attributes
                  key: ipgroup.type
                  value: "white"
            actions:
              - type: set-acl-ipgroup
                ipgroup_name: ["my-ipgroup"]
                ipgroup_type: white
    """

    schema = type_schema(type_name="set-acl-ipgroup",
                         ipgroup_id={'type': 'array'},
                         ipgroup_name={'type': 'array'},
                         enable={'type': 'boolean', 'default': True},
                         ipgroup_type={'type': 'string', 'enum': ['white', 'black']},
                         required=['ipgroup_type'])

    def perform_action(self, resource):
        ipgroup_id = ",".join(self.data.get("ipgroup_id")) if self.data.get("ipgroup_id") else None
        ipgroup_name = (
            ",".join(self.data.get("ipgroup_name"))
            if self.data.get("ipgroup_name") else None
        )
        enable = self.data.get("enable")
        ipgroup_type = self.data.get("ipgroup_type")

        if (
            (not ipgroup_id or len(ipgroup_id) == 0)
            and (not ipgroup_name or len(ipgroup_name) == 0)
        ):
            log.error("Either 'ipgroup_id' or 'ipgroup_name' must be provided.")
            raise Exception("Either 'ipgroup_id' or 'ipgroup_name' must be provided.")

        client = self.manager.get_client()
        ipgroup_request = ListIpGroupsRequest(
            enterprise_project_id=["all_granted_eps"],
            name=[ipgroup_name] if ipgroup_name else None,
            id=[ipgroup_id] if ipgroup_id else None,
        )
        ipgroup_response = client.list_ip_groups(ipgroup_request)
        check_response(ipgroup_response)
        if not ipgroup_response.ipgroups or len(ipgroup_response.ipgroups) == 0:
            log.error(f"No ip_groups found for name: {ipgroup_name} or id: {ipgroup_id}")
            raise Exception(f"No ip_groups found for name: {ipgroup_name} or id: {ipgroup_id}")
        ipgroup_ids = [ipgroup.id for ipgroup in ipgroup_response.ipgroups]
        ipgroup_ids_str = ",".join(ipgroup_ids)

        request = UpdateListenerRequest(listener_id=resource["id"])
        request.body = UpdateListenerRequestBody()
        request.body.listener = UpdateListenerOption()
        request.body.listener.ipgroup = UpdateListenerIpGroupOption(
            ipgroup_id=ipgroup_ids_str, enable_ipgroup=enable, type=ipgroup_type)
        response = client.update_listener(request)
        check_response(response, params=request.body)
        log.info(f"Successfully updated ipgroup of listener: {resource['id']}")


class ListenerRedirectAction(HuaweiCloudBaseAction):
    """Set redirect to HTTPS listener for HTTP Listeners.
    Note: Only support HTTP to HTTPS redirection.

    :Example:

    .. code-block:: yaml

        policies:
          - name: redirect-to-https-listener
            resource: huaweicloud.elb-listener
            filters:
              - not:
                - type: is-redirect-to-https-listener
            actions:
              - type: redirect-to-https-listener
                name: my-https-listener
    """

    schema = type_schema(type_name="redirect-to-https-listener",
                         id={'type': 'string'},
                         name={'type': 'string'},
                         port={'type': 'number', 'minimum': 0})

    def perform_action(self, resource):
        if resource['protocol'] != 'HTTP':
            return
        redirect_listener_id = self.data.get('id', None)
        name = self.data.get('name', None)
        port = self.data.get('port', None)
        listener_id = resource['id']

        client = self.manager.get_client()
        # List all listeners by the given parameters
        request = ListListenersRequest(
            enterprise_project_id=["all_granted_eps"],
            id=[redirect_listener_id] if redirect_listener_id else None,
            name=[name] if name else None,
            protocol=['HTTPS'],
            protocol_port=[port] if port is not None else None
        )
        response = client.list_listeners(request)
        check_response(response)
        if not response.listeners or len(response.listeners) == 0:
            log.error(f"No listeners found for id: {redirect_listener_id}, "
                      f"name: {name}, protocol: HTTPS, port: {port}")
            raise Exception(f"No listeners found for id: {redirect_listener_id}, "
                            f"name: {name}, protocol: HTTPS, port: {port}")
        listener = response.listeners[0]
        redirect_listener_id = listener.id
        request = CreateL7PolicyRequest(
            body=CreateL7PolicyRequestBody(
                l7policy=CreateL7PolicyOption(
                    action='REDIRECT_TO_LISTENER',
                    listener_id=listener_id,
                    redirect_listener_id=redirect_listener_id
                )
            )
        )
        response = client.create_l7_policy(request)
        check_response(response, params=request.body)
        log.info(
            f"Successfully redirected listener {listener_id} to listener {redirect_listener_id}"
        )
        return response


def check_response(response, service_name="ELB", params=None):
    if response is None:
        log.error(f"Failed to get response from {service_name} service.")
        if params:
            log.error(f"Parameters: {params}")
        raise exceptions.SdkException(
            f"Failed to get response from {service_name} service."
        )
    if response.status_code != 200 and response.status_code != 201 and response.status_code != 204:
        log.error(
            f"Response failed from {service_name} service: {response.status_code}, "
            f"{response.request_id}, {response.error_code}, {response.error_msg}"
        )
        if params:
            log.error(f"Parameters: {params}")
        raise exceptions.ServiceResponseException(
            f"Get response from {service_name} service failed: {response.error_msg}. ",
            response.error_code
        )
