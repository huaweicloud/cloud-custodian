# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from dateutil.parser import parse

from huaweicloudsdkelb.v3 import ListAllMembersRequest

from c7n.filters import ValueFilter, AgeFilter, OPERATORS, Filter
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdklts.v2 import ListTransfersRequest

from c7n.utils import type_schema, local_session
from c7n_huaweicloud.filters.transfer import LtsTransferLogGroupStreamFilter

log = logging.getLogger("custodian.huaweicloud.resources.elb")


class LoadbalancerBackendServerCountFilter(Filter):
    """Allows filtering on ELB backend servers count.

    :example:

    .. code-block:: yaml

        policies:
          - name: delete-no-backend-loadbalancer
            resource: huaweicloud.elb-loadbalancer
            filters:
              - type: backend-server-count
                count: 0
                op: le
            actions:
              - type: delete
    """
    schema = type_schema('backend-server-count',
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


class LoadbalancerPublicipCountFilter(Filter):
    """Allows filtering on ELB public IP counts.

    :example:

    .. code-block:: yaml
        policies:
          - name: delete-loadbalancer-has-eip
            resource: huaweicloud.elb-loadbalancer
            filters:
              - type: publicip-count
                count: 0
                op: gt
            actions:
              - type: delete
    """
    schema = type_schema('publicip-count',
                         op={'enum': list(OPERATORS.keys())},
                         count={'type': 'integer', 'minimum': 0})

    def __call__(self, resource):
        count = self.data.get('count', 0)
        op_name = self.data.get('op', 'gte')
        op = OPERATORS.get(op_name)

        eip_count = len(resource['eips']) if resource['eips'] else 0
        ipv6bandwidth_count = len(resource['ipv6_bandwidth']) \
            if 'ipv6_bandwidth' in resource and resource['ipv6_bandwidth'] else 0
        geip_count = len(resource['global_eips']) \
            if 'global_eips' in resource and resource['global_eips'] else 0

        return op(eip_count + ipv6bandwidth_count + geip_count, count)


class LoadbalancerIsLoggingFilter(Filter):
    """Check if logging enable on ELB.

    :example:

    .. code-block:: yaml

        policies:
          - name: enable-logging-for-loadbalancer
            filters:
              - not:
                - type: is-logging
            actions:
              - type: enable-logging
                log_group_id: "c5c89263-cfce-45cf-ac08-78cf537ba6c5"
                log_topic_id: "328abfed-ab1a-4484-b2c1-031c0d06ea66"
    """
    schema = type_schema('is-logging')

    def __call__(self, resource):
        log_group_id = resource['log_group_id'] if 'log_group_id' in resource else None
        log_topic_id = resource['log_topic_id'] if 'log_topic_id' in resource else None
        if (log_group_id is None or log_group_id.strip() == ""
                or log_topic_id is None or log_topic_id.strip() == ""):
            return False
        return True


class LoadbalancerIsNotLoggingFilter(Filter):
    """Check if logging not enable on ELB.

    :example:

    .. code-block:: yaml

        policies:
          - name: enable-logging-for-loadbalancer
            filters:
              - type: is-not-logging
            actions:
              - type: enable-logging
                log_group_id: "c5c89263-cfce-45cf-ac08-78cf537ba6c5"
                log_topic_id: "328abfed-ab1a-4484-b2c1-031c0d06ea66"
    """
    schema = type_schema('is-not-logging')

    def __call__(self, resource):
        log_group_id = resource['log_group_id'] if 'log_group_id' in resource else None
        log_topic_id = resource['log_topic_id'] if 'log_topic_id' in resource else None
        if (log_group_id is None or log_group_id.strip() == ""
                or log_topic_id is None or log_topic_id.strip() == ""):
            return True
        return False


class LoadbalancerIsLTSLogTransferFilter(Filter):
    """Check if logging transfer on ELB.

    :example:

    .. code-block:: yaml

        policies:
          - name: elb-policy-4
            resource: huaweicloud.elb-loadbalancer
            filters:
              - type: attributes
                key: id
                value: "147476c5-1fa5-4743-b4e0-d52ae39e1142"
              - type: is-logging
              - type: is-lts-log-transfer
    """
    schema = type_schema('is-lts-log-transfer', rinherit=LtsTransferLogGroupStreamFilter.schema)

    def process(self, resources, event=None):
        if len(resources) == 0:
            return resources

        transfer_log_topic_id_set = None
        filter_resources = []
        i = 0
        while i < len(resources):
            resource = resources[i]
            i += 1
            log_group_id = resource['log_group_id'] if 'log_group_id' in resource else None
            log_topic_id = resource['log_topic_id'] if 'log_topic_id' in resource else None
            if (log_group_id is None or log_group_id.strip() == ""
                    or log_topic_id is None or log_topic_id.strip() == ""):
                continue
            if transfer_log_topic_id_set is None:
                transfer_log_topic_id_set = self.get_all_transfer_log_topic_ids()
            if log_topic_id in transfer_log_topic_id_set:
                filter_resources.append(resource)
                continue

        return filter_resources

    def get_all_transfer_log_topic_ids(self):
        # get all log transfer
        lts_client = local_session(self.manager.session_factory).client('lts-transfer')
        lts_request = ListTransfersRequest()
        lts_request.limit = limit = 100
        offset = 0
        log_transfer_stream_ids = []
        while 1:
            lts_request.offset = offset
            lts_response = lts_client.list_transfers(lts_request)
            if lts_response.status_code != 200:
                log.error(lts_response.status_code, lts_response.request_id,
                          lts_response.error_code, lts_response.error_msg)
                raise exceptions.ClientRequestException()

            log_transfers = lts_response.log_transfers
            for log_transfer in log_transfers:
                for log_stream in log_transfer.log_streams:
                    log_transfer_stream_ids.append(log_stream.log_stream_id)

            if len(lts_response.log_transfers) == limit:
                offset += limit
            else:
                break
        return log_transfer_stream_ids


class LoadbalancerIsNotLTSLogTransferFilter(LoadbalancerIsLTSLogTransferFilter):
    """Check if logging transfer on ELB.

    :example:

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
    """
    schema = type_schema('is-not-lts-log-transfer',
                         rinherit=LoadbalancerIsLTSLogTransferFilter.schema)

    def process(self, resources, event=None):
        transfer_resources = super().process(resources, event)
        diff = [resource for resource in resources if resource not in transfer_resources]
        return diff


class ELBAttributesFilter(ValueFilter):
    """Filter by ELB resources attributes

    :example:

    .. code-block:: yaml
        policies:
          - name: list-autoscaling-loadbalancer
            resource: huaweicloud.elb-loadbalancer or huaweicloud.elb-listener
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


class ELBAgeFilter(AgeFilter):
    """Filter elb resources by age.

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
    schema = type_schema('age',
                         op={'$ref': '#/definitions/filters_common/comparison_operators'},
                         days={'type': 'number'},
                         hours={'type': 'number'},
                         minutes={'type': 'number'})

    def get_resource_date(self, resource):
        return parse(resource.get(
            self.date_attribute, "2000-01-01T01:01:01.000Z"))
