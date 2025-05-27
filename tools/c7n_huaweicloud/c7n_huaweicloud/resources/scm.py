# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkscm.v3 import (
    # Certificate management related
    DeleteCertificateRequest,
)

from c7n.utils import type_schema
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction

log = logging.getLogger('custodian.huaweicloud.scm')


@resources.register('ccm-ssl-certificate')
class Scm(QueryResourceManager):

    class resource_type(TypeInfo):
        service = 'ccm-ssl-certificate'
        enum_spec = ('list_certificates', 'certificates', None)
        id = 'id'
        name = 'name'
        filter_name = 'name'
        filter_type = 'scalar'
        taggable = True
        # Set tag resource type for TMS operations
        tag_resource_type = 'scm'


@Scm.action_registry.register('delete')
class DeleteCertificateAction(HuaweiCloudBaseAction):
    """Delete Certificate Action

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-expired-certificates
            resource: huaweicloud.ccm-ssl-certificate
            filters:
              - type: value
                key: status
                value: EXPIRED
            actions:
              - delete
    """

    schema = type_schema('delete')

    def perform_action(self, resource):
        client = self.manager.get_client()
        certificate_id = resource['id']

        try:
            request = DeleteCertificateRequest(certificate_id=certificate_id)
            client.delete_certificate(request)
            self.log.info(
                f"Successfully deleted certificate: {resource.get('name')} (ID: {certificate_id})"
            )
        except exceptions.ClientRequestException as e:
            self.log.error(
                f"Failed to delete certificate {resource.get('name')} (ID: {certificate_id}): "
                f"RequestId: {e.request_id}, Error: {e.error_msg}"
            )
            raise
