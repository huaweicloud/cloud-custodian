# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from c7n.utils import type_schema, local_session
from c7n.filters import Filter
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from huaweicloudsdksmn.v2 import (
    PublishMessageRequest,
    PublishMessageRequestBody,
)

log = logging.getLogger('custodian.huaweicloud.resources.vpcep')


@resources.register('vpcep-ep')
class VpcEndpoint(QueryResourceManager):
    """Huawei Cloud VPC Endpoint Resource Manager

    :example:

    .. code-block:: yaml

        policies:
          - name: list-vpc-endpoints
            resource: huaweicloud.vpcep-ep
    """
    class resource_type(TypeInfo):
        service = 'vpcep-ep'
        enum_spec = ('list_endpoints', 'endpoints', 'offset')
        id = 'id'
        name = 'endpoint_service_name'
        filter_name = 'endpoint_service_name'
        filter_type = 'scalar'
        taggable = True
        tag_resource_type = 'endpoint'

    def augment(self, resources):
        if not resources:
            # Return a fake resource
            return [{"fake-resource": True}]
        return resources


@VpcEndpoint.filter_registry.register('by-service-and-vpc-check')
class VpcEndpointServiceAndVpcFilter(Filter):
    """Check endpoints with a specific service name and verify their VPC IDs

    This filter requires the endpoint_service_name parameter and optionally accepts a vpc_ids list.

    If no endpoint matching the service name is found, it will return a single item list containing
    only the service name.

    If vpc_ids is provided, it will return a list of VPC IDs that do not exist in the endpoints
    that match the service name. If all VPC IDs exist, it returns an empty list.

    :example:

    .. code-block:: yaml

        policies:
          - name: check-vpc-endpoints-for-service
            resource: huaweicloud.vpcep-ep
            filters:
              - type: by-service-and-vpc-check
                endpoint_service_name: "com.huaweicloud.service.test"
                vpc_ids:
                  - vpc-12345678
                  - vpc-87654321
    """
    schema = type_schema(
        'by-service-and-vpc-check',
        endpoint_service_name={'type': 'string'},
        vpc_ids={'type': 'array', 'items': {'type': 'string'}},
        required=['endpoint_service_name']
    )

    def process(self, resources, event=None):
        endpoint_service_name = self.data.get('endpoint_service_name')
        vpc_ids = self.data.get('vpc_ids', [])

        # Validate if endpoint_service_name is valid
        if not endpoint_service_name:
            self.log.error(
                "endpoint_service_name is a required parameter and cannot be empty")
            return []

        # Find endpoints that match the service name
        matching_endpoints = [
            r for r in resources
            if r.get('endpoint_service_name') == endpoint_service_name
        ]

        # If no matching endpoints found, return a list containing only the service name
        if not matching_endpoints:
            self.log.info(
                f"No endpoints found with service name {endpoint_service_name}")
            return [{"endpoint_service_name": endpoint_service_name}]

        # If vpc_ids not provided, return empty list (no need to check VPCs)
        if not vpc_ids:
            return []

        # Get all vpc_ids that exist in matching endpoints
        existing_vpc_ids = {r.get('vpc_id')
                            for r in matching_endpoints if r.get('vpc_id')}

        # Find vpc_ids that don't exist in matching endpoints
        missing_vpc_ids = [
            vpc_id for vpc_id in vpc_ids if vpc_id not in existing_vpc_ids]

        # If there are missing vpc_ids, return result with missing VPC IDs
        if missing_vpc_ids:
            self.log.info(
                (f"Missing VPC IDs found in service {endpoint_service_name}: "
                 f"{', '.join(missing_vpc_ids)}")
            )
            return [{"endpoint_service_name": endpoint_service_name, "vpc_ids": missing_vpc_ids}]

        # If all vpc_ids exist, return empty list (no issues found)
        return []


@VpcEndpoint.action_registry.register('eps-check-ep-msg')
class VpcEndpointSendMsg(HuaweiCloudBaseAction):
    """VPC Endpoint message notification action.

    Used to send notification messages about VPC endpoint configuration, including
    endpoint service name and VPC ID information.

    :example:

    .. code-block:: yaml

        policies:
          - name: vpc-endpoint-notification
            resource: huaweicloud.vpcep-ep
            filters:
              - type: by-service-and-vpc-check
                endpoint_service_name: "com.huaweicloud.service.test"
            actions:
              - type: eps-check-ep-msg
                topic_urn_list:
                  - "urn:smn:region:account-id:topic-name"
                message: "alert: xxxxx"
    """

    schema = type_schema(
        'eps-check-ep-msg',
        required=['topic_urn_list'],
        topic_urn_list={'type': 'array', 'items': {'type': 'string'}},
        message={'type': 'string'}
    )

    def process(self, resources):
        """Process message sending logic"""
        if not resources:
            return resources

        topic_urn_list = self.data.get('topic_urn_list', [])
        user_message = self.data.get(
            'message', 'Notification: VPC Endpoint Configuration Check')

        for resource in resources:
            self.perform_action(resource, topic_urn_list, user_message)

        return resources

    def perform_action(self, resource, topic_urn_list=None, user_message=None):
        """Execute message sending operation for a single resource"""
        if topic_urn_list is None:
            topic_urn_list = self.data.get('topic_urn_list', [])

        if user_message is None:
            user_message = self.data.get(
                'message', 'Notification: VPC Endpoint Configuration Check')

        endpoint_service_name = resource.get('endpoint_service_name', '')

        vpc_ids = resource.get('vpc_ids', [])
        if vpc_ids:
            vpc_id_str = ", ".join(vpc_ids)
            # Build message content for multiple VPC IDs
            message = (
                f"{user_message} Please check whether VPC ({vpc_id_str}) "
                "has VPC endpoints configured, "
                f"and whether the endpoint service name is {endpoint_service_name}."
            )
        else:
            message = (
                f"{user_message} Please check whether VPC "
                "has a VPC endpoint configured, "
                f"and whether the endpoint service name is {endpoint_service_name}."
            )

        subject = "VPC Endpoint Configuration Notification"
        body = PublishMessageRequestBody(subject=subject, message=message)

        results = []
        for topic_urn in topic_urn_list:
            publish_message_request = PublishMessageRequest(
                topic_urn=topic_urn, body=body
            )
            log.info(f"Sending message, request: {publish_message_request}")

            try:
                client = local_session(
                    self.manager.session_factory).client('smn')
                publish_message_response = client.publish_message(
                    publish_message_request)
                log.info(
                    f"Message sent successfully, response: {publish_message_response}")
                results.append({
                    'status': 'success',
                    'topic_urn': topic_urn,
                    'message_id': getattr(publish_message_response, 'message_id', None)
                })
            except Exception as e:
                log.error(f"Failed to send message: {e}")
                results.append({
                    'status': 'error',
                    'topic_urn': topic_urn,
                    'error': str(e)
                })

        return results
