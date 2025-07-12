# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from functools import wraps
import logging

from dateutil.parser import parse

from huaweicloudsdkelb.v3 import ListAllMembersRequest, ListL7PoliciesRequest, ShowListenerRequest


from c7n.filters import ValueFilter, AgeFilter, OPERATORS, Filter
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdklts.v2 import ListTransfersRequest

from c7n.utils import type_schema, local_session
from c7n_huaweicloud.filters.transfer import LtsTransferLogGroupStreamFilter

log = logging.getLogger("custodian.huaweicloud.resources.elb")


def wrap_filter_log(resource_name, raise_exception=True):
    """ Decorator to wrap filter methods with logging for ELB resources."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions.SdkException as e:
                log.error(
                    f"[filters]-[{args[0].data.get('type', 'UnknownFilter')}] "
                    f"Failed to filter resource[{resource_name}]. Exception: {e}"
                )
                if raise_exception:
                    raise
        return wrapper
    return decorator


class LoadbalancerBackendServerCountFilter(Filter):
    """Allows filtering on ELB backend servers count.

    :example:

    .. code-block:: yaml

        policies:
          - name: check-no-backend-loadbalancer
            resource: huaweicloud.elb-loadbalancer
            filters:
              - type: backend-server-count
                count: 0
                op: le
    """

    schema = type_schema(
        "backend-server-count",
        op={"enum": list(OPERATORS.keys()), "default": "gte"},
        count={"type": "integer", "minimum": 0, "default": 0},
    )

    @wrap_filter_log("huaweicloud.elb-loadbalancer")
    def __call__(self, resource):
        count = self.data.get("count")
        op_name = self.data.get("op")
        op = OPERATORS.get(op_name)

        client = self.manager.get_client()
        backend_count = 0
        request = ListAllMembersRequest(
            loadbalancer_id=[resource["id"]],
            enterprise_project_id=["all_granted_eps"],
        )
        members_response = client.list_all_members(request)
        log.debug(
            f"[filter]-[{self.data.get('type', 'UnknownFilter')}] "
            "Query the service:[ELB:list_all_members] is success."
        )
        backend_count = len(members_response.members)
        return op(backend_count, count)


class LoadbalancerPublicipCountFilter(Filter):
    """Allows filtering on ELB public IP counts. Includes EIP, IPv6 bandwidth, and global EIP.

    :example:

    .. code-block:: yaml
        policies:
          - name: check-loadbalancer-has-eip
            resource: huaweicloud.elb-loadbalancer
            filters:
              - type: publicip-count
                count: 0
                op: gt
    """

    schema = type_schema(
        "publicip-count",
        op={"enum": list(OPERATORS.keys()), "default": "gte"},
        count={"type": "integer", "minimum": 0, "default": 0},
    )

    def __call__(self, resource):
        count = self.data.get("count")
        op_name = self.data.get("op")
        op = OPERATORS.get(op_name)

        eip_count = len(resource["eips"]) if resource["eips"] else 0
        ipv6bandwidth_count = (
            len(resource["ipv6_bandwidth"])
            if "ipv6_bandwidth" in resource and resource["ipv6_bandwidth"]
            else 0
        )
        geip_count = (
            len(resource["global_eips"])
            if "global_eips" in resource and resource["global_eips"]
            else 0
        )

        return op(eip_count + ipv6bandwidth_count + geip_count, count)


class LoadbalancerIsLoggingFilter(Filter):
    """Allows filtering on checking if logging is enabled on ELB.

    :example:

    .. code-block:: yaml

        policies:
          - name: is-logging-on-loadbalancer
            filters:
              - type: is-logging
    """

    schema = type_schema("is-logging")

    def __call__(self, resource):
        log_group_id = resource["log_group_id"] if "log_group_id" in resource else None
        log_topic_id = resource["log_topic_id"] if "log_topic_id" in resource else None
        if (
            log_group_id is None
            or log_group_id.strip() == ""
            or log_topic_id is None
            or log_topic_id.strip() == ""
        ):
            return False
        return True


class LoadbalancerIsNotLoggingFilter(LoadbalancerIsLoggingFilter):
    """Allows filtering on checking if logging is not enabled on ELB.

    :example:

    .. code-block:: yaml

        policies:
          - name: enable-logging-for-loadbalancer
            filters:
              - type: is-not-logging
    """

    schema = type_schema("is-not-logging")

    def __call__(self, resource):
        return not super().__call__(resource)


class LoadbalancerIsLTSLogTransferFilter(Filter):
    """
    Filters ELB resources to check if their logging is transferred to OBS.

    This filter returns ELB resources that have logging enabled and whose logging is configured
    for transfer to OBS.

    :example:

    .. code-block:: yaml

        policies:
          - name: filter-elb-has-log-transfer
            resource: huaweicloud.elb-loadbalancer
            filters:
              - type: is-logging
              - type: is-lts-log-transfer
    """

    schema = type_schema("is-lts-log-transfer", rinherit=LtsTransferLogGroupStreamFilter.schema)

    @wrap_filter_log("huaweicloud.elb-loadbalancer")
    def process(self, resources, event=None):
        if len(resources) == 0:
            return resources

        transfer_log_topic_id_set = None
        filter_resources = []
        for resource in resources:
            log_group_id = resource["log_group_id"] if "log_group_id" in resource else None
            log_topic_id = resource["log_topic_id"] if "log_topic_id" in resource else None
            if (
                log_group_id is None
                or log_group_id.strip() == ""
                or log_topic_id is None
                or log_topic_id.strip() == ""
            ):
                continue
            if transfer_log_topic_id_set is None:
                transfer_log_topic_id_set = self.get_all_transfer_log_topic_ids()
            if log_topic_id in transfer_log_topic_id_set:
                filter_resources.append(resource)

        return filter_resources

    def get_all_transfer_log_topic_ids(self):
        # get all log transfer
        lts_client = local_session(self.manager.session_factory).client("lts-transfer")
        lts_request = ListTransfersRequest()
        lts_response = lts_client.list_transfers(lts_request)
        log.debug(
            f"[filter]-[{self.data.get('type', 'UnknownFilter')}] "
            "Query the service:[LTS:list_transfers] is success."
        )
        log_transfers = lts_response.log_transfers
        log_transfer_stream_ids = []
        for log_transfer in log_transfers:
            for log_stream in log_transfer.log_streams:
                log_transfer_stream_ids.append(log_stream.log_stream_id)

        return log_transfer_stream_ids


class LoadbalancerIsNotLTSLogTransferFilter(LoadbalancerIsLTSLogTransferFilter):
    """Filters ELB resources to check if their logging is not transferred to OBS.

    This filter returns ELB resources that have logging enabled and whose logging is not configured
    for transfer to OBS.

    :example:

    .. code-block:: yaml

        policies:
          - name: filter-elb-not-lts-log-transfer
            resource: huaweicloud.elb-loadbalancer
            filters:
              - type: is-logging
              - type: is-not-lts-log-transfer
    """

    schema = type_schema(
        "is-not-lts-log-transfer", rinherit=LoadbalancerIsLTSLogTransferFilter.schema
    )

    @wrap_filter_log("huaweicloud.elb-loadbalancer")
    def process(self, resources, event=None):
        transfer_resources = super().process(resources, event)
        diff = [resource for resource in resources if resource not in transfer_resources]
        return diff


class ListenerRedirectListenerFilter(Filter):
    """Allows filtering on checking if https listener has been redirected to https listener.
    Note: This filter only works for HTTP listeners.

    :example:

    .. code-block:: yaml

        policies:
          - name: has-redirect-to-https-listener
            resource: huaweicloud.elb-listener
            filters:
              - type: attributes
                key: protocol
                value: HTTP
              - not:
                - type: is-redirect-to-https-listener
    """

    schema = type_schema(
        "is-redirect-to-https-listener",
        id={"type": "string"},
        name={"type": "string"},
        port={"type": "number", "minimum": 0},
    )

    @wrap_filter_log("huaweicloud.elb-listener")
    def __call__(self, resource):
        if resource["protocol"] != "HTTP":
            # This filter only applies to HTTP listeners
            return False
        id = self.data.get("id", None)
        name = self.data.get("name", None)
        port = self.data.get("port", None)
        listener_id = resource["id"]
        # Get the policy information for the listener
        client = self.manager.get_client()
        request = ListL7PoliciesRequest(
            enterprise_project_id=["all_granted_eps"],
            listener_id=[listener_id],
            action=["REDIRECT_TO_LISTENER"],
            redirect_listener_id=[id] if id else None,
        )
        response = client.list_l7_policies(request)
        log.debug(
            f"[filter]-[{self.data.get('type', 'UnknownFilter')}] "
            "Query the service:[ELB:list_l7_policies] is success."
        )
        for policy in response.l7policies:
            if policy.redirect_listener_id is None:
                continue
            # Get the listener information for the redirect listener
            request = ShowListenerRequest(listener_id=policy.redirect_listener_id)
            response = client.show_listener(request)
            log.debug(
                f"[filter]-[{self.data.get('type', 'UnknownFilter')}] "
                "query the service:[ELB:show_listener] is success."
            )

            listener = response.listener
            if (
                (listener.protocol != 'HTTPS')
                or (name and listener.name != name)
                or (port and listener.protocol_port != port)
            ):
                continue
            return True
        return False


class ELBAttributesFilter(ValueFilter):
    """
    Allows filtering on checking by ELB resources attributes.
    Supports both `huaweicloud.elb-loadbalancer` and `huaweicloud.elb-listener` resources.
    Note: The set of available attributes may differ between
    `huaweicloud.elb-loadbalancer` and `huaweicloud.elb-listener` resources;
    ensure you reference attributes supported by the specific resource type you are targeting.

    :example:
    'description', 'status', or nested keys like 'autoscaling.enable' or 'tags.key'.

    To filter on nested attributes, use dot notation in the 'key' field
    (e.g., 'autoscaling.enable').
    The filter supports all standard value filter operations.

    :example:

    .. code-block:: yaml
        policies:
          - name: list-autoscaling-loadbalancer
            resource: huaweicloud.elb-loadbalancer
            filters:
              - type: attributes
                key: autoscaling.enable
                value: true

    """

    annotate = False  # no annotation from value filter
    schema = type_schema("attributes", rinherit=ValueFilter.schema)
    schema_alias = False

    def process(self, resources, event=None):
        return super().process(resources, event)

    def __call__(self, r):
        return super().__call__(r)


class ELBAgeFilter(AgeFilter):
    """
    Allows filtering ELB resources by age.

    Supports both `huaweicloud.elb-loadbalancer` and `huaweicloud.elb-listener` resources.

    :example:

    .. code-block:: yaml

        policies:
          - name: list-latest-loadbalancer
            resource: huaweicloud.elb-loadbalancer or huaweicloud.elb-listener
            filters:
              - type: age
                days: 7
                op: le
    """

    date_attribute = "created_at"
    schema = type_schema(
        "age",
        op={"$ref": "#/definitions/filters_common/comparison_operators"},
        days={"type": "number"},
        hours={"type": "number"},
        minutes={"type": "number"},
    )

    def get_resource_date(self, i):
        return parse(i.get(self.date_attribute, "2000-01-01T01:01:01.000Z"))
