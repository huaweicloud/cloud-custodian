# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from functools import wraps
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
                                  ListIpGroupsRequest, CreateIpGroupRequest,
                                  CreateIpGroupRequestBody, CreateIpGroupOption)
from huaweicloudsdkgeip.v3 import DisassociateInstanceRequest
from huaweicloudsdklts.v2 import CreateTransferRequestBodyLogTransferInfo, TransferDetail, \
    CreateTransferRequestBodyLogStreams, CreateTransferRequestBody, CreateTransferRequest, \
    ListLogGroupsRequest, ListLogStreamRequest, CreateLogGroupRequest, \
    CreateLogGroupParams, CreateLogStreamRequest, CreateLogStreamParams

from c7n.utils import type_schema, local_session

log = logging.getLogger("custodian.huaweicloud.resources.elb")


def wrap_perform_action_log(resource_name):
    """Decorator to wrap the perform_action method for logging and error handling."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                log.info(
                    f"[actions]-[{args[0].data.get('type', 'UnknownAction')}] "
                    f"Success to deal resource[{resource_name}] with id:[{args[1]['id']}]. "
                )
                return result
            except exceptions.SdkException as e:
                log.error(
                    f"[actions]-[{args[0].data.get('type', 'UnknownAction')}] "
                    f"Failed to deal resource[{resource_name}] with id:[{args[1]['id']}]. "
                    f"Exception: {e}"
                )
                # Raise the exception if it is a RequestTimeoutException or has a 403 status code
                if isinstance(e, exceptions.RequestTimeoutException):
                    raise e
                if hasattr(e, 'status_code') and e.status_code == 403:
                    raise e

        return wrapper
    return decorator


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

    @wrap_perform_action_log("huaweicloud.elb-loadbalancer")
    def perform_action(self, resource):
        client = self.manager.get_client()
        request = DeleteLoadBalancerCascadeRequest(loadbalancer_id=resource["id"])
        request.body = DeleteLoadBalancerCascadeRequestBody()
        request.body.loadbalancer = (
            DeleteLoadBalancerCascadeOption(unbounded_pool=True, public_ip=False))
        client.delete_load_balancer_cascade(request)


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

    @wrap_perform_action_log("huaweicloud.elb-loadbalancer")
    def perform_action(self, resource):
        loadbalancer_id = resource['id']

        publicip_types = self.data.get("publicip_types")
        if not publicip_types or len(publicip_types) == 0:
            publicip_types = ['eip', 'ipv6_bandwidth', 'global_eip']

        eip_count = len(resource['eips']) if resource['eips'] else 0
        geip_count = len(resource['global_eips']) \
            if 'global_eips' in resource and resource['global_eips'] else 0

        # unbind public ipv6
        if 'ipv6_bandwidth' in publicip_types and eip_count > 0:
            elb_client = self.manager.get_client()
            for eip in resource['eips']:
                if eip['ip_version'] == 6:
                    request = UpdateLoadBalancerRequest(loadbalancer_id=loadbalancer_id)
                    request.body = UpdateLoadBalancerRequestBody()
                    request.body.loadbalancer = {'ipv6_bandwidth': None}
                    elb_client.update_load_balancer(request)
                    log.info(
                        f"[actions]-[{self.data.get('type', 'UnknownAction')}] "
                        f"The resource[huaweicloud.elb-loadbalancer] with id:[{loadbalancer_id}] "
                        f"is unbinded ipv6 eip: {eip['eip_address']} successfully."
                    )

        # unbind public ipv4
        if 'eip' in publicip_types and eip_count > 0:
            eip_client = local_session(self.manager.session_factory).client('eip')
            for eip in resource['eips']:
                if eip['ip_version'] == 4:
                    request = DisassociatePublicipsRequest(publicip_id=eip['eip_id'])
                    eip_client.disassociate_publicips(request)
                    log.info(
                        f"[actions]-[{self.data.get('type', 'UnknownAction')}] "
                        f"The resource[huaweicloud.elb-loadbalancer] with id:[{loadbalancer_id}] "
                        f"is unbinded ipv4 eip: {eip['eip_address']} successfully."
                    )

        # unbind geip
        if 'global_eip' in publicip_types and geip_count > 0:
            geip_client = local_session(self.manager.session_factory).client('geip')
            for geip in resource['global_eips']:
                request = DisassociateInstanceRequest(global_eip_id=geip['global_eip_id'])
                geip_client.disassociate_instance(request)
                log.info(
                    f"[actions]-[{self.data.get('type', 'UnknownAction')}] "
                    f"The resource[huaweicloud.elb-loadbalancer] with id:[{loadbalancer_id}] "
                    f"is unbinded global eip: {geip['eip_address']} successfully."
                )


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
                creation: "always"  # Create new log group and topic or not. Options are:
                                    # "no" - means do not create. Default is "no".
                                    # "always" - means create new log group and topic.
                                    # "create-if-absent" - means create if not exists.
                log_group_name: "{my-log-group}  # Rrequired. Replace with your log group name."
                log_group_tags: # Optional. Only meaningful when creation is "always" or
                                # "create-if-absent."
                    - key: "key1"
                      value: "value1"
                log_group_ttl_in_days: 30 # Log storage time (days), value range: 1-30,
                                          # default is 30.
                                          # Optional. Only meaningful when creation is "always" or
                                          # "create-if-absent"
                log_topic_name: "{my-log-topic}  # Rrequired. Replace with your log topic name."
                log_topic_tags: # Optional. Only meaningful when creation is "always" or
                                # "create-if-absent."
                    - key: "key1"
                      value: "value1"
                log_topic_ttl_in_days: 30 # Log storage time (days), value range: 1-30.
                                          # Optional, default is 30.
                                          # Optional. Only meaningful when creation is "always" or
                                          # "create-if-absent."
    """

    schema = type_schema(
        type_name="enable-logging",
        creation={
            'type': 'string',
            'enum': ['no', 'always', 'create-if-absent'],
            'default': 'no'
        },
        log_group_id={'type': 'string'},
        log_group_name={'type': 'string'},
        log_group_ttl_in_days={'type': 'integer', 'minimum': 1, 'maximum': 30},
        log_group_tags={'type': 'array', 'items': {
                    'type': 'object',
                    'required': ['key', 'value'],
                    'properties': {
                        'key': {'type': 'string'},
                        'value': {'type': 'string'},
                    }
                }},
        log_topic_id={'type': 'string'},
        log_topic_name={'type': 'string'},
        log_topic_ttl_in_days={'type': 'integer', 'minimum': 1, 'maximum': 30},
        log_topic_tags={'type': 'array', 'items': {
                    'type': 'object',
                    'required': ['key', 'value'],
                    'properties': {
                        'key': {'type': 'string'},
                        'value': {'type': 'string'},
                    }
                }},
        enterprise_project_name={'type': 'string'}
    )

    @wrap_perform_action_log("huaweicloud.elb-loadbalancer")
    def perform_action(self, resource):
        loadbalancer_id = resource['id']
        creation = self.data.get("creation", "no")

        log_group_id = self.data.get("log_group_id")
        log_group_name = self.data.get("log_group_name")
        log_group_ttl_in_days = self.data.get("log_group_ttl_in_days", 30)
        log_group_tags = self.data.get("log_group_tags", [])

        log_topic_id = self.data.get("log_topic_id")
        log_topic_name = self.data.get("log_topic_name")
        log_topic_ttl_in_days = self.data.get("log_topic_ttl_in_days", 30)
        log_topic_tags = self.data.get("log_topic_tags", [])

        enterprise_project_name = self.data.get("enterprise_project_name", "default")

        if creation == "always":
            resp_log_group_id = self.create_log_group(
                log_group_name,
                log_group_ttl_in_days,
                log_group_tags
            )
            resp_log_stream_id = self.create_log_topic(
                resp_log_group_id,
                log_topic_name,
                log_topic_ttl_in_days,
                log_topic_tags,
                enterprise_project_name
            )
        elif creation == "create-if-absent":
            resp_log_group_id, resp_log_stream_id = self.check_logging_existence(
                log_group_id, log_group_name, log_topic_id, log_topic_name
            )
            if not resp_log_group_id:
                resp_log_group_id = self.create_log_group(
                    log_group_name,
                    log_group_ttl_in_days,
                    log_group_tags
                )
            if not resp_log_stream_id:
                resp_log_stream_id = self.create_log_topic(
                    resp_log_group_id,
                    log_topic_name,
                    log_topic_ttl_in_days,
                    log_topic_tags,
                    enterprise_project_name
                )
        else:
            resp_log_group_id, resp_log_stream_id = self.check_logging_existence(
                log_group_id, log_group_name, log_topic_id, log_topic_name
            )
            if not resp_log_group_id or not resp_log_stream_id:
                raise Exception("Log group or log topic does not exist and "
                                "creation is set to 'no'. Cannot enable logging.")

        client = self.manager.get_client()
        logtank = CreateLogtankOption(loadbalancer_id=loadbalancer_id,
                                      log_group_id=resp_log_group_id,
                                      log_topic_id=resp_log_stream_id)
        request = CreateLogtankRequest(CreateLogtankRequestBody(logtank))
        client.create_logtank(request)
        resource['log_group_id'] = resp_log_group_id
        resource['log_topic_id'] = resp_log_stream_id

    def create_log_group(self, log_group_name, group_ttl_in_days, log_group_tags):
        lts_client = local_session(self.manager.session_factory).client('lts-stream')
        log_group_request = CreateLogGroupRequest()
        log_group_request.body = CreateLogGroupParams(log_group_name=log_group_name,
                                          ttl_in_days=group_ttl_in_days,
                                          tags=log_group_tags)
        group_response = lts_client.create_log_group(log_group_request)
        log_group_id = group_response.log_group_id
        log.info(
            f"[actions]-[{self.data.get('type', 'UnknownAction')}] "
            f"Successfully created log group: {log_group_name}, id: {log_group_id}"
        )
        return log_group_id

    def create_log_topic(self, log_group_id,
                       log_topic_name, log_topic_ttl_in_days, log_topic_tags,
                       enterprise_project_name):
        lts_client = local_session(self.manager.session_factory).client('lts-stream')

        log_topic_request = CreateLogStreamRequest()
        log_topic_request.log_group_id = log_group_id
        log_topic_request.body = CreateLogStreamParams(log_stream_name=log_topic_name,
                                            ttl_in_days=log_topic_ttl_in_days,
                                            tags=log_topic_tags,
                                            enterprise_project_name=enterprise_project_name)
        topic_response = lts_client.create_log_stream(log_topic_request)
        log_topic_id = topic_response.log_stream_id
        log.info(
            f"[actions]-[{self.data.get('type', 'UnknownAction')}] "
            f"Successfully created log topic: {log_topic_name}, id: {log_topic_id}"
        )
        return log_topic_id

    def check_logging_existence(self, log_group_id, log_group_name,
                                log_topic_id, log_topic_name):

        if not log_group_id and not log_group_name:
            log.error(
                f"[actions]-[{self.data.get('type', 'UnknownAction')}] "
                "log_group_id or log_group_name must be provided "
                "in the policy action type 'enable-logging'."
            )
            raise Exception("log_group_id or log_group_name must be provided"
                            " in the policy action type 'enable-logging'.")
        if not log_topic_id and not log_topic_name:
            log.error(
                f"[actions]-[{self.data.get('type', 'UnknownAction')}] "
                "log_topic_id or log_topic_name must be provided "
                "in the policy action type 'enable-logging'.")
            raise Exception("log_topic_id or log_topic_name must be provided"
                            " in the policy action type 'enable-logging'.")

        lts_client = local_session(self.manager.session_factory).client('lts-stream')
        log_group_response = lts_client.list_log_groups(ListLogGroupsRequest())
        resp_log_group_id = None
        if log_group_id:
            for group in log_group_response.log_groups:
                if group.log_group_id == log_group_id:
                    if log_group_name and group.log_group_name != log_group_name:
                        log.error(
                            f"[actions]-[{self.data.get('type', 'UnknownAction')}] "
                            f"Log group name '{log_group_name}' does not"
                            f" match log group id '{log_group_id}'"
                        )
                        raise Exception(
                            f"Log group name '{log_group_name}' "
                            f"does not match log group id '{log_group_id}'"
                        )
                    resp_log_group_id = group.log_group_id
                    break
            if not resp_log_group_id:
                log.info(
                    f"[actions]-[{self.data.get('type', 'UnknownAction')}] "
                    f"Log group with specified log_group_id='{log_group_id}' not found."
                )
                return None, None
        elif log_group_name:
            for group in log_group_response.log_groups:
                if group.log_group_name == log_group_name:
                    resp_log_group_id = group.log_group_id
                    break
            if not resp_log_group_id:
                log.info(
                    f"[actions]-[{self.data.get('type', 'UnknownAction')}] "
                    f"Log group with specified log_group_name='{log_group_name}' not found."
                )
                return None, None

        log_stream_response = lts_client.list_log_stream(
            ListLogStreamRequest(log_group_id=resp_log_group_id)
        )
        resp_log_stream_id = None
        if log_topic_id:
            for topic in log_stream_response.log_streams:
                if topic.log_stream_id == log_topic_id:
                    if log_topic_name and topic.log_stream_name != log_topic_name:
                        log.error(
                            f"[actions]-[{self.data.get('type', 'UnknownAction')}] "
                            f"Log topic name '{log_topic_name}' does not match "
                            f"log topic id '{log_topic_id}'"
                        )
                        raise Exception(
                            f"Log topic name '{log_topic_name}' does not match "
                            f"log topic id '{log_topic_id}'"
                        )
                    resp_log_stream_id = topic.log_stream_id
                    break
            if not resp_log_stream_id:
                log.info(
                    f"[actions]-[{self.data.get('type', 'UnknownAction')}] "
                    f"Log topic with specified log_topic_id='{log_topic_id}' not found."
                )
                return resp_log_group_id, None
        elif log_topic_name:
            for topic in log_stream_response.log_streams:
                if topic.log_stream_name == log_topic_name:
                    resp_log_stream_id = topic.log_stream_id
                    break
            if not resp_log_stream_id:
                log.info(
                    f"[actions]-[{self.data.get('type', 'UnknownAction')}] "
                    f"Log topic with specified log_topic_name='{log_topic_name}' not found."
                )
                return resp_log_group_id, None
        return resp_log_group_id, resp_log_stream_id


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

    @wrap_perform_action_log("huaweicloud.elb-loadbalancer")
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
        client.create_transfer(request)


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

    @wrap_perform_action_log("huaweicloud.elb-listener")
    def perform_action(self, resource):
        lb_from_schema = self.data.get("loadbalancers")
        if (lb_from_schema and len(lb_from_schema) > 0
                and resource['loadbalancers'][0]['id'] not in lb_from_schema):
            return

        client = self.manager.get_client()

        if ('default_pool_id' in resource and resource['default_pool_id'] and
                len(resource['default_pool_id']) > 0):
            try:
                pool_request = DeletePoolCascadeRequest(pool_id=resource['default_pool_id'])
                client.delete_pool_cascade(pool_request)
                log.info(
                    f"[actions]-[{self.data.get('type', 'UnknownAction')}] "
                    f"Successfully deleted listener default pool: {resource['default_pool_id']}"
                )
            except exceptions.SdkException as e:
                log.warning(
                    f"[actions]-[{self.data.get('type', 'UnknownAction')}] "
                    f"Failed to delete listener default pool: {resource['default_pool_id']}, "
                    f"error: {str(e)}"
                )

        request = DeleteListenerForceRequest(listener_id=resource["id"])
        client.delete_listener_force(request)


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
                creation: "always"  # Create new ipgroup or not. Options are:
                                    # "no" - means do not create. Default is "no".
                                    # "always" - means create new ipgroup.
                                    # "create-if-absent" - means create if not exists.
                                    # (compare using the ipgroup_name).
                description: 'some description' # only meaningful for creating new ipgroup when
                                            # creation is "always" or "create-if-absent."
                ip_list:
                - ip: '192.168.0.1'
                    description: 'some description'
                - ip: '192.168.0.0/24'
                    description: 'some description'
                - ip: '192.168.0.10-192.168.0.99'
                    description: 'some description'
    """

    schema = type_schema(type_name="set-acl-ipgroup",
                         ipgroup_id={'type': 'array'},
                         ipgroup_name={'type': 'array'},
                         enable={'type': 'boolean', 'default': True},
                         ipgroup_type={'type': 'string', 'enum': ['white', 'black']},
                         required=['ipgroup_type'],
                         creation={
                             'type': 'string',
                             'enum': ['no', 'always', 'create-if-absent'],
                             'default': 'no'
                         },
                         description={'type': 'string'},
                         ip_list={
                             'type': 'array',
                             'items': {
                                 'type': 'object',
                                 'properties': {
                                     'ip': {'type': 'string'},
                                     'description': {'type': 'string'}
                                 },
                                 'required': ['ip']
                             }
                         },
                         enterprise_project_name={'type': 'string'})

    @wrap_perform_action_log("huaweicloud.elb-listener")
    def perform_action(self, resource):
        ipgroup_ids = self.data.get("ipgroup_id", [])
        ipgroup_names = self.data.get("ipgroup_name", [])
        enable = self.data.get("enable", True)
        ipgroup_type = self.data.get("ipgroup_type", "white")
        creation = self.data.get("creation", "no")
        description = self.data.get("description", "")
        ip_list = self.data.get("ip_list", [])
        enterprise_project_name = self.data.get("enterprise_project_name", "default")

        if (not ipgroup_ids or len(ipgroup_ids) == 0) \
            and (not ipgroup_names or len(ipgroup_names) == 0):
            log.error(
                f"[actions]-[{self.data.get('type', 'UnknownAction')}] "
                "ipgroup_id or ipgroup_name must be provided "
                "in the policy action type 'set-acl-ipgroup'."
            )
            raise Exception("ipgroup_id or ipgroup_name must be provided"
                            " in the policy action type 'set-acl-ipgroup'.")

        ipgroup_name = len(ipgroup_names) > 0 and ipgroup_names[0] or ""
        ipgroups = []
        if creation == "always":
            ipgroups = [self.create_ipgroup(
                ipgroup_name, ip_list, enterprise_project_name, description)]
        elif creation == "create-if-absent":
            all_finded, ipgroups = self.get_ipgroup(ipgroup_ids, ipgroup_names)
            if not all_finded:
                ipgroups = [self.create_ipgroup(
                    ipgroup_name, ip_list, enterprise_project_name, description)]
        else:
            all_finded, ipgroups = self.get_ipgroup(ipgroup_ids, ipgroup_names)
            if not all_finded:
                raise Exception("Ipgroup does not exist and creation is set to 'no'."
                                " Cannot set acl ipgroup.")

        ipgroup_ids = [ipgroup.id for ipgroup in ipgroups]
        ipgroup_ids_str = ",".join(ipgroup_ids)

        request = UpdateListenerRequest(listener_id=resource["id"])
        request.body = UpdateListenerRequestBody()
        request.body.listener = UpdateListenerOption()
        request.body.listener.ipgroup = UpdateListenerIpGroupOption(
            ipgroup_id=ipgroup_ids_str, enable_ipgroup=enable, type=ipgroup_type)
        client = self.manager.get_client()
        client.update_listener(request)

    def get_ipgroup(self, ipgroup_ids, ipgroup_names):
        client = self.manager.get_client()
        ipgroup_request = ListIpGroupsRequest(
            enterprise_project_id=["all_granted_eps"],
            name=ipgroup_names if ipgroup_names and len(ipgroup_names) > 0 else None,
            id=ipgroup_ids if ipgroup_ids and len(ipgroup_ids) > 0 else None
        )
        ipgroup_response = client.list_ip_groups(ipgroup_request)
        if not ipgroup_response.ipgroups:
            log.warning(
                f"[actions]-[{self.data.get('type', 'UnknownAction')}] "
                f"No ip_groups found for name: {ipgroup_names} or id: {ipgroup_ids}"
            )
            return False, []

        all_name_finded = True
        if (ipgroup_names and len(ipgroup_names) > 0
                and len(ipgroup_response.ipgroups) < len(ipgroup_names) and
                any(ipgroup.name not in ipgroup_names for ipgroup in ipgroup_response.ipgroups)):
            log.warning(
                f"[actions]-[{self.data.get('type', 'UnknownAction')}] "
                f"Some ip_groups not found for name: {ipgroup_names}"
            )
            all_name_finded = False
        all_id_finded = True
        if (ipgroup_ids and len(ipgroup_ids) > 0
                and len(ipgroup_response.ipgroups) < len(ipgroup_ids) and
                any(ipgroup.id not in ipgroup_ids for ipgroup in ipgroup_response.ipgroups)):
            log.warning(
                f"[actions]-[{self.data.get('type', 'UnknownAction')}] "
                f"Some ip_groups not found for id: {ipgroup_ids}"
            )
            all_id_finded = False

        return all_name_finded and all_id_finded, ipgroup_response.ipgroups

    def create_ipgroup(self, ipgroup_name, ip_list, enterprise_project_name, description):
        client = self.manager.get_client()
        ip_list_body = []
        for ip in ip_list:
            ip_list_body.append({'ip': ip['ip'], 'description': ip.get('description', '')})
        request = CreateIpGroupRequest()
        request.body = CreateIpGroupRequestBody()
        request.body.ipgroup = CreateIpGroupOption()
        request.body.ipgroup.name = ipgroup_name
        request.body.ipgroup.description = description
        request.body.ipgroup.ip_list = ip_list_body
        if not enterprise_project_name or len(enterprise_project_name) == 0 or \
                enterprise_project_name == "default":
            enterprise_project_id = "0"
            request.body.ipgroup.enterprise_project_id = enterprise_project_id
        # else:
        #     ep_client = local_session(self.manager.session_factory).client('eps')
        #     ep_request = ListEnterpriseProjectsRequest()
        #     ep_request.name = [enterprise_project_name]
        #     ep_response = ep_client.list_enterprise_projects(ep_request)
        #     if not ep_response.enterprise_projects or len(ep_response.enterprise_projects) == 0:
        #         log.error(
        #             f"[actions]-[{self.data.get('type', 'UnknownAction')}] "
        #             f"Enterprise project with name '{enterprise_project_name}' not found."
        #         )
        #         raise Exception(
        #             f"Enterprise project with name '{enterprise_project_name}' "
        #             "not found."
        #         )
        #     enterprise_project_id = ep_response.enterprise_projects[0].id
        #     request.body.ipgroup.enterprise_project_id = enterprise_project_id
        response = client.create_ip_group(request)
        log.info(
            f"[actions]-[{self.data.get('type', 'UnknownAction')}] "
            f"Successfully created ipgroup: {ipgroup_name}, id: {response.ipgroup.id}"
        )
        return response.ipgroup


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

    @wrap_perform_action_log("huaweicloud.elb-listener")
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
        if not response.listeners or len(response.listeners) == 0:
            log.error(
                f"[actions]-[{self.data.get('type', 'UnknownAction')}] "
                f"No listeners found for id: {redirect_listener_id}, "
                f"name: {name}, protocol: HTTPS, port: {port}"
            )
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
        client.create_l7_policy(request)
