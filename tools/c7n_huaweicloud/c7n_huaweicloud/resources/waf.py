# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from c7n.utils import type_schema
from c7n.filters.core import ValueFilter

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkwaf.v1.model.update_lts_info_config_request import UpdateLtsInfoConfigRequest
from huaweicloudsdkwaf.v1.model.update_lts_info_config_request_body import UpdateLtsInfoConfigRequestBody
from huaweicloudsdkwaf.v1.model.lts_id_info import LtsIdInfo

from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

log = logging.getLogger('custodian.huaweicloud.resources.waf')


@resources.register('waf-policy')
class WafPolicy(QueryResourceManager):
    """Huawei Cloud Web Application Firewall (WAF) Policy Resource
    """

    class resource_type(TypeInfo):
        """Define WAF policy resource metadata and type information"""
        service = 'waf-policy'  # Specify the corresponding Huawei Cloud service name
        # Specify the API operation, result list key name, and pagination parameters for enumerating resources
        # 'list_policy' is the API method name
        # 'items' is the field name containing the instance list in the response
        # None indicates no pagination is used
        enum_spec = ('list_policy', 'items', "waf")
        id = 'id'  # Specify the resource unique identifier field name
        name = 'name'  # Specify the resource name field
        date = 'timestamp'  # Specify the resource creation time field
        arn_type = 'waf-policy'  # Resource ARN type
        tag_resource_type = None # Tag not supported


@resources.register('waf-log-config')
class WafLogConfig(QueryResourceManager):
    """Huawei Cloud Web Application Firewall (WAF) Log Configuration Resource
    """

    class resource_type(TypeInfo):
        """Define WAF log configuration resource metadata and type information"""
        service = 'waf-log-config'  # Specify the corresponding Huawei Cloud service name
        # Specify the API operation, result list key name, and pagination parameters for enumerating resources
        # 'show_lts_info_config' is the API method name
        # 'lts_info' is the field name containing the instance info in the response
        # None indicates no pagination is used
        enum_spec = ('show_lts_info_config', "[ @ ]", None)
        id = 'id'  # Specify the resource unique identifier field name
        name = 'id' # Specify the resource name field
        arn_type = 'waf-log-config'  # Resource ARN type
        tag_resource_type = None # Tag not supported


@WafLogConfig.filter_registry.register('enabled')
class LogEnabledFilter(ValueFilter):
    """Filter by WAF log configuration enabled status

    :example:

    .. code-block:: yaml

        policies:
          - name: waf-logs-disabled
            resource: huaweicloud.waf-log-config
            filters:
              - type: enabled
                value: false  # Not enabled
    """
    schema = type_schema('enabled', rinherit=ValueFilter.schema)
    
    def __init__(self, data, manager=None):
        """Initialize the filter

        :param data: Filter configuration data
        :param manager: Resource manager
        """
        super(LogEnabledFilter, self).__init__(data, manager)
        self.data['key'] = 'enabled'


@WafLogConfig.action_registry.register('update')
class UpdateLogConfig(HuaweiCloudBaseAction):
    """Update WAF log configuration

    This operation allows enabling/disabling WAF log configuration and setting log group and log stream information.

    :example:

    .. code-block:: yaml

        policies:
          - name: enable-waf-logs
            resource: huaweicloud.waf-log-config
            filters:
              - type: enabled
                value: false  # Not enabled
            actions:
              - type: update
                enabled: true  # Enabled
                lts_id_info:
                  lts_group_id: "4bcff74d-f649-41c8-8325-1b0a264ff683"
                  lts_access_stream_id: "0a7ef713-cc3e-418d-abda-85df04db1a3c"
                  lts_attack_stream_id: "f4fa07f6-277b-4e4a-a257-26508ece81e6"
    """
    schema = type_schema(
        'update',
        enabled={'type': 'boolean'},
        lts_id_info={
            'type': 'object',
            'properties': {
                'lts_group_id': {'type': 'string'},
                'lts_access_stream_id': {'type': 'string'},
                'lts_attack_stream_id': {'type': 'string'}
            },
            'additionalProperties': False
        }
    )

    def perform_action(self, resource):
        """Perform action on a single resource

        :param resource: Resource to perform action on
        :return: API response
        """
        client = self.manager.get_client()
        resource_id = resource['id']

        # Construct log information object
        lts_id_info_data = self.data.get('lts_id_info')
        lts_id_info = None
        
        if lts_id_info_data:
            lts_id_info = LtsIdInfo(
                lts_group_id=lts_id_info_data.get('lts_group_id'),
                lts_access_stream_id=lts_id_info_data.get('lts_access_stream_id'),
                lts_attack_stream_id=lts_id_info_data.get('lts_attack_stream_id')
            )
        
        # Construct request body
        request_body = UpdateLtsInfoConfigRequestBody(
            enabled=self.data.get('enabled'),
            lts_id_info=lts_id_info
        )
        
        # Construct request
        request = UpdateLtsInfoConfigRequest(
            ltsconfig_id=resource_id,
            body=request_body
        )
        
        # Get enterprise project ID from resource data
        if 'enterprise_project_id' in resource:
            request.enterprise_project_id = resource['enterprise_project_id']
            
        try:
            # Call API to update log configuration
            response = client.update_lts_info_config(request)
            log.info(f"Updated WAF log configuration: {resource_id}")
            return response
        except exceptions.ClientRequestException as e:
            log.error(f"Failed to update WAF log configuration: {e.status_code}, {e.request_id}, {e.error_code}, {e.error_msg}")
            raise
