# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import time
from concurrent.futures import as_completed
from datetime import datetime, timedelta, timezone

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkevs.v2 import (
    CreateVolumeRequestBody, CreateVolumeOption, CreateVolumeRequest,
    BatchDeleteVolumeTagsRequestBody, DeleteTagsOption, BatchDeleteVolumeTagsRequest,
    DeleteVolumeRequest, CreateSnapshotRequestBody, CreateSnapshotOption, CreateSnapshotRequest,
    ResizeVolumeRequestBody, OsExtend, ResizeVolumeRequest, ShowJobRequest)
from huaweicloudsdkecs.v2 import (
    BatchStopServersRequestBody, BatchStopServersOption, ServerId, BatchStopServersRequest,
    BatchStartServersRequestBody, BatchStartServersOption, BatchStartServersRequest,
    UpdateServerBlockDeviceReq, UpdateServerBlockDeviceOption, UpdateServerBlockDeviceRequest,
    AttachServerVolumeRequestBody, AttachServerVolumeOption, AttachServerVolumeRequest,
    DetachServerVolumeRequest, ShowServerRequest)
from huaweicloudsdkcbr.v1 import (
    VaultBackupReq, VaultBackup, CheckpointParam, Resource, CreateCheckpointRequest,
    VaultAssociate, AssociateVaultPolicyRequest, VaultAddResourceReq, ResourceCreate,
    AddVaultResourceRequest, ListBackupsRequest, ShowCheckpointRequest, VaultCreateReq,
    VaultCreate, BillingCreate, CreateVaultRequest, DeleteBackupRequest, DeleteVaultRequest,
    ListVaultRequest)

from c7n.utils import type_schema, local_session
from c7n.filters import Filter, AgeFilter
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo


log = logging.getLogger("custodian.huaweicloud.resources.evs")


CBR_VOLUME_RESOURCE_TYPE = "OS::Cinder::Volume"


def wait_job_end(client, job_id, timeout=120):
    for _ in range(timeout):
        try:
            request = ShowJobRequest()
            request.job_id = job_id
            response = client.show_job(request)
            if response.status.upper() == "SUCCESS":
                return
            time.sleep(1)
        except exceptions.ClientRequestException as e:
            log.error(f"Job {job_id} status_code: {e.status_code},"
                     f" request_id: {e.request_id},"
                     f" error_code: {e.error_code},"
                     f" error_msg: {e.error_msg}")

    log.error(f"Job {job_id} timeout: {timeout}")


def get_cbr_vault_of_volume(client, volume_id):
    request = ListVaultRequest()
    request.object_type = 'disk'
    request.resource_ids = volume_id
    response = client.list_vault(request)
    return response


@resources.register('evs-volume')
class Volume(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'evs'
        enum_spec = ("list_volumes_invoker", 'volumes', 'offset')
        id = 'id'
        tag_resource_type = 'disk'


@Volume.filter_registry.register("not-protected-by-backup")
class NotProtectedByBackupVolumes(Filter):
    """Check if an evs volume is not protected by backup.

    .. code-block:: yaml

      policies:
       - name: not-protected-by-backup
         resource: huaweicloud.evs-volume
         filters:
           - not-protected-by-backup
    """
    schema = type_schema('not-protected-by-backup')

    def is_volume_not_associated_to_vault(self, volume):
        client = local_session(self.manager.session_factory).client('cbr')
        response = get_cbr_vault_of_volume(client, volume['id'])
        if len(response.vaults) == 0:
            return True
        else:
            return False

    def process(self, resources, event=None):
        return [r for r in resources if self.is_volume_not_associated_to_vault(r)]


@Volume.filter_registry.register("last-backup-exceed-safe-time-interval")
class LastBackupCreateExceedSafeTimeVolumes(Filter):
    """Check if the creating time of the latest backup exceeds safe time interval (in hours)

    .. code-block:: yaml

      policies:
       - name: last-backup-exceed-safe-time-interval
         resource: huaweicloud.evs-volume
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

    def is_last_backup_exceed_safe_time_interval(self, volume, interval):
        client = local_session(self.manager.session_factory).client('cbr')
        volume_id = volume["id"]
        request = ListBackupsRequest()
        request.limit = 1
        request.resource_id = volume_id
        request.resource_type = CBR_VOLUME_RESOURCE_TYPE
        request.sort = "created_at"
        response = client.list_backups(request)
        if len(response.backups) == 0:
            log.info("Volume %s has no backup" % volume_id)
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
        return [r for r in resources if self.is_last_backup_exceed_safe_time_interval(
            r, self.data.get('interval'))]


@Volume.filter_registry.register('volume-age')
class VolumeAge(AgeFilter):
    """EVS Volume Age Filter

    Filters an EVS volume based on the age of the volume (in days)

    :example:

    .. code-block:: yaml

            policies:
              - name: evs-volumes-days-old
                resource: evs-volume
                filters:
                  - type: volume-age
                    days: 7
                    op: ge
    """

    schema = type_schema(
        'volume-age',
        days={'type': 'number'},
        op={'$ref': '#/definitions/filters_common/comparison_operators'})
    date_attribute = 'created_at'


@Volume.action_registry.register("delete")
class VolumeDelete(HuaweiCloudBaseAction):
    """Deletes EVS Volumes.

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-unencrypted-volume
            resource: huaweicloud.evs-volume
            filters:
              - type: value
                key: metadata.__system__encrypted
                value: "0"
            actions:
              - delete
    """

    schema = type_schema("delete")

    def perform_action(self, resource):
        client = self.manager.get_client()
        volume_id = resource["id"]
        log.info("delete Volume %s" % volume_id)
        request = DeleteVolumeRequest(volume_id=volume_id)

        # request with retry
        response = self._invoke_client_request(
            client, "delete_volume_invoker", request
        )
        job_id = response.job_id
        log.info(f"Received Job ID:{job_id}")
        wait_job_end(client, job_id)
        response = None
        return response


@Volume.action_registry.register("detach")
class VolumeDetach(HuaweiCloudBaseAction):
    """
    Detach an EVS volume from an Instance.

    If 'force' Param is True, then we'll do a forceful detach
    of the Volume. The default value for 'force' is False.

     :Example:

     .. code-block:: yaml

             policies:
               - name: detach-volumes
                 resource: huaweicloud.evs-volume
                 filters:
                   - id :  volumeid
                 actions:
                   - detach


    """

    schema = type_schema("detach", force={'type': 'boolean'})

    def perform_action(self, resource):
        ecs_client = local_session(self.manager.session_factory).client('ecs')
        log.info("detach Volume %s" % resource['id'])

        for attachment in resource.get('attachments', []):
            request = DetachServerVolumeRequest()
            request.volume_id = attachment['volume_id']
            request.delete_flag = str(int(self.data.get('force', False)))
            request.server_id = attachment['server_id']
            ecs_client.detach_server_volume(request)


@Volume.action_registry.register("extend")
class VolumeExtend(HuaweiCloudBaseAction):
    """
    Extend an EVS volume

     :Example:

     .. code-block:: yaml

             policies:
               - name: extend-volumes
                 resource: huaweicloud.evs-volume
                 filters:
                   - id:  volumeid
                 actions:
                   - type: extend
                     size: 200

    """

    schema = type_schema("extend", required=['size'], size={'type': 'number'})

    def perform_action(self, resource):
        client = self.manager.get_client()
        volume_id = resource["id"]
        log.info("extend Volume %s" % volume_id)
        request = ResizeVolumeRequest()
        request.volume_id = volume_id
        osextendbody = OsExtend(
            new_size=self.data.get('size')
        )
        request.body = ResizeVolumeRequestBody(
            os_extend=osextendbody
        )
        response = client.resize_volume(request)
        job_id = response.job_id
        log.info(f"Received Job ID:{job_id}")
        wait_job_end(client, job_id)


@Volume.action_registry.register("snapshot")
class CreateSnapshot(HuaweiCloudBaseAction):
    """
    Snapshot an EVS volume

     :Example:

     .. code-block:: yaml

             policies:
               - name: snapshot-volumes
                 resource: huaweicloud.evs-volume
                 filters:
                   - id:  volumeid
                 actions:
                   - type: snapshot
                     force: true

    """

    schema = type_schema("snapshot",
                         **{"force": {"type": "boolean"},
                            "name": {"type": "string"},
                            "description": {"type": "string"}})

    def perform_action(self, resource):
        client = self.manager.get_client()
        volume_id = resource["id"]
        log.info("create snapshot of Volume %s" % volume_id)
        request = CreateSnapshotRequest()
        snapshotbody = CreateSnapshotOption(
            volume_id=volume_id,
            force=self.data.get("force", False),
            description=self.data.get("description"),
            name=self.data.get("name")
        )
        request.body = CreateSnapshotRequestBody(
            snapshot=snapshotbody
        )
        client.create_snapshot(request)


@Volume.action_registry.register('encrypt-instance-data-volumes')
class EncryptInstanceDataVolumes(HuaweiCloudBaseAction):
    """
    Encrypt extant volumes attached to an instance

    - Requires instance restart

    Multistep process:

    - Stop instance (if running)
    - For each volume
       - Create backup
       - Wait on backup creation
       - Create encrypted volume from backup
       - Wait on volume creation
       - Delete transient backups
       - Detach Unencrypted Volume
       - Attach Encrypted Volume
    - For each volume
       - Delete unencrypted volume
    - Start Instance (if originally running)

    :example:

    .. code-block:: yaml

            policies:
              - name: encrypt-unencrypted-evs
                resource: huaweicloud.evs-volume
                filters:
                  - or:
                    - type: value
                      key: metadata.__system__encrypted
                      value: "0"
                    - type: value
                      key: metadata.__system__encrypted
                      value: "empty"
                actions:
                  - type: encrypt-instance-data-volumes
                    key: kmsKeyId
    """

    schema = type_schema(
        'encrypt-instance-data-volumes',
        required=['key'],
        key={'type': 'string'},
        delay={'type': 'number'})

    def perform_action(self, resource):
        pass

    def process(self, volumes):
        original_count = len(volumes)
        volumes = [v for v in volumes
                   if not str(v['metadata'].get('__system__encrypted')) == "1"
                   and v['attachments']
                   and not v.get('volume_image_metadata')]
        log.debug(
            "EncryptVolumes filtered from %d to %d "
            " unencrypted attached volumes" % (
                original_count, len(volumes)))

        # Group volumes by instance id
        instance_vol_map = {}
        for v in volumes:
            instance_id = v['attachments'][0]['server_id']
            instance_vol_map.setdefault(instance_id, []).append(v)

        ecs_client = local_session(self.manager.session_factory).client('ecs')
        evs_client = self.manager.get_client()
        cbr_client = local_session(self.manager.session_factory).client('cbr')

        with self.executor_factory(max_workers=3) as w:
            futures = {}
            for instance_id, vol_set in instance_vol_map.items():
                futures[w.submit(
                    self.process_volume, ecs_client, evs_client, cbr_client,
                    instance_id, vol_set)] = instance_id

            for f in as_completed(futures):
                if f.exception():
                    instance_id = futures[f]
                    log.error(
                        "Exception processing instance:%s volset: %s \n %s" % (
                            instance_id, instance_vol_map[instance_id],
                            f.exception()))
            return self.process_result(volumes)

    def process_volume(self, ecs_client, evs_client, cbr_client, instance_id, vol_set):
        """Encrypt attached unencrypted evs volumes

        vol_set corresponds to all the unencrypted volumes on a given instance.
        """
        request = ShowServerRequest()
        request.server_id = instance_id
        server_detail = ecs_client.show_server(request)
        server_extend_volume_attachments = server_detail.server.os_extended_volumesvolumes_attached
        volume_attachment_map = {}
        for server_extend_volume_attachment in server_extend_volume_attachments:
            volume_attachment_map[server_extend_volume_attachment.id] = {
                'delete_on_termination': server_extend_volume_attachment.delete_on_termination,
                'device': server_extend_volume_attachment.device
            }
        instance_state = server_detail.server.status
        # Only stop and start the instance if it was running.
        instance_running = self.stop_instance(ecs_client, instance_id, instance_state)
        if instance_running is None:
            return

        # Create all the volumes before patching the instance.
        paired = []
        for volume in vol_set:
            new_volume_id = self.create_encrypted_volume(cbr_client, evs_client, volume,
                                                         self.data.get('key'), instance_id,
                                                         volume_attachment_map)
            paired.append((volume, new_volume_id))

        # Next detach and reattach
        for volume, new_volume_id in paired:
            old_volume_id = volume['id']
            request = DetachServerVolumeRequest()
            request.volume_id = old_volume_id
            request.server_id = instance_id
            ecs_client.detach_server_volume(request)
            # detach isn't immediately consistent
            time.sleep(self.data.get('delay', 15))

            request = AttachServerVolumeRequest()
            request.server_id = instance_id
            volumeAttachmentbody = AttachServerVolumeOption(
                volume_id=new_volume_id
            )
            request.body = AttachServerVolumeRequestBody(
                volume_attachment=volumeAttachmentbody
            )
            response = ecs_client.attach_server_volume(request)
            wait_job_end(ecs_client, response.job_id)

            request = UpdateServerBlockDeviceRequest()
            request.volume_id = new_volume_id
            request.server_id = instance_id
            if str(volume_attachment_map.get(old_volume_id, {}).get(
                    'delete_on_termination')).lower() == 'true':
                blockDevicebody = UpdateServerBlockDeviceOption(
                    delete_on_termination=True
                )
                request.body = UpdateServerBlockDeviceReq(
                    block_device=blockDevicebody
                )
                ecs_client.update_server_block_device(request)

        if instance_running:
            request = BatchStartServersRequest()
            listServersOsstart = [
                ServerId(
                    id=instance_id
                )
            ]
            osstartbody = BatchStartServersOption(
                servers=listServersOsstart
            )
            request.body = BatchStartServersRequestBody(
                os_start=osstartbody
            )
            ecs_client.batch_start_servers(request)

        for volume in vol_set:
            request = DeleteVolumeRequest(volume_id=volume["id"])
            evs_client.delete_volume(request)

        # Clean-up transient tags on newly created encrypted volume.
        for _, new_volume_id in paired:
            request = BatchDeleteVolumeTagsRequest()
            request.volume_id = new_volume_id
            listTagsbody = [
                DeleteTagsOption(
                    key="maid-crypt-remediation"
                ),
                DeleteTagsOption(
                    key="maid-origin-volume"
                ),
                DeleteTagsOption(
                    key="maid-instance-device"
                )
            ]
            request.body = BatchDeleteVolumeTagsRequestBody(
                tags=listTagsbody,
                action="delete"
            )
            evs_client.batch_delete_volume_tags(request)

    def stop_instance(self, client, instance_id, instance_state):
        if instance_state in ('SHUTOFF', 'DELETED'):
            log.debug('Skipping terminating instance: %s' % instance_id)
            return
        elif instance_state in ('ACTIVE',):
            log.info(f"begin to stop instance {instance_id}")
            request = BatchStopServersRequest()
            listServersOsstop = [
                ServerId(
                    id=instance_id
                )
            ]
            osstopbody = BatchStopServersOption(
                servers=listServersOsstop,
                type="SOFT"
            )
            request.body = BatchStopServersRequestBody(
                os_stop=osstopbody
            )
            response = client.batch_stop_servers(request)
            wait_job_end(client, response.job_id)
            log.info(f"stop instance {instance_id} success")
            return True
        return False

    def create_encrypted_volume(self, cbr_client, evs_client, volume, key_id,
                                instance_id, volume_attachment_map):
        volume_id = volume['id']
        volume_size = volume['size']
        transient_vault_id = None
        # Create backup
        response = get_cbr_vault_of_volume(cbr_client, volume_id)
        if len(response.vaults) > 0:
            log.info('volume %s has already associated vault' % volume_id)
            vault_id = response.vaults[0].id
        else:
            vault_id = self.create_vault(cbr_client, volume_id, volume_size)
            transient_vault_id = vault_id
        backup_id = self.create_backup(cbr_client, vault_id, volume_id)

        # Create encrypted volume
        request = CreateVolumeRequest()
        listMetadataVolume = {
            "__system__encrypted": "1",
            "__system__cmkid": key_id
        }
        new_name = "%s_for_new_encrypted" % volume.get('name')
        volume_type = volume.get('volume_type')
        listTagsVolume = {
            "maid-crypt-remediation": instance_id,
            "maid-origin-volume": volume_id,
            "maid-instance-device": volume_attachment_map.get(volume_id, {}).get('device')
        }
        listTagsVolume.update(volume['tags'])
        volumebody = CreateVolumeOption(
            availability_zone=volume.get('availability_zone'),
            backup_id=backup_id,
            metadata=listMetadataVolume,
            name=new_name,
            size=volume.get('size'),
            volume_type=volume_type,
            tags=listTagsVolume,
            enterprise_project_id=volume.get('enterprise_project_id')
        )

        if volume_type == "GPSSD2":
            volumebody.iops = volume.get('iops').get('total_val')
            volumebody.throughput = volume.get('throughput').get('total_val')
        elif volume_type == "ESSD2":
            volumebody.iops = volume.get('iops').get('total_val')

        request.body = CreateVolumeRequestBody(
            volume=volumebody
        )
        response = evs_client.create_volume(request)
        new_volume_id = response.volume_ids[0]
        wait_job_end(evs_client, response.job_id)
        log.info('create new volume %s success' % new_volume_id)

        if transient_vault_id is not None:
            request = DeleteVaultRequest()
            request.vault_id = transient_vault_id
            cbr_client.delete_vault(request)
        else:
            request = DeleteBackupRequest()
            request.backup_id = backup_id
            cbr_client.delete_backup(request)
        return new_volume_id

    def create_vault(self, client, volume_id, volume_size):
        log.info('begin to create tmp vault of volume %s' % volume_id)
        request = CreateVaultRequest()
        listResourcesVault = [
            ResourceCreate(
                id=volume_id,
                type=CBR_VOLUME_RESOURCE_TYPE
            )
        ]
        billingVault = BillingCreate(
            consistent_level="crash_consistent",
            object_type="disk",
            protect_type="backup",
            size=volume_size
        )
        vaultbody = VaultCreate(
            billing=billingVault,
            name=self.data.get('name', 'cn7-tmp-vault-%s' % volume_id),
            resources=listResourcesVault
        )
        request.body = VaultCreateReq(
            vault=vaultbody
        )
        response = client.create_vault(request)
        log.info('create tmp vault of volume %s success' % volume_id)
        return response.vault.id

    def create_backup(self, client, vault_id, volume_id):
        log.info('create checkpoint of volume %s begin' % volume_id)
        request = CreateCheckpointRequest()
        listResourceDetailsParameters = [
            Resource(
                id=volume_id,
                type=CBR_VOLUME_RESOURCE_TYPE
            )
        ]
        parametersCheckpoint = CheckpointParam(
            resource_details=listResourceDetailsParameters
        )
        checkpointbody = VaultBackup(
            parameters=parametersCheckpoint,
            vault_id=vault_id
        )
        request.body = VaultBackupReq(
            checkpoint=checkpointbody
        )
        response = client.create_checkpoint(request)
        checkpoint_id = response.checkpoint.id

        for _ in range(86400):
            request = ShowCheckpointRequest()
            request.checkpoint_id = checkpoint_id
            response = client.show_checkpoint(request)
            if response.checkpoint.status == 'available':
                log.info('create checkpoint of volume %s success' % volume_id)
                break
            time.sleep(10)

        request = ListBackupsRequest()
        request.checkpoint_id = checkpoint_id
        response = client.list_backups(request)
        backup_id = response.backups[0].id
        return backup_id


@Volume.action_registry.register('add-volume-to-vault')
class VolumeAssociateToVault(HuaweiCloudBaseAction):
    """ associate Volumes to an already existed backup vault.

    :Example:

    .. code-block:: yaml

        policies:
          - name: add-encrypted-volume-to-backup-vault
            resource: huaweicloud.evs-volume
            filters:
              - type: value
                key: metadata.__system__encrypted
                value: "1"
            actions:
              - type: add-volume-to-vault
                vault_id: vault_id
    """

    schema = type_schema("add-volume-to-vault", required=['vault_id'], vault_id={'type': 'string'})

    def perform_action(self, resource):
        client = local_session(self.manager.session_factory).client('cbr')
        volume_id = resource["id"]
        response = get_cbr_vault_of_volume(client, volume_id)
        if len(response.vaults) != 0:
            log.info('volume %s has already associated to a vault, ignore' % volume_id)
            return
        log.info("associate Volume %s to vault" % volume_id)
        request = AddVaultResourceRequest()
        request.vault_id = self.data.get("vault_id")
        listResourcesbody = [
            ResourceCreate(
                id=volume_id,
                type=CBR_VOLUME_RESOURCE_TYPE
            )
        ]
        request.body = VaultAddResourceReq(
            resources=listResourcesbody
        )
        client.add_vault_resource(request)


@Volume.action_registry.register('associate-volume-vault-to-policy')
class VolumeAssociateToVaultPolicy(HuaweiCloudBaseAction):
    """ associate volume's vault to a vault policy.

    :Example:

    .. code-block:: yaml

        policies:
          - name: associate-encrypted-volume-vault-to-policy
            resource: huaweicloud.evs-volume
            filters:
              - type: value
                key: metadata.__system__encrypted
                value: "1"
            actions:
              - type: associate-volume-vault-to-policy
                policy_id: policy_id
    """

    schema = type_schema("associate-volume-vault-to-policy",
                         required=['policy_id'], policy_id={'type': 'string'})

    def perform_action(self, resource):
        client = local_session(self.manager.session_factory).client('cbr')
        volume_id = resource["id"]
        log.info("associate vault of Volume %s to vault policy" % volume_id)
        response = get_cbr_vault_of_volume(client, volume_id)
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


@Volume.action_registry.register('backup')
class CreateBackup(HuaweiCloudBaseAction):
    """ Backup an evs volume.

    :Example:

    .. code-block:: yaml

        policies:
          - name: backup-volumes
            resource: huaweicloud.evs-volume
            filters:
              - type: value
                key: metadata.__system__encrypted
                value: "1"
            actions:
              - backup
    """

    schema = type_schema("backup")

    def perform_action(self, resource):
        client = local_session(self.manager.session_factory).client('cbr')
        volume_id = resource["id"]
        log.info("begin to create backup of Volume %s" % volume_id)
        response = get_cbr_vault_of_volume(client, volume_id)
        if len(response.vaults) == 0:
            log.info('volume %s has not associated to any vault, ignore' % volume_id)
            return
        vault_id = response.vaults[0].id
        request = CreateCheckpointRequest()
        listResourceDetailsParameters = [
            Resource(
                id=volume_id,
                type=CBR_VOLUME_RESOURCE_TYPE
            )
        ]
        parametersCheckpoint = CheckpointParam(
            resource_details=listResourceDetailsParameters
        )
        checkpointbody = VaultBackup(
            parameters=parametersCheckpoint,
            vault_id=vault_id
        )
        request.body = VaultBackupReq(
            checkpoint=checkpointbody
        )
        client.create_checkpoint(request)
