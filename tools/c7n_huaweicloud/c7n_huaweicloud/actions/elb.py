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
                                  UpdateListenerOption, UpdateListenerIpGroupOption)
from huaweicloudsdkgeip.v3 import DisassociateInstanceRequest
from huaweicloudsdklts.v2 import CreateTransferRequestBodyLogTransferInfo, TransferDetail, \
    CreateTransferRequestBodyLogStreams, CreateTransferRequestBody, CreateTransferRequest

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
        log.info(f"Delete loadbalancer: {resource['id']}")
        return response


class LoadbalancerEnableLoggingAction(HuaweiCloudBaseAction):
    """Enable logging for loadbalancers.

    :Example:

    .. code-block:: yaml

        policies:
          - name: enable-logging-for-loadbalancer
            filters:
              - type: is-logging
                enable: false
            actions:
              - type: enable-logging
                log_group_id: "c5c89263-cfce-45cf-ac08-78cf537ba6c5"
                log_topic_id: "328abfed-ab1a-4484-b2c1-031c0d06ea66"
    """

    schema = type_schema(type_name="enable-logging",
                         log_group_id={'type': 'string'},
                         log_topic_id={'type': 'string'},
                         required=['log_group_id', 'log_topic_id'], )

    def perform_action(self, resource):
        loadbalancer_id = resource['id']
        log_group_id = self.data.get("log_group_id")
        log_topic_id = self.data.get("log_topic_id")

        client = self.manager.get_client()
        logtank = CreateLogtankOption()
        logtank.loadbalancer_id = loadbalancer_id
        logtank.log_group_id = log_group_id
        logtank.log_topic_id = log_topic_id
        body = CreateLogtankRequestBody(logtank)
        request = CreateLogtankRequest(body)
        response = client.create_logtank(request)
        if response.status_code == 201:
            log.info(f"Enable logging for loadbalancer: {loadbalancer_id}")
            resource['log_group_id'] = log_group_id
            resource['log_topic_id'] = log_topic_id
            return response
        else:
            raise exceptions.ClientRequestException(response.status_code, response.request_id,
                                                    response.error_code, response.error_msg)


class LoadbalancerUnbindPublicipsAction(HuaweiCloudBaseAction):
    """Unbind all public IP of loadbalancers.

    :Example:

    .. code-block:: yaml

        policies:
          - name: elb-policy-3
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
                    log.info(f"Unbind ipv6_bandwidth for loadbalancer: {loadbalancer_id}")

        # unbind public ipv4
        if 'eip' in publicip_types and eip_count > 0:
            eip_client = local_session(self.manager.session_factory).client('eip')
            for eip in resource['eips']:
                if eip['ip_version'] == 4:
                    request = DisassociatePublicipsRequest(publicip_id=eip['eip_id'])
                    response = eip_client.disassociate_publicips(request)
                    log.info(f"Unbind eip: {eip['eip_address']} for loadbalancer: "
                             f"{loadbalancer_id}")

        # unbind geip
        if 'global_eip' in publicip_types and geip_count > 0:
            geip_client = local_session(self.manager.session_factory).client('geip')
            for geip in resource['global_eips']:
                request = DisassociateInstanceRequest(global_eip_id=geip['global_eip_id'])
                response = geip_client.disassociate_instance(request)
                log.info(f"Unbind global eip: {geip['eip_address']} for loadbalancer: "
                         f"{loadbalancer_id}")

        return response


class LoadbalancerCreateLTSLogTransferAction(LtsCreateTransferLog):
    """Enable logging for loadbalancers.

    :Example:

    .. code-block:: yaml

        policies:
          - name: elb-policy-4
            resource: huaweicloud.elb-loadbalancer
            filters:
              - type: attributes
                key: id
                value: "147476c5-1fa5-4743-b4e0-d52ae39e1142"
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
                obs_bucket_name: "{my_obs_bucket}"
    """

    schema = type_schema(type_name="create-lts-log-transfer",
                         rinherit=LtsCreateTransferLog.schema,
                         required=['obs_bucket_name'])

    def process(self, resources):
        if "log_transfer_type" not in self.data or not self.data["log_transfer_type"]:
            self.data.set("log_transfer_type", "OBS")
        if "log_transfer_mode" not in self.data or not self.data["log_transfer_mode"]:
            self.data.set("log_transfer_mode", "cycle")
        if "log_transfer_status" not in self.data or not self.data["log_transfer_status"]:
            self.data.set("log_transfer_status", "ENABLE")
        if "log_storage_format" not in self.data or not self.data["log_storage_format"]:
            self.data.set("log_storage_format", "JSON")
        if "obs_period" not in self.data or not self.data["obs_period"]:
            self.data.set("obs_period", 2)
        if "obs_period_unit" not in self.data or not self.data["obs_period_unit"]:
            self.data.set("obs_period_unit", "min")

        log_topic_id_set = []
        for resource in resources:
            try:
                log_group_id = resource['log_group_id']
                log_topic_id = resource['log_topic_id']
                if log_topic_id in log_topic_id_set:
                    continue
                self.data["log_group_id"] = log_group_id
                self.data["log_streams"] = []
                self.data["log_streams"].append({"log_stream_id": log_topic_id})
                self.perform_action(resource)
                log_topic_id_set.append(log_topic_id)
            except exceptions.ClientRequestException as ex:
                res = resource.get("id", resource.get("name"))
                log.exception(
                    f"Unable to submit action against the resource - {res}"
                    f" RequestId: {ex.request_id}, Reason: {ex.error_msg}"
                )
                self.handle_exception(resource, resources)
        return super().process_result(resources)

    def perform_action(self, resource):
        client = local_session(self.manager.session_factory).client("lts-transfer")
        try:
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
            for stream in self.data.get("log_streams"):
                listLogStreamsbody.append(CreateTransferRequestBodyLogStreams(
                    log_stream_id=stream["log_stream_id"]
                ))
            request.body = CreateTransferRequestBody(
                log_transfer_info=logTransferInfobody,
                log_streams=listLogStreamsbody,
                log_group_id=self.data.get("log_group_id"),
            )
            log.warning(request.body)
            response = client.create_transfer(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response


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
                loadbalancers: ['94c11c75-e3de-48b7-a5a2-28202ada60b1']
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
            client.delete_pool_cascade(pool_request)
            log.info(f"Delete listener default pool: {resource['default_pool_id']}")

        request = DeleteListenerForceRequest(listener_id=resource["id"])
        response = client.delete_listener_force(request)
        log.info(f"Delete listener: {resource['id']}")

        return response


class ListenerSetAclIpgroupAction(HuaweiCloudBaseAction):
    """Set Ipgroup for ELB Listeners.

    :Example:

    .. code-block:: yaml

        policies:
          - name: set-acl-ipgroup-for-listeners
            resource: huaweicloud.elb-listener
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
              - type: set-acl-ipgroup
                ipgroup_id: ["a5fe56db-4894-416d-a9a7-684c78f5897c"]
                enable: true
                ipgroup_type: white
    """

    schema = type_schema(type_name="set-acl-ipgroup",
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
        request.body.listener.ipgroup = UpdateListenerIpGroupOption(
            ipgroup_id=ipgroup_id, enable_ipgroup=enable, type=ipgroup_type)
        response = client.update_listener(request)
        log.info(f"Update ipgroup of listener: {resource['id']}")
        return response
