import logging
from huaweicloudsdkcore.exceptions import exceptions

from huaweicloudsdkcbr.v1 import DeleteBackupRequest

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
            log.info(f"[actions]-[delete] The resource:[cbr-backup] with id:[{resource['id']}]"
                     f" is deleted success.")
        except exceptions.ClientRequestException as e:
            log.error(f"[actions]-[delete] The resource:[cbr-backup] with id:[{resource['id']}]"
                      f" is failed, cause:request id:{e.request_id}, status code:{e.status_code},"
                      f" msg: {e.error_msg}")
            raise
        return response
