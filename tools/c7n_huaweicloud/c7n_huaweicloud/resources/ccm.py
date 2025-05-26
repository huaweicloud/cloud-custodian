# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from c7n.utils import type_schema, local_session
from c7n.filters import Filter
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkccm.v1.model import (
    DisableCertificateAuthorityRequest,
    ListCaTagsRequest,
    ListCertTagsRequest,
)

log = logging.getLogger('custodian.huaweicloud.resources.ccm')


@resources.register('ccm-private-ca')
class CertificateAuthority(QueryResourceManager):
    """Huawei Cloud Certificate Authority Resource Manager

    :example:
    Define a simple policy to get all certificate authorities:

    .. code-block:: yaml

        policies:
          - name: list-certificate-authorities
            resource: huaweicloud.ccm-private-ca
    """
    class resource_type(TypeInfo):
        service = 'ccm-private-ca'
        enum_spec = ('list_certificate_authority',
                     'certificate_authorities', 'offset')
        id = 'ca_id'
        name = 'distinguished_name.common_name'
        filter_name = 'name'
        filter_type = 'scalar'
        taggable = True
        tag_resource_type = 'private-certificate-authorities'

    def augment(self, resources):
        """Process resource information, ensure id field is correctly set"""
        for r in resources:
            if 'id' not in r and 'ca_id' in r:
                r['id'] = r['ca_id']

        # Query tags for each CA and add them to the resource properties
        session = local_session(self.session_factory)
        client = session.client('ccm-private-ca')

        for resource in resources:
            try:
                # Get CA ID
                ca_id = resource.get('ca_id')
                if not ca_id:
                    continue

                # Use ListCaTagsRequest to query tags for this CA
                request = ListCaTagsRequest()
                request.ca_id = ca_id

                try:
                    # Call the API to get tags
                    response = client.list_ca_tags(request)

                    # Check if tags are available in the response
                    if hasattr(response, 'tags') and response.tags is not None:
                        # Convert response tags to standard dict format
                        tags = []
                        for tag in response.tags:
                            if hasattr(tag, 'key') and hasattr(tag, 'value'):
                                tags.append(
                                    {'key': tag.key, 'value': tag.value})
                        resource['tags'] = tags
                    else:
                        resource['tags'] = []
                except exceptions.ClientRequestException as e:
                    log.warning(
                        f"Failed to retrieve tags for CA {ca_id}: {e.error_msg}")
                    resource['tags'] = []
            except Exception as e:
                log.error(
                    f"Error retrieving tags for CA {resource.get('ca_id')}: {str(e)}")
                resource['tags'] = []

        return resources


@CertificateAuthority.filter_registry.register('status')
class CertificateAuthorityStatusFilter(Filter):
    """Filter certificate authorities by CA status

    Statuses include: ACTIVED (activated), DISABLED (disabled), PENDING (pending activation),
    DELETED (scheduled for deletion), EXPIRED (expired)

    :example:

    .. code-block:: yaml

        policies:
          - name: find-disabled-cas
            resource: huaweicloud.ccm-private-ca
            filters:
              - type: status
                value: DISABLED
    """
    schema = type_schema(
        'status',
        value={'type': 'string'}
    )

    def process(self, resources, event=None):
        status_value = self.data.get('value')
        if not status_value:
            return resources

        results = []
        for resource in resources:
            if resource.get('status') == status_value:
                results.append(resource)

        return results


@CertificateAuthority.filter_registry.register('issuer-name')
class CertificateAuthorityIssuerNameFilter(Filter):
    """Filter certificate authorities by issuer_name

    Supports finding resources with specific issuer_name
    or with empty/null issuer_name using value: null

    :example:

    .. code-block:: yaml
        # Find CAs with empty/null issuer_name
        policies:
          - name: find-cas-with-empty-issuer
            resource: huaweicloud.ccm-private-ca
            filters:
              - type: issuer-name
                value: null
    """
    schema = type_schema(
        'issuer-name',
        value={'type': ['string', 'null']}
    )

    def process(self, resources, event=None):
        issuer_name = self.data.get('value')

        results = []
        for resource in resources:
            resource_issuer = resource.get('issuer_name')

            # Handle the case where we're looking for empty/null issuer_name
            if issuer_name is None or issuer_name == 'null':
                # Check for None or empty string or whitespace only string
                is_empty = not resource_issuer
                is_blank = isinstance(
                    resource_issuer, str) and not resource_issuer.strip()
                if is_empty or is_blank:
                    results.append(resource)
            # Otherwise do an exact match
            elif resource_issuer == issuer_name:
                results.append(resource)

        return results


@CertificateAuthority.filter_registry.register('crl-obs-bucket')
class CertificateAuthorityCrlObsBucketFilter(Filter):
    """Filter certificate authorities by OBS bucket BPA configuration

    This filter filters certificate authorities based on the OBS bucket BPA configuration
    of the bucket specified in the CRL configuration.

    The BPA (Block Public Access) configuration consists of four boolean properties:
    - blockPublicAcls: Blocks public ACLs for the bucket
    - ignorePublicAcls: Ignores public ACLs for the bucket
    - blockPublicPolicy: Blocks public policies for the bucket
    - restrictPublicBuckets: Restricts public access to the bucket

    By default (with no parameters), this filter will return resources where ANY of the
    four BPA properties are set to false (not secure).

    You can specify one or more BPA properties to filter on. When multiple properties are
    specified, resources will be returned if ANY of the specified properties are false.

    :example:

    .. code-block:: yaml

        # Example 1: Filter CAs with any BPA property set to false (default behavior)
        policies:
          - name: find-cas-with-insecure-bpa
            resource: huaweicloud.ccm-private-ca
            filters:
              - type: crl-obs-bucket

        # Example 2: Filter CAs where any of blockPublicAcls,
        # ignorePublicAcls, or blockPublicPolicy is false
        policies:
          - name: find-cas-with-multiple-bpa-issues
            resource: huaweicloud.ccm-private-ca
            filters:
              - type: crl-obs-bucket
                bpa_properties:
                  - blockPublicAcls
                  - ignorePublicAcls
                  - blockPublicPolicy
    """
    schema = type_schema(
        'crl-obs-bucket',
        bucket_name={'type': 'string'},
        bpa_properties={
            'type': 'array',
            'items': {
                'type': 'string',
                'enum': [
                    'blockPublicAcls',
                    'ignorePublicAcls',
                    'blockPublicPolicy',
                    'restrictPublicBuckets'
                ]
            }
        }
    )

    def process(self, resources, event=None):
        session = local_session(self.manager.session_factory)
        obs_client = session.client('obs')

        bucket_name = self.data.get('bucket_name')
        bpa_properties = self.data.get('bpa_properties', [])

        # If no properties specified, check all four properties
        check_all = not bpa_properties

        results = []

        for resource in resources:
            # Check if CRL configuration exists
            crl_config = resource.get('crl_configuration', {})
            if not crl_config:
                continue

            # Get OBS bucket name
            obs_bucket_name = crl_config.get('obs_bucket_name')
            if not obs_bucket_name:
                continue

            # Filter by bucket name if specified
            if bucket_name and obs_bucket_name != bucket_name:
                continue

            # Get the bucket's BPA configuration
            try:
                resp = obs_client.getBucketPublicAccessBlock(obs_bucket_name)

                # Check response status
                if resp.status < 300 and hasattr(resp, 'body'):
                    # Set the BPA configuration on the resource for reference
                    resource['obs_bpa_config'] = {
                        'blockPublicAcls': getattr(resp.body, 'blockPublicAcls', False),
                        'ignorePublicAcls': getattr(resp.body, 'ignorePublicAcls', False),
                        'blockPublicPolicy': getattr(resp.body, 'blockPublicPolicy', False),
                        'restrictPublicBuckets': getattr(resp.body, 'restrictPublicBuckets', False)
                    }

                    # Check if any of the specified properties (or all if none specified) are false
                    should_include = False

                    if check_all:
                        # Check if any of the four properties are false
                        if (not resource['obs_bpa_config']['blockPublicAcls'] or
                            not resource['obs_bpa_config']['ignorePublicAcls'] or
                            not resource['obs_bpa_config']['blockPublicPolicy'] or
                                not resource['obs_bpa_config']['restrictPublicBuckets']):
                            should_include = True
                    else:
                        # Check only the specified properties
                        for prop in bpa_properties:
                            if not resource['obs_bpa_config'].get(prop, False):
                                should_include = True
                                break

                    if should_include:
                        results.append(resource)

            except exceptions.ClientRequestException as e:
                # Log the error but don't include the resource in results
                log.error(
                    f"Failed to get bucket PublicAccessBlock for {obs_bucket_name}: {e.error_msg}")
                continue

        return results


@CertificateAuthority.filter_registry.register('key-algorithm')
class CertificateAuthorityKeyAlgorithmFilter(Filter):
    """Filter certificate authorities by key algorithm

    This filter allows filtering CAs by key algorithm type,
    such as RSA2048, RSA4096, EC256, EC384, etc.

    :example:

    .. code-block:: yaml

        policies:
          - name: find-cas-with-specific-key-algorithm
            resource: huaweicloud.ccm-private-ca
            filters:
              - type: key-algorithm
                algorithms:
                  - RSA2048
                  - RSA4096
    """
    schema = type_schema(
        'key-algorithm',
        algorithms={'type': 'array', 'items': {'type': 'string'}}
    )

    def process(self, resources, event=None):
        algorithms = self.data.get('algorithms', [])
        if not algorithms:
            return resources

        results = []
        for resource in resources:
            key_algorithm = resource.get('key_algorithm')
            if key_algorithm in algorithms:
                results.append(resource)

        return results


@CertificateAuthority.filter_registry.register('signature-algorithm')
class CertificateAuthoritySignatureAlgorithmFilter(Filter):
    """Filter certificate authorities by signature algorithm

    This filter allows filtering CAs by signature algorithm type,
    such as SHA256, SHA384, SHA512, etc.

    :example:

    .. code-block:: yaml

        policies:
          - name: find-cas-with-specific-signature-algorithm
            resource: huaweicloud.ccm-private-ca
            filters:
              - type: signature-algorithm
                algorithms:
                  - SHA256
                  - SHA384
    """
    schema = type_schema(
        'signature-algorithm',
        algorithms={'type': 'array', 'items': {'type': 'string'}}
    )

    def process(self, resources, event=None):
        algorithms = self.data.get('algorithms', [])
        if not algorithms:
            return resources

        results = []
        for resource in resources:
            signature_algorithm = resource.get('signature_algorithm')
            if signature_algorithm in algorithms:
                results.append(resource)

        return results


@CertificateAuthority.action_registry.register('disable')
class DisableCertificateAuthority(HuaweiCloudBaseAction):
    """Disable Certificate Authority

    This action will only disable CAs that have an empty or null issuer_name.

    :example:
    .. code-block:: yaml

        policies:
          - name: disable-cas
            resource: huaweicloud.ccm-private-ca
            filters:
              - type: status
                value: ACTIVED
              - type: issuer-name
                value: null
            actions:
              - disable
    """
    schema = type_schema('disable')
    permissions = ('ccm:disableCertificateAuthority',)

    def process(self, resources):
        filtered_resources = []

        for resource in resources:
            # Only process resources with empty or null issuer_name
            issuer_name = resource.get('issuer_name')
            if not issuer_name or (isinstance(issuer_name, str) and not issuer_name.strip()):
                filtered_resources.append(resource)
            else:
                self.log.info(
                    f"Skipping CA: {resource.get('name')} (ID: {resource.get('ca_id')}) - "
                    f"issuer_name is not empty: {issuer_name}")

        return super(DisableCertificateAuthority, self).process(filtered_resources)

    def perform_action(self, resource):
        client = self.manager.get_client()
        ca_id = resource.get('ca_id') or resource.get('id')

        try:
            request = DisableCertificateAuthorityRequest(ca_id=ca_id)
            response = client.disable_certificate_authority(request)
            self.log.info(
                f"Successfully disabled CA: {resource.get('name')} (ID: {ca_id})")
            return response
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to disable CA {resource.get('name')} (ID: {ca_id}): {e.error_msg}")
            raise


@resources.register('ccm-private-certificate')
class PrivateCertificate(QueryResourceManager):
    """Huawei Cloud Private Certificate Resource Manager

    :example:
    Define a simple policy to get all private certificates:

    .. code-block:: yaml

        policies:
          - name: list-certificates
            resource: huaweicloud.ccm-private-certificate
    """
    class resource_type(TypeInfo):
        service = 'ccm-private-certificate'
        enum_spec = ('list_certificate', 'certificates', 'offset')
        id = 'certificate_id'
        name = 'common_name'
        filter_name = 'name'
        filter_type = 'scalar'
        taggable = True
        tag_resource_type = 'private-certificates'

    def augment(self, resources):
        """Process resource information, ensure id field is correctly set"""
        for r in resources:
            if 'id' not in r and 'certificate_id' in r:
                r['id'] = r['certificate_id']

        # Query tags for each certificate and add them to the resource properties
        session = local_session(self.session_factory)
        client = session.client('ccm-private-certificate')

        for resource in resources:
            try:
                # Get certificate ID
                certificate_id = resource.get('certificate_id')
                if not certificate_id:
                    continue

                # Use ListCertTagsRequest to query tags for this certificate
                request = ListCertTagsRequest()
                request.certificate_id = certificate_id

                try:
                    # Call the API to get tags
                    response = client.list_cert_tags(request)

                    # Check if tags are available in the response
                    if hasattr(response, 'tags') and response.tags is not None:
                        # Convert response tags to standard dict format
                        tags = []
                        for tag in response.tags:
                            if hasattr(tag, 'key') and hasattr(tag, 'value'):
                                tags.append(
                                    {'key': tag.key, 'value': tag.value})
                        resource['tags'] = tags
                    else:
                        resource['tags'] = []
                except exceptions.ClientRequestException as e:
                    log.warning(
                        f"Failed to retrieve tags for certificate {certificate_id}: {e.error_msg}")
                    resource['tags'] = []
            except Exception as e:
                log.error(
                    f"Error retrieving tags for cert {resource.get('certificate_id')}: {str(e)}"
                )
                resource['tags'] = []

        return resources


@PrivateCertificate.filter_registry.register('key-algorithm')
class PrivateCertificateKeyAlgorithmFilter(Filter):
    """Filter private certificates by key algorithm

    This filter allows filtering certificates by key algorithm type,
    such as RSA2048, RSA4096, EC256, EC384, etc.

    :example:

    .. code-block:: yaml

        policies:
          - name: find-certificates-with-specific-key-algorithm
            resource: huaweicloud.ccm-private-certificate
            filters:
              - type: key-algorithm
                algorithms:
                  - RSA2048
                  - RSA4096
    """
    schema = type_schema(
        'key-algorithm',
        algorithms={'type': 'array', 'items': {'type': 'string'}}
    )

    def process(self, resources, event=None):
        algorithms = self.data.get('algorithms', [])
        if not algorithms:
            return resources

        results = []
        for resource in resources:
            key_algorithm = resource.get('key_algorithm')
            if key_algorithm in algorithms:
                results.append(resource)

        return results


@PrivateCertificate.filter_registry.register('signature-algorithm')
class PrivateCertificateSignatureAlgorithmFilter(Filter):
    """Filter private certificates by signature algorithm

    This filter allows filtering certificates by signature algorithm type,
    such as SHA256, SHA384, SHA512, etc.

    :example:

    .. code-block:: yaml

        policies:
          - name: find-certificates-with-specific-signature-algorithm
            resource: huaweicloud.ccm-private-certificate
            filters:
              - type: signature-algorithm
                algorithms:
                  - SHA256
                  - SHA384
    """
    schema = type_schema(
        'signature-algorithm',
        algorithms={'type': 'array', 'items': {'type': 'string'}}
    )

    def process(self, resources, event=None):
        algorithms = self.data.get('algorithms', [])
        if not algorithms:
            return resources

        results = []
        for resource in resources:
            signature_algorithm = resource.get('signature_algorithm')
            if signature_algorithm in algorithms:
                results.append(resource)

        return results


@PrivateCertificate.filter_registry.register('create-time')
class PrivateCertificateCreateTimeFilter(Filter):
    """Filter private certificates created after a specified datetime

    This filter allows finding certificates created after a specified datetime.
    Users can input a standard datetime string (e.g., 2025-5-26 09:27:25),
    and the filter will convert it to a timestamp to compare with
    the create_time returned by the API.

    :example:

    .. code-block:: yaml

        # Find all certificates created after May 26, 2025, 9:27:25 AM
        policies:
          - name: find-certificates-created-after-specific-time
            resource: huaweicloud.ccm-private-certificate
            filters:
              - type: create-time
                value: "2025-5-26 09:27:25"
    """
    schema = type_schema(
        'create-time',
        value={'type': 'string'}
    )

    def process(self, resources, event=None):
        import datetime
        import time

        date_str = self.data.get('value')
        if not date_str:
            return resources

        # Convert user input datetime string to timestamp (milliseconds)
        try:
            # Try to parse the user input datetime string
            dt = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            # Convert to millisecond timestamp
            timestamp_ms = int(time.mktime(dt.timetuple()) * 1000)
        except ValueError as e:
            log.error(
                f"Date format error: {date_str}. Should be 'YYYY-MM-DD HH:MM:SS'. Error: {e}")
            return []

        results = []
        for resource in resources:
            # Get resource creation time (millisecond timestamp)
            create_time = resource.get('create_time')

            # Only include resources where create_time exists and
            # is greater than or equal to the specified timestamp
            if create_time and create_time >= timestamp_ms:
                results.append(resource)

        return results
