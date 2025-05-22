# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import json
from c7n.utils import type_schema, local_session
from c7n.filters import ValueFilter, Filter
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkccm.v1.model import (
    DisableCertificateAuthorityRequest,
)

log = logging.getLogger('custodian.huaweicloud.resources.ccm')


@resources.register('ccm-certificateAuthority')
class CertificateAuthority(QueryResourceManager):
    """Huawei Cloud Certificate Authority Resource Manager

    :example:
    Define a simple policy to get all certificate authorities:

    .. code-block:: yaml

        policies:
          - name: list-certificate-authorities
            resource: huaweicloud.ccm-certificateAuthority
    """
    class resource_type(TypeInfo):
        service = 'ccm-certificateAuthority'
        enum_spec = ('list_certificate_authority',
                     'certificate_authorities', 'offset')
        id = 'ca_id'
        name = 'distinguished_name.common_name'
        filter_name = 'name'
        filter_type = 'scalar'
        taggable = True
        tag_resource_type = 'ccm-certificateAuthority'

    def augment(self, resources):
        """Process resource information, ensure id field is correctly set"""
        for r in resources:
            if 'id' not in r and 'ca_id' in r:
                r['id'] = r['ca_id']
            # Ensure tags are properly handled
            if 'tags' in r and r['tags'] is None:
                r['tags'] = []
        return resources


@CertificateAuthority.filter_registry.register('status')
class CertificateAuthorityStatusFilter(ValueFilter):
    """Filter certificate authorities by CA status

    Statuses include: ACTIVED (activated), DISABLED (disabled), PENDING (pending activation),
    DELETED (scheduled for deletion), EXPIRED (expired)

    :example:

    .. code-block:: yaml

        policies:
          - name: find-disabled-cas
            resource: huaweicloud.ccm-certificateAuthority
            filters:
              - type: status
                value: DISABLED
    """
    schema = type_schema(
        'status',
        rinherit=ValueFilter.schema
    )
    schema_alias = True

    def __init__(self, data, manager=None):
        super(CertificateAuthorityStatusFilter, self).__init__(data, manager)
        self.data['key'] = 'status'

    def process(self, resources, event=None):
        return super(CertificateAuthorityStatusFilter, self).process(resources, event)


@CertificateAuthority.filter_registry.register('crl-obs-bucket')
class CertificateAuthorityCrlObsBucketFilter(Filter):
    """Filter certificate authorities by OBS bucket name in CRL configuration

    This filter filters certificate authorities based on the OBS bucket name in the CRL configuration
    and BPA response values.

    :example:

    .. code-block:: yaml

        policies:
          - name: find-cas-with-obs-bucket
            resource: huaweicloud.ccm-certificateAuthority
            filters:
              - type: crl-obs-bucket
                bucket_name: my-certificate-bucket
                bpa_response:
                  read: true
                  write: true
                  list: true
                  delete: true
    """
    schema = type_schema(
        'crl-obs-bucket',
        bucket_name={'type': 'string'},
        bpa_response={
            'type': 'object',
            'properties': {
                'read': {'type': 'boolean'},
                'write': {'type': 'boolean'},
                'list': {'type': 'boolean'},
                'delete': {'type': 'boolean'}
            }
        }
    )

    def process(self, resources, event=None):
        session = local_session(self.manager.session_factory)
        obs_client = session.client('obs')

        bucket_name = self.data.get('bucket_name')
        bpa_response = self.data.get('bpa_response', {})

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

            # Check bucket permissions
            if bpa_response:
                try:
                    resp = obs_client.getBucketPolicy(
                        bucketName=obs_bucket_name)
                    # Check response status
                    if resp.status < 300:
                        # Parse bucket policy
                        policy = json.loads(resp.body.buffer) if hasattr(
                            resp, 'body') and hasattr(resp.body, 'buffer') else {}

                        # Default all permissions to False
                        actual_bpa = {
                            'read': False,
                            'write': False,
                            'list': False,
                            'delete': False
                        }

                        # Analyze policy to determine permissions
                        # Simplified policy analysis; actual implementation should parse OBS policy format in detail
                        if 'Statement' in policy:
                            for statement in policy['Statement']:
                                if 'Effect' in statement and statement['Effect'] == 'Allow':
                                    if 'Action' in statement:
                                        actions = statement['Action'] if isinstance(
                                            statement['Action'], list) else [statement['Action']]
                                        for action in actions:
                                            if 'obs:object:Get' in action:
                                                actual_bpa['read'] = True
                                            if 'obs:object:Put' in action:
                                                actual_bpa['write'] = True
                                            if 'obs:bucket:ListBucket' in action:
                                                actual_bpa['list'] = True
                                            if 'obs:object:Delete' in action:
                                                actual_bpa['delete'] = True

                        # Compare user specified BPA response with actual BPA response
                        match = True
                        for key, value in bpa_response.items():
                            if actual_bpa.get(key) != value:
                                match = False
                                break

                        if match:
                            results.append(resource)

                except exceptions.ClientRequestException as e:
                    log.error(
                        f"Failed to get bucket policy for {obs_bucket_name}: {e.error_msg}")
                    continue
            else:
                # If no BPA response specified, return all CAs with OBS buckets by default
                results.append(resource)

        return results


@CertificateAuthority.filter_registry.register('key-algorithm')
class CertificateAuthorityKeyAlgorithmFilter(Filter):
    """Filter certificate authorities by key algorithm

    This filter allows filtering CAs by key algorithm type, such as RSA2048, RSA4096, EC256, EC384, etc.

    :example:

    .. code-block:: yaml

        policies:
          - name: find-cas-with-specific-key-algorithm
            resource: huaweicloud.ccm-certificateAuthority
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

    This filter allows filtering CAs by signature algorithm type, such as SHA256, SHA384, SHA512, etc.

    :example:

    .. code-block:: yaml

        policies:
          - name: find-cas-with-specific-signature-algorithm
            resource: huaweicloud.ccm-certificateAuthority
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

    :example:
    .. code-block:: yaml

        policies:
          - name: disable-cas
            resource: huaweicloud.ccm-certificateAuthority
            filters:
              - type: status
                value: ACTIVED
            actions:
              - disable
    """
    schema = type_schema('disable')
    permissions = ('ccm:disableCertificateAuthority',)

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


@resources.register('ccm-privateCertificate')
class PrivateCertificate(QueryResourceManager):
    """Huawei Cloud Private Certificate Resource Manager

    :example:
    Define a simple policy to get all private certificates:

    .. code-block:: yaml

        policies:
          - name: list-certificates
            resource: huaweicloud.ccm-privateCertificate
    """
    class resource_type(TypeInfo):
        service = 'ccm-privateCertificate'
        enum_spec = ('list_certificate', 'certificates', 'offset')
        id = 'certificate_id'
        name = 'common_name'
        filter_name = 'name'
        filter_type = 'scalar'
        taggable = True
        tag_resource_type = 'ccm-privateCertificate'

    def augment(self, resources):
        """Process resource information, ensure id field is correctly set"""
        for r in resources:
            if 'id' not in r and 'certificate_id' in r:
                r['id'] = r['certificate_id']
        return resources


@PrivateCertificate.filter_registry.register('key-algorithm')
class PrivateCertificateKeyAlgorithmFilter(Filter):
    """Filter private certificates by key algorithm

    This filter allows filtering certificates by key algorithm type, such as RSA2048, RSA4096, EC256, EC384, etc.

    :example:

    .. code-block:: yaml

        policies:
          - name: find-certificates-with-specific-key-algorithm
            resource: huaweicloud.ccm-privateCertificate
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

    This filter allows filtering certificates by signature algorithm type, such as SHA256, SHA384, SHA512, etc.

    :example:

    .. code-block:: yaml

        policies:
          - name: find-certificates-with-specific-signature-algorithm
            resource: huaweicloud.ccm-privateCertificate
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
