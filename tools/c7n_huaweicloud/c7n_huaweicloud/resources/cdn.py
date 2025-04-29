# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from c7n.filters.core import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

from huaweicloudsdkcdn.v2.model import (
    DeleteDomainRequest, 
    EnableDomainRequest, 
    DisableDomainRequest
)
from huaweicloudsdkcore.exceptions import exceptions

log = logging.getLogger('custodian.huaweicloud.cdn')


@resources.register('cdn-domain')
class CdnDomain(QueryResourceManager):
    """Huawei Cloud Content Delivery Network (CDN) Domain Resource

    This resource allows querying and managing Huawei Cloud CDN domains, supporting filtering by domain status, business type, etc.,
    and performing enable, disable, and delete operations.

    :example:

    .. code-block:: yaml

        policies:
          - name: offline-cdn-domains
            resource: huaweicloud.cdn-domain
            filters:
              - type: value
                key: domain_status
                value: offline
          
          - name: find-download-cdn-domains
            resource: huaweicloud.cdn-domain
            filters:
              - type: value
                key: business_type
                value: download
    """

    class resource_type(TypeInfo):
        """CDN domain resource type definition"""
        service = 'cdn'  # Specify the corresponding Huawei Cloud service name
        enum_spec = ('list_domains', 'domains', "cdn")  # API info for enumerating resources: (operation name, result list field, pagination type)
        id = 'id'  # Resource unique identifier field name
        name = 'domain_name'  # Resource name field name
        date = 'create_time'  # Resource creation time field name
        tag_resource_type = 'cdn'  # Resource type for tag queries

    def augment(self, resources):
        """Enhance resource data, add extra information

        Process CDN domain resource data to ensure consistent format and add necessary tag info
        
        Args:
            resources: original resource list
            
        Returns:
            list: enhanced resource list
        """
        if not resources:
            return []
            
        # Convert tags field to a dict for tag filtering
        for resource in resources:
            if 'tags' in resource:
                tags_map = {}
                for tag in resource['tags']:
                    if isinstance(tag, dict) and 'key' in tag and 'value' in tag:
                        tags_map[tag['key']] = tag['value']
                resource['tags'] = tags_map
                
        return resources


@CdnDomain.action_registry.register('delete')
class DeleteCdnDomain(HuaweiCloudBaseAction):
    """Delete CDN domain

    This operation will permanently delete the CDN domain. Use with caution.

    :example:

    .. code-block:: yaml

        policies:
          - name: delete-unused-cdn-domains
            resource: huaweicloud.cdn-domain
            filters:
              - type: value
                key: domain_status
                value: offline
              - type: value
                key: modify_time
                value_type: age
                value: 90
                op: greater-than
            actions:
              - delete
    """
    
    schema = type_schema(
        'delete',
        enterprise_project_id={'type': 'string'}
    )
    
    def perform_action(self, resource):
        """Perform delete operation

        Args:
            resource: resource info dict
        """
        client = self.manager.get_client()
        domain_id = resource['id']
        
        log.info(f"Preparing to delete CDN domain: id={domain_id}, domain_name={resource.get('domain_name')}")
        
        # Build delete domain request
        request = DeleteDomainRequest()
        request.domain_id = domain_id
        
        # If enterprise project ID is needed
        if self.data.get('enterprise_project_id'):
            request.enterprise_project_id = self.data.get('enterprise_project_id')
        
        # Perform disable operation
        try:
            client.disable_domain(request)
            log.info(f"CDN domain disabled successfully: id={domain_id}")
        except exceptions.ClientRequestException as e:
            log.error(
                f"CDN domain disable failed: id={domain_id}, RequestId={e.request_id}, "
                f"StatusCode={e.status_code}, ErrorCode={e.error_code}, "
                f"ErrorMsg={e.error_msg}"
            )
            raise

        # Perform delete operation
        try:
            client.delete_domain(request)
            log.info(f"CDN domain deleted successfully: id={domain_id}")
        except exceptions.ClientRequestException as e:
            log.error(
                f"CDN domain deletion failed: id={domain_id}, RequestId={e.request_id}, "
                f"StatusCode={e.status_code}, ErrorCode={e.error_code}, "
                f"ErrorMsg={e.error_msg}"
            )
            raise
        

@CdnDomain.action_registry.register('enable')
class EnableCdnDomain(HuaweiCloudBaseAction):
    """Enable CDN domain

    Restore a disabled CDN domain to enabled status.

    :example:

    .. code-block:: yaml

        policies:
          - name: enable-cdn-domains
            resource: huaweicloud.cdn-domain
            filters:
              - type: value
                key: domain_status
                value: offline
            actions:
              - enable
    """
    
    schema = type_schema(
        'enable',
        enterprise_project_id={'type': 'string'}
    )
    
    def perform_action(self, resource):
        """Perform enable operation

        Args:
            resource: resource info dict
        """
        client = self.manager.get_client()
        domain_id = resource['id']
        
        log.info(f"Preparing to enable CDN domain: id={domain_id}, domain_name={resource.get('domain_name')}")
        
        # Build enable domain request
        request = EnableDomainRequest()
        request.domain_id = domain_id
        
        # If enterprise project ID is needed
        if self.data.get('enterprise_project_id'):
            request.enterprise_project_id = self.data.get('enterprise_project_id')
        
        # Perform enable operation
        try:
            client.enable_domain(request)
            log.info(f"CDN domain enabled successfully: id={domain_id}")
        except exceptions.ClientRequestException as e:
            log.error(
                f"CDN domain enable failed: id={domain_id}, RequestId={e.request_id}, "
                f"StatusCode={e.status_code}, ErrorCode={e.error_code}, "
                f"ErrorMsg={e.error_msg}"
            )
            raise


@CdnDomain.action_registry.register('disable')
class DisableCdnDomain(HuaweiCloudBaseAction):
    """Disable CDN domain

    Set the CDN domain to disabled status and suspend its service.

    :example:

    .. code-block:: yaml

        policies:
          - name: disable-inactive-cdn-domains
            resource: huaweicloud.cdn-domain
            filters:
              - type: value
                key: domain_status
                value: online
              - type: value
                key: cname
                value: ""
                op: eq
            actions:
              - disable
    """
    
    schema = type_schema(
        'disable',
        enterprise_project_id={'type': 'string'}
    )
    
    def perform_action(self, resource):
        """Perform disable operation

        Args:
            resource: resource info dict
        """
        client = self.manager.get_client()
        domain_id = resource['id']
        
        log.info(f"Preparing to disable CDN domain: id={domain_id}, domain_name={resource.get('domain_name')}")
        
        # Build disable domain request
        request = DisableDomainRequest()
        request.domain_id = domain_id
        
        # If enterprise project ID is needed
        if self.data.get('enterprise_project_id'):
            request.enterprise_project_id = self.data.get('enterprise_project_id')
        
        # Perform disable operation
        try:
            client.disable_domain(request)
            log.info(f"CDN domain disabled successfully: id={domain_id}")
        except exceptions.ClientRequestException as e:
            log.error(
                f"CDN domain disable failed: id={domain_id}, RequestId={e.request_id}, "
                f"StatusCode={e.status_code}, ErrorCode={e.error_code}, "
                f"ErrorMsg={e.error_msg}"
            )
            raise
