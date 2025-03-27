# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import logging
from datetime import datetime, timezone, timedelta

from c7n.utils import type_schema, local_session
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n.filters import Filter
from huaweicloudsdkcbr.v1 import ListVaultRequest, ListBackupsRequest
from huaweicloudsdkcbr.v1 import AddVaultResourceRequest, VaultAddResourceReq
from huaweicloudsdkcbr.v1 import ResourceCreate, VaultAssociate, AssociateVaultPolicyRequest
from huaweicloudsdksfsturbo.v1 import DeleteShareRequest

log = logging.getLogger("custodian.huaweicloud.resources.sfsturbo")

CBR_SFSTurbo_RESOURCE_TYPE = "OS::Sfs::Turbo"


@resources.register('sfsturbo')
class SfsTurbo(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'sfsturbo'
        enum_spec = ("list_shares", 'shares', 'offset')
        id = 'id'
        tag_resource_type = "sfs-turbo"


@SfsTurbo.filter_registry.register("not-protected-by-backup")
class NotProtectedByBackupSfsturbo(Filter):
    """Check if an evs volume is not protected by backup.

    .. code-block:: yaml

      policies:
       - name: not-protected-by-backup
         resource: huaweicloud.sfsturbo
         filters:
           - not-protected-by-backup
    """
    schema = type_schema('not-protected-by-backup')

    def is_sfsturbo_not_associated_to_vault(self, resource):
        client = local_session(self.manager.session_factory).client('cbr')
        request = ListVaultRequest()
        share_id = resource['id']
        request.resource_ids = share_id
        request.object_type = 'turbo'
        response = client.list_vault(request)
        if len(response.vaults) == 0:
            return True
        else:
            return False

    def process(self, resources, event=None):
        all_match_resources = []
        for r in resources:
            if self.is_sfsturbo_not_associated_to_vault(r):
                all_match_resources.append(r)
        return all_match_resources


@SfsTurbo.filter_registry.register("last-backup-exceed-safe-time-interval")
class LastBackupCreateExceedSafeTimeSfsTurbo(Filter):
    """Check if the creating time of the latest backup exceeds safe time interval in hours

    .. code-block:: yaml

      policies:
       - name: last-backup-exceed-safe-time-interval
         resource: huaweicloud.sfsturbo
         filters:
           - type: last-backup-exceed-safe-time-interval
             interval: 24
    """

    schema = type_schema(
        'last-backup-exceed-safe-time-interval',
        required=['interval'],
        interval={'type': 'number'},
        reference_time={'type': 'string'}
    )

    def is_last_backup_exceed_safe_time_interval(self, resource, interval):
        client = local_session(self.manager.session_factory).client('cbr')
        share_id = resource["id"]
        request = ListBackupsRequest()
        request.limit = 1
        request.resource_id = share_id
        request.resource_type = CBR_SFSTurbo_RESOURCE_TYPE
        request.sort = "created_at"
        response = client.list_backups(request)
        if len(response.backups) == 0:
            log.info("sfsturbo %s has no backup" % share_id)
            return True

        # add reference_time(local timezone) for ut test
        reference_time = self.data.get('reference_time')
        if not reference_time:
            current_time = datetime.utcnow().replace(tzinfo=timezone.utc)
        else:
            current_time = datetime.fromisoformat(reference_time).astimezone(timezone.utc)

        # created_at info from backend API is already UTC timezone
        backup_time = response.backups[0].created_at
        if not isinstance(backup_time, datetime):
            backup_time = datetime.fromisoformat(backup_time).replace(tzinfo=timezone.utc)
        time_difference = current_time - backup_time
        return time_difference > timedelta(hours=interval)

    def process(self, resources, event=None):
        all_match_resources = []
        for r in resources:
            if self.is_last_backup_exceed_safe_time_interval(r, self.data.get('interval')):
                all_match_resources.append(r)
        return all_match_resources


@SfsTurbo.action_registry.register("delete")
class SfsTurboDelete(HuaweiCloudBaseAction):
    """Deletes SfsTurbo Volumes.

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-unencrypted-sfsturbo
            resource: huaweicloud.sfsturbo
            filters:
              - "crypt_key_id": "empty"
            actions:
              - delete
    """

    schema = type_schema("delete")

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = DeleteShareRequest()
        request.share_id = resource["id"]
        response = client.delete_share(request)
        return response


@SfsTurbo.action_registry.register('add-sfsturbo-to-vault')
class AssociateBackupPolicyToSfsTurbo(HuaweiCloudBaseAction):
    """ associate sfsturbo to an already existed backup vault.

    :Example:

    .. code-block:: yaml

        policies:
          - name: add-encrypted-sfsturbo-to-backup-vault
            resource: huaweicloud.sfsturbo
            filters:
              - not-protected-by-backup
            actions:
              - type: add-sfsturbo-to-vault
                vault_id: vault_id
    """

    schema = type_schema("add-sfsturbo-to-vault", vault_id={'type': 'string'})

    def perform_action(self, resource):
        client = local_session(self.manager.session_factory).client('cbr')
        request = AddVaultResourceRequest()
        request.vault_id = self.data.get("vault_id")
        listResourcesbody = [
            ResourceCreate(
                id=resource["id"],
                type=CBR_SFSTurbo_RESOURCE_TYPE
            )
        ]
        request.body = VaultAddResourceReq(
            resources=listResourcesbody
        )
        client.add_vault_resource(request)


@SfsTurbo.action_registry.register('associate-sfsturbo-vault-to-policy')
class SfsTurboAssociateToVaultPolicy(HuaweiCloudBaseAction):
    """ associate sfsturbo's vault to a vault policy.

    :Example:

    .. code-block:: yaml

        policies:
          - name: associate-sfsturbo-vault-to-policy
            resource: huaweicloud.sfsturbo
            filters:
              - type: last-backup-exceed-safe-time-interval
                interval: 1
            actions:
              - type: associate-sfsturbo-vault-to-policy
                policy_id: policy_id
    """

    schema = type_schema(type_name="associate-sfsturbo-vault-to-policy",
                         required=['policy_id'],
                         policy_id={'type': 'string'})

    def perform_action(self, resource):
        client = local_session(self.manager.session_factory).client('cbr')
        volume_id = resource["id"]
        log.info("associate vault of Volume %s to vault policy" % volume_id)
        request = ListVaultRequest()
        request.resource_ids = volume_id
        response = client.list_vault(request)
        if len(response.vaults) == 0:
            log.info('volume %s has not associated to any vault, ignore' % volume_id)
            return
        vault_id = response.vaults[0].id
        request = AssociateVaultPolicyRequest()
        request.vault_id = vault_id
        request.body = VaultAssociate(
            policy_id=self.data.get('policy_id')
        )
        client.associate_vault_policy(request)
