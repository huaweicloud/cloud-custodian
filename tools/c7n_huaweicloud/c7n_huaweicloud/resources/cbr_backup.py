import logging
from huaweicloudsdkcore.exceptions import exceptions

from huaweicloudsdkcbr.v1 import (DeleteBackupRequest,
                                  CopyBackupRequest,
                                  BackupReplicateReqBody,
                                  BackupReplicateReq,
                                  )

from c7n.filters import Filter
from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

log = logging.getLogger("custodian.huaweicloud.resources.cbr-backup")


@resources.register('cbr-backup')
class CbrBackup(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'cbr-backup'
        enum_spec = ('list_backups', 'backups', 'offset')
        id = 'id'
        tag_resource_type = ''


@CbrBackup.action_registry.register('delete')
class CbrDeleteBackup(HuaweiCloudBaseAction):
    """Checks if a recovery point is encrypted.Delete the recovery point not encrypted.

    WARNING: Deleted backups are unrecoverable forever.

    : Example:

    .. code-block:: yaml

        policies:
            - name: delete-unencrypted-backup
              resource: huaweicloud.cbr-backup
              filters:
                - and:
                  - type: value
                    key: extend_info.encrypted
                    value: false
                  - type: value
                    key: resource_type
                    value: "OS::Cinder::Volume"
              actions:
                  - delete
    """
    schema = type_schema('delete')

    def perform_action(self, resource):
        client = self.manager.get_client()
        try:
            request = DeleteBackupRequest()
            request.backup_id = resource['id']
            response = client.delete_backup(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response


@CbrBackup.filter_registry.register('without_replication_record')
class CbrBackupFilter(Filter):
    """
        Filter the backup without replication record.
    """
    schema = type_schema('without_replication_record')

    def process(self, resources, event=None):
        results = []
        for r in resources:
            try:
                replication_record = r['replication_records']
                if not replication_record:
                    results.append(r)
            except exceptions.ClientRequestException as e:
                log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
                raise
        return results


@CbrBackup.action_registry.register('create_replication')
class CbrCreateReplication(HuaweiCloudBaseAction):
    """
        Create replication record to a preset vault in a preset region.
    """
    schema = type_schema('create_replication',
                         destination_project_id={'type': 'string'},
                         destination_region={'type': 'string'},
                         destination_vault_id={'type': 'string'},
    )
    def perform_action(self, resource, event=None):
        client = self.manager.get_client()
        try:
            request = CopyBackupRequest()
            request.backup_id = resource['id']
            replicatebody = BackupReplicateReqBody(
                destination_project_id=self.data.get('destination_project_id'),
                destination_region=self.data.get('destination_region'),
                destination_vault_id=self.data.get('destination_vault_id'),
            )
            request.body = BackupReplicateReq(
                replicate=replicatebody
            )
            response = client.copy_backup(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response

