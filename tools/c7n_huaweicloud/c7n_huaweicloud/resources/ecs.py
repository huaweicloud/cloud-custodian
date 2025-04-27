import logging
import base64
import json
import zlib
import time
from typing import List
from concurrent.futures import as_completed

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkecs.v2 import (
    ShowJobRequest,
    ShowServerRequest,
    NovaShowFlavorExtraSpecsRequest,
    ServerId,
    BatchStartServersRequestBody,
    UpdateServerBlockDeviceOption,
    UpdateServerBlockDeviceRequest,
    UpdateServerBlockDeviceReq,
    BatchStartServersRequest,
    BatchStopServersRequestBody,
    BatchStopServersRequest,
    BatchRebootServersRequestBody,
    BatchRebootServersRequest,
    NovaAddSecurityGroupOption,
    NovaAssociateSecurityGroupRequestBody,
    NovaAssociateSecurityGroupRequest,
    NovaRemoveSecurityGroupOption,
    NovaDisassociateSecurityGroupRequest,
    NovaDisassociateSecurityGroupRequestBody,
    ResizeServerExtendParam,
    CpuOptions,
    ResizePrePaidServerOption,
    ResizeServerRequest,
    ResizeServerRequestBody,
    UpdateServerMetadataRequestBody,
    UpdateServerMetadataRequest,
    DeleteServersRequestBody,
    DeleteServersRequest,
    DeleteServerMetadataRequest
)
from huaweicloudsdkims.v2 import (
    CreateWholeImageRequestBody,
    CreateWholeImageRequest,
    ShowJobProgressRequest,
    ListImagesRequest,
)
from huaweicloudsdkcbr.v1 import (
    ResourceCreate,
    ShowVaultRequest,
    ShowOpLogRequest,
    CreateCheckpointRequest,
    ListOpLogsRequest,
    Resource,
    VaultAddResourceReq,
    CheckpointParam,
    VaultBackup,
    AddVaultResourceRequest,
    VaultBackupReq,
)

from c7n import utils
from c7n.utils import type_schema, local_session
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n.filters import AgeFilter, ValueFilter, Filter, OPERATORS
from dateutil.parser import parse

log = logging.getLogger("custodian.huaweicloud.resources.ecs")


@resources.register("ecs")
class Ecs(QueryResourceManager):
    class resource_type(TypeInfo):
        service = "ecs"
        enum_spec = ("list_servers_details", "servers", "page")
        id = "id"
        tag_resource_type = "ecs"


@Ecs.action_registry.register("fetch-job-status")
class FetchJobStatus(HuaweiCloudBaseAction):
    """Fetch An Asyn Job Status.

    :Example:

    .. code-block:: yaml

        policies:
          - name: fetch-job-status
            resource: huaweicloud.ecs
            actions:
              - type: fetch-job-status
                job_id: "asyn job id"
    """

    schema = type_schema(
        "fetch-job-status", job_id={"type": "string"}, required=("job_id",)
    )

    def process(self, resources):
        job_id = self.data.get("job_id")
        client = self.manager.get_client()
        request = ShowJobRequest(job_id=job_id)
        try:
            response = client.show_job(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return json.dumps(response.to_dict())

    def perform_action(self, resource):
        return super().perform_action(resource)


@Ecs.action_registry.register("instance-start")
class EcsStart(HuaweiCloudBaseAction):
    """Start ECS Instances.

    :Example:

    .. code-block:: yaml

        policies:
          - name: start-ecs-server
            resource: huaweicloud.ecs
            filters:
              - type: value
                key: id
                value: "your server id"
            actions:
              - instance-start
    """

    valid_origin_states = ("SHUTOFF",)
    schema = type_schema("instance-start")

    def process(self, resources):
        if len(resources) > 1000:
            log.error("The most instances to start is 1000")
            return
        client = self.manager.get_client()
        instances = self.filter_resources(resources, "status", self.valid_origin_states)
        if not instances:
            log.warning("No instance need start")
            return None
        request = self.init_request(instances)
        try:
            response = client.batch_start_servers(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return json.dumps(response.to_dict())

    def init_request(self, instances):
        serverIds: List[ServerId] = []
        for r in instances:
            serverIds.append(ServerId(id=r["id"]))
        options = {"servers": serverIds}
        requestBody = BatchStartServersRequestBody(os_start=options)
        request = BatchStartServersRequest(body=requestBody)
        return request

    def perform_action(self, resource):
        return super().perform_action(resource)


@Ecs.action_registry.register("instance-stop")
class EcsStop(HuaweiCloudBaseAction):
    """Stop Ecs Instances.

    :Example:

    .. code-block:: yaml

        policies:
          - name: stop-ecs-server
            resource: huaweicloud.ecs
            filters:
              - type: value
                key: id
                value: "your server id"
            actions:
              - type: instance-stop
                mode: "SOFT"
    """

    valid_origin_states = ("ACTIVE",)
    schema = type_schema("instance-stop", mode={"type": "string"})

    def process(self, resources):
        if len(resources) > 1000:
            log.error("The most instances to stop is 1000")
            return
        client = self.manager.get_client()
        instances = self.filter_resources(resources, "status", self.valid_origin_states)
        if not instances:
            log.warning("No instance need stop")
            return None
        request = self.init_request(instances)
        try:
            response = client.batch_stop_servers(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return json.dumps(response.to_dict())

    def init_request(self, resources):
        serverIds: List[ServerId] = []
        for r in resources:
            serverIds.append(ServerId(id=r["id"]))
        options = {"servers": serverIds, "type": self.data.get("mode", "SOFT")}
        requestBody = BatchStopServersRequestBody(os_stop=options)
        request = BatchStopServersRequest(body=requestBody)
        return request

    def perform_action(self, resource):
        return super().perform_action(resource)


@Ecs.action_registry.register("instance-reboot")
class EcsReboot(HuaweiCloudBaseAction):
    """Reboot Ecs Instances.

    :Example:

    .. code-block:: yaml

        policies:
          - name: reboot-ecs-server
            resource: huaweicloud.ecs
            filters:
              - type: value
                key: id
                value: "your server id"
            actions:
              - type: instance-reboot
                mode: "SOFT"
    """

    valid_origin_states = ("ACTIVE",)
    schema = type_schema("instance-reboot", mode={"type": "string"})

    def process(self, resources):
        if len(resources) > 1000:
            log.error("The most instances to reboot is 1000")
            return
        client = self.manager.get_client()
        instances = self.filter_resources(resources, "status", self.valid_origin_states)
        if not instances:
            log.warning("No instance need reboot")
            return None
        request = self.init_request(instances)
        try:
            response = client.batch_reboot_servers(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return json.dumps(response.to_dict())

    def init_request(self, resources):
        serverIds: List[ServerId] = []
        for r in resources:
            serverIds.append(ServerId(id=r["id"]))
        options = {"servers": serverIds, "type": self.data.get("mode", "SOFT")}
        requestBody = BatchRebootServersRequestBody(reboot=options)
        request = BatchRebootServersRequest(body=requestBody)
        return request

    def perform_action(self, resource):
        return super().perform_action(resource)


@Ecs.action_registry.register("instance-terminate")
class EcsTerminate(HuaweiCloudBaseAction):
    """Terminate Ecs Instances.

    :Example:

    .. code-block:: yaml

        policies:
          - name: terminate-ecs-server
            resource: huaweicloud.ecs
            filters:
              - type: value
                key: id
                value: "your instance id"
            actions:
              - instance-terminate
    """

    schema = type_schema("instance-terminate", delete_publicip={'type': 'boolean'},
                         delete_volume={'type': 'boolean'})

    def process(self, resources):
        client = self.manager.get_client()
        serverIds: List[ServerId] = []
        for r in resources:
            serverIds.append(ServerId(id=r["id"]))
        delete_publicip = self.data.get('delete_publicip', False)
        delete_volume = self.data.get('delete_volume', False)
        requestBody = DeleteServersRequestBody(delete_publicip=delete_publicip,
                                               delete_volume=delete_volume, servers=serverIds)
        request = DeleteServersRequest(body=requestBody)
        try:
            response = client.delete_servers(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return json.dumps(response.to_dict())

    def perform_action(self, resource):
        pass


@Ecs.action_registry.register("instance-add-security-groups")
class AddSecurityGroup(HuaweiCloudBaseAction):
    """Add Security Groups For An Ecs Instance.

    :Example:

    .. code-block:: yaml

        policies:
          - name: add-security-groups
            resource: huaweicloud.ecs
            filters:
              - type: value
                key: id
                value: "your server id"
            actions:
              - instance-add-security-groups
    """

    schema = type_schema(
        "instance-add-security-groups", name={"type": "string"}, required=("name",)
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        name = self.data.get("name", None)
        if name is None:
            log.error("security group name is None")
            return None
        option = NovaAddSecurityGroupOption(name=name)
        requestBody = NovaAssociateSecurityGroupRequestBody(add_security_group=option)
        request = NovaAssociateSecurityGroupRequest(
            server_id=resource["id"], body=requestBody
        )
        try:
            response = client.nova_associate_security_group(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response


@Ecs.action_registry.register("instance-delete-security-groups")
class DeleteSecurityGroup(HuaweiCloudBaseAction):
    """Deletes Security Groups For An Ecs Instance.

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-security-groups
            resource: huaweicloud.ecs
            filters:
              - type: value
                key: id
                value: "your server id"
            actions:
              - type: instance-delete-security-groups
                name: "test_group"
    """

    schema = type_schema("instance-delete-security-groups", name={"type": "string"})

    def perform_action(self, resource):
        client = self.manager.get_client()
        name = self.data.get("name", None)
        if name is None:
            log.error("security group name is None")
            return None
        option = NovaRemoveSecurityGroupOption(name=name)
        requestBody = NovaDisassociateSecurityGroupRequestBody(
            remove_security_group=option
        )
        request = NovaDisassociateSecurityGroupRequest(
            server_id=resource["id"], body=requestBody
        )
        try:
            response = client.nova_disassociate_security_group(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response


@Ecs.action_registry.register("instance-resize")
class Resize(HuaweiCloudBaseAction):
    """Resize An Ecs Instance Flavor.

    :Example:

    .. code-block:: yaml

        policies:
          - name: resize
            resource: huaweicloud.ecs
            filters:
              - type: value
                key: id
                value: "bac642b0-a9ca-4a13-b6b9-9e41b35905b6"
            actions:
              - type: instance-resize
                flavor_ref: "x1.1u.4g"
                mode: "withStopServer"
    """

    schema = type_schema(
        "instance-resize",
        flavor_ref={"type": "string"},
        dedicated_host_id={"type": "string"},
        is_auto_pay={"type": "string"},
        mode={"type": "string"},
        hwcpu_threads={"type": "int"},
        dry_run={"type": "boolean"},
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        extendParam = ResizeServerExtendParam(
            is_auto_pay=self.data.get("is_auto_pay", None)
        )
        cpuOptions = CpuOptions(hwcpu_threads=self.data.get("hwcpu_threads", None))
        flavorRef = self.data.get("flavor_ref", None)
        dedicatedHostId = self.data.get("dedicated_host_id", None)
        mode = self.data.get("mode", None)
        if flavorRef is None:
            log.error("flavor_ref con not be None")
            return None
        option = ResizePrePaidServerOption(
            flavor_ref=flavorRef,
            dedicated_host_id=dedicatedHostId,
            extendparam=extendParam,
            mode=mode,
            cpu_options=cpuOptions,
        )
        requestBody = ResizeServerRequestBody(
            resize=option, dry_run=self.data.get("dry_run", None)
        )
        request = ResizeServerRequest(server_id=resource["id"], body=requestBody)
        try:
            response = client.resize_server(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response


@Ecs.action_registry.register("set-instance-profile")
class SetInstanceProfile(HuaweiCloudBaseAction):
    """Set Profile(metadata) For An Ecs Instance Flavor.

    :Example:

    .. code-block:: yaml

        policies:
          - name: set-instance-profile
            resource: huaweicloud.ecs
            filters:
              - type: value
                key: id
                value: "bac642b0-a9ca-4a13-b6b9-9e41b35905b6"
            actions:
              - type: set-instance-profile
                metadata:
                  key: value
    """

    schema = type_schema("set-instance-profile", metadata={"type": "object"})

    def perform_action(self, resource):
        client = self.manager.get_client()
        metadata = self.data.get("metadata", None)
        requestBody = UpdateServerMetadataRequestBody(metadata=metadata)
        request = UpdateServerMetadataRequest(
            server_id=resource["id"], body=requestBody
        )
        try:
            response = client.update_server_metadata(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response


@Ecs.action_registry.register("instance-whole-image")
class InstanceWholeImage(HuaweiCloudBaseAction):
    """Create Whole Image Backup For An ECS Instance.

    - `vault_id` CBR vault_id the instance was associated
    - `name` whole image name

    :Example:

    .. code-block:: yaml

       policies:
         - name: instance-whole-image
           resource: huaweicloud.ecs
           actions:
             - type: instance-whole-image
               name: "wholeImage"
               vault_id: "your CBR vault id"
    """

    schema = type_schema(
        "instance-whole-image",
        name={"type": "string"},
        vault_id={"type": "string"},
        required=("name", "vault_id"),
    )
    batch_size = 1

    def perform_action(self, resource):
        return super().perform_action(resource)

    def process(self, resources):
        ims_client = local_session(self.manager.session_factory).client("ims")
        results = []
        with self.executor_factory(max_workers=5) as w:
            futures = {}
            for instance_set in utils.chunks(resources, self.batch_size):
                futures[w.submit(self.create_whole_image, instance_set[0], ims_client)] = (
                    instance_set
                )
            for f in as_completed(futures):
                if f.exception():
                    self.log.error(
                        "Error creating whole image on instance set %s", f.exception()
                    )
                results.append(f.result())
        return results

    def create_whole_image(self, r, ims_client):
        requestBody = CreateWholeImageRequestBody(
                name=self.data.get("name"),
                instance_id=r['id'],
                vault_id=self.data.get("vault_id"),
            )
        request = CreateWholeImageRequest(body=requestBody)
        try:
            response = ims_client.create_whole_image(request)
            if response.status_code != 200:
                log.error(
                    "create whole image for instance %s fail"
                    % self.data.get("instance_id")
                )
                return False
            return self.wait_backup(response.job_id, ims_client)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            return False

    def wait_backup(self, job_id, ims_client):
        while True:
            time.sleep(5)
            status = self.fetch_ims_job_status(job_id, ims_client)
            if status == "SUCCESS":
                return True
            elif status == "RUNNING" or status == "INIT":
                log.info("waitting for create whole image")
                continue
            else:
                log.error("waitting for create whole image fail")
                return False

    def fetch_ims_job_status(self, job_id, ims_client):
        request = ShowJobProgressRequest(job_id=job_id)
        try:
            response = ims_client.show_job_progress(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response.status


@Ecs.action_registry.register("instance-snapshot")
class InstanceSnapshot(HuaweiCloudBaseAction):
    """CBR Backup The Volumes Attached To An ECS Instance, you should add instance to an vault.

    - `vault_id` CBR vault_id the instance was associated
    - `incremental` false : full server volumes backup
                    true : incremental of server volumes backup

    :Example:

    .. code-block:: yaml

       policies:
         - name: instance-snapshot
           resource: huaweicloud.ecs
           actions:
             - type: instance-snapshot
               incremental: false
               vault_id: "c789a0e1-9207-46c7-b539-39dac13bce51"
    """

    schema = type_schema(
        "instance-snapshot",
        vault_id={"type": "string"},
        incremental={"type": "boolean"},
    )
    batch_size = 1

    def perform_action(self, resource):
        return super().perform_action(resource)

    def process(self, resources):
        if self.data.get("vault_id", None) is None:
            log.error("vault_id is required.")
            return []
        cbr_backup_client = local_session(self.manager.session_factory).client(
            "cbr-backup"
        )
        vaults = self.list_vault()
        vaults_resource_ids = self.fetch_vaults_resource_ids(vaults)
        response = self.back_up(resources, vaults_resource_ids, cbr_backup_client)
        return response

    def back_up(self, resources, vaults_resource_ids, cbr_backup_client):
        results = []
        with self.executor_factory(max_workers=5) as w:
            futures = {}
            for instance_set in utils.chunks(resources, self.batch_size):
                futures[w.submit(self.snapshot, instance_set[0],
                                 vaults_resource_ids, cbr_backup_client)] = (
                    instance_set
                )
            for f in as_completed(futures):
                if f.exception():
                    self.log.error(
                        "Error creating instance snapshot on instance set %s", f.exception()
                    )
                results.append(f.result())
        return results

    def snapshot(self, r, vaults_resource_ids, cbr_backup_client):
        server_id = r["id"]
        input_vault_id = self.data.get("vault_id", None)
        if input_vault_id is not None:
            if server_id not in vaults_resource_ids:
                log.warning("server %s do not related an vault." % server_id)
                resource = [ResourceCreate(id=server_id, type="OS::Nova::Server")]
                add_resource_response = self.add_vault_resource(
                    input_vault_id, resource, cbr_backup_client
                )
                if add_resource_response.status_code != 200:
                    log.error("add instance %s to vault error" % server_id)
                    return False
                return self.checkpoint_and_wait(
                    r, input_vault_id, server_id, cbr_backup_client
                )
            else:
                vault_id = vaults_resource_ids[server_id]
                if vault_id != input_vault_id:
                    log.error("error vault id for instance %s" % server_id)
                    return False
                else:
                    return self.checkpoint_and_wait(
                        r, vault_id, server_id, cbr_backup_client
                    )
        else:
            if server_id not in vaults_resource_ids:
                log.error("server %s do not related an vault." % server_id)
                return False
            else:
                vault_id = vaults_resource_ids[server_id]
                return self.checkpoint_and_wait(
                        r, vault_id, server_id, cbr_backup_client
                    )

    def wait_backup(self, vault_id, resource_id, cbr_client):
        while True:
            response = self.list_op_log(resource_id, vault_id, cbr_client)
            op_logs = response.operation_logs
            if len(op_logs) != 0:
                log.info("waitting for create instance snapshot")
                time.sleep(5)
                continue
            return True

    def checkpoint_and_wait(self, r, vault_id, server_id, cbr_client):
        checkpoint_response = self.create_checkpoint_for_instance(
            r, vault_id, cbr_client
        )
        if checkpoint_response.status_code != 200:
            log.error("instance %s backup error" % server_id)
            return False
        return self.wait_backup(vault_id, server_id, cbr_client)

    def create_checkpoint_for_instance(self, r, vault_id, cbr_client):
        resource_details = [Resource(id=r["id"], type="OS::Nova::Server")]
        params = CheckpointParam(
            resource_details=resource_details,
            incremental=self.data.get("incremental", True),
        )
        backup = VaultBackup(vault_id=vault_id, parameters=params)
        try:
            response = self.create_checkpoint(cbr_client, backup)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response

    def fetch_vaults_resource_ids(self, vaults):
        vaults_resource_ids = {}
        for vault in vaults:
            resources = vault["resources"]
            for r in resources:
                if r["protect_status"] == "available":
                    vaults_resource_ids.setdefault(r["id"], vault["id"])
        return vaults_resource_ids

    def list_vault(self):
        try:
            response = self.manager.get_resource_manager(
                "huaweicloud.cbr-vault"
            ).resources()
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response

    def show_vault(self, cbr_client, vault_id):
        request = ShowVaultRequest(vault_id=vault_id)
        try:
            response = cbr_client.show_vault(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response

    def add_vault_resource(self, vault_id, resources: ResourceCreate, cbr_client):
        requestBody = VaultAddResourceReq(resources=resources)
        request = AddVaultResourceRequest(vault_id=vault_id, body=requestBody)
        try:
            response = cbr_client.add_vault_resource(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response

    def show_op_log_by_op_log_id(self, cbr_client, op_log_id):
        request = ShowOpLogRequest(operation_log_id=op_log_id)
        try:
            response = cbr_client.show_op_log(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response

    def list_op_log(self, resource_id, vault_id, cbr_client):
        request = ListOpLogsRequest(
            status="running", vault_id=vault_id, resource_id=resource_id
        )
        try:
            response = cbr_client.list_op_logs(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response

    def create_checkpoint(self, cbr_client, backup: VaultBackup):
        requestBody = VaultBackupReq(checkpoint=backup)
        request = CreateCheckpointRequest(body=requestBody)
        try:
            response = cbr_client.create_checkpoint(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response

    def vault_add_resource(self, vault_id, server_id, cbr_client):
        resource = ResourceCreate(id=server_id, type="OS::Nova::Server")
        requestBody = VaultAddResourceReq(resources=resource)
        request = AddVaultResourceRequest(vault_id=vault_id, body=requestBody)
        try:
            response = cbr_client.add_vault_resource(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response


@Ecs.action_registry.register("instance-volumes-corrections")
class InstanceVolumesCorrections(HuaweiCloudBaseAction):
    """Correction Instances Volumes delete_on_termination To True.

    :Example:

    .. code-block:: yaml

       policies:
         - name: instance-volumes-corrections
           resource: huaweicloud.ecs
           filters:
             - type: instance-volumes-not-compliance
           actions:
             - type: instance-volumes-corrections
    """

    schema = type_schema("instance-volumes-corrections")

    def perform_action(self, resource):
        results = []
        client = self.manager.get_client()
        volumes = list(resource["os-extended-volumes:volumes_attached"])
        for volume in volumes:
            if volume["delete_on_termination"] == "True":
                continue
            option = UpdateServerBlockDeviceOption(delete_on_termination=True)
            requestBody = UpdateServerBlockDeviceReq(block_device=option)
            request = UpdateServerBlockDeviceRequest(
                server_id=resource["id"], volume_id=volume["id"], body=requestBody
            )
            try:
                response = client.update_server_block_device(request)
                results.append(response)
            except exceptions.ClientRequestException as e:
                log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
                continue
        return results


@Ecs.action_registry.register("instance-delete-metadata-key")
class InstanceDeleteMetadataKey(HuaweiCloudBaseAction):
    """Delete Instance metadata key

    :Example:

    .. code-block:: yaml

        policies:
        - name: instance-delete-metadata-key
            resource: huaweicloud.ecs
            filters:
            - type: value
                key: id
                value: "bac642b0-a9ca-4a13-b6b9-9e41b35905b6"
            actions:
            - type: instance-delete-metadata-key
                key: "agency_name"

    """

    schema = type_schema("instance-delete-metadata-key", key={"type": "string"})

    def process(self, resources):
        key = self.data.get("key", None)
        if key is None:
            log.error("key is required")
            return []
        results = []
        client = self.manager.get_client()
        for resource in resources:
            request = DeleteServerMetadataRequest(key=key, server_id=resource['id'])
            try:
                response = client.delete_server_metadata(request)
            except exceptions.ClientRequestException as e:
                log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
                continue
            results.append(json.dumps(response.to_dict()))
        return results

    def perform_action(self, resource):
        pass
# ---------------------------ECS Filter-------------------------------------#


@Ecs.filter_registry.register("instance-age")
class EcsInstanceAgeFilter(AgeFilter):
    """ECS Instance Age Filter: greater-than or less-than threshold date

    :Example:

    .. code-block:: yaml

        policies:
          - name: ecs-instances-age
            resource: huaweicloud.ecs
            filters:
              - type: instance-age
                op: ge
                days: 1
    """

    date_attribute = "created"

    schema = type_schema(
        "instance-age",
        op={"$ref": "#/definitions/filters_common/comparison_operators"},
        days={"type": "number"},
        hours={"type": "number"},
        minutes={"type": "number"},
    )


@Ecs.filter_registry.register("instance-uptime")
class EcsInstanceUptimeFilter(AgeFilter):
    """Automatically filter resources older or younger than a given date.

    :Example:

    .. code-block:: yaml

        policies:
          - name: ecs-instances-age
            resource: huaweicloud.ecs
            filters:
              - type: instance-uptime
                op: ge
                days: 1
    """

    date_attribute = "created"

    schema = type_schema(
        "instance-uptime",
        op={"$ref": "#/definitions/filters_common/comparison_operators"},
        days={"type": "number"},
    )


@Ecs.filter_registry.register("instance-attribute")
class InstanceAttributeFilter(ValueFilter):
    """ECS Instance Value Filter on a given instance attribute.

    :Example:

    .. code-block:: yaml

        policies:
          - name: ecs-instances-attribute
            resource: huaweicloud.ecs
            filters:
              - type: instance-attribute
                attribute: OS-EXT-SRV-ATTR:user_data
                key: "Value"
                op: regex
                value: (?smi).*user=
    """

    valid_attrs = (
        "flavorId",
        "OS-EXT-SRV-ATTR:user_data",
        "OS-EXT-SRV-ATTR:root_device_name",
    )

    schema = type_schema(
        "instance-attribute",
        rinherit=ValueFilter.schema,
        attribute={"enum": valid_attrs},
        required=("attribute",),
    )
    schema_alias = False

    def process(self, resources, event=None):
        attribute = self.data["attribute"]
        self.get_instance_attribute(resources, attribute)
        return [
            resource
            for resource in resources
            if self.match(resource["c7n:attribute-%s" % attribute])
        ]

    def get_instance_attribute(self, resources, attribute):
        for resource in resources:
            userData = resource.get("OS-EXT-SRV-ATTR:user_data", "")
            flavorId = resource["flavor"]["id"]
            rootDeviceName = ["OS-EXT-SRV-ATTR:root_device_name"]
            attributes = {
                "OS-EXT-SRV-ATTR:user_data": {"Value": deserialize_user_data(userData)},
                "flavorId": {"Value": flavorId},
                "OS-EXT-SRV-ATTR:root_device_name": {"Value": rootDeviceName},
            }
            resource["c7n:attribute-%s" % attribute] = attributes[attribute]


class InstanceImageBase:

    def prefetch_instance_images(self, instances):
        self.image_map = self.get_local_image_mapping(instances)

    def get_base_image_mapping(self, image_ids):
        ims_client = local_session(self.manager.session_factory).client("ims")
        request = ListImagesRequest(id=image_ids, limit=1000)
        return {i.id: i for i in ims_client.list_images(request).images}

    def get_instance_image_created_at(self, instance):
        return instance["image:created_at"]

    def get_local_image_mapping(self, instances):
        image_ids = ",".join(
            list(set(item["metadata"]["metering.image_id"] for item in instances))
        )
        base_image_map = self.get_base_image_mapping(image_ids)
        for r in instances:
            if r["metadata"]["metering.image_id"] in base_image_map.keys():
                r["image:created_at"] = base_image_map[
                    r["metadata"]["metering.image_id"]
                ].created_at
            else:
                r["image:created_at"] = "2000-01-01T01:01:01.000Z"
        return instances


@Ecs.filter_registry.register("instance-image-age")
class ImageAgeFilter(AgeFilter, InstanceImageBase):
    """ECS Image Age Filter

    Filters ECS instances based on the age of their image (in days)

    :Example:

    .. code-block:: yaml

        policies:
          - name: instance-image-age
            resource: huaweicloud.ecs
            filters:
              - type: instance-image-age
                op: ge
                days: 14400
    """

    date_attribute = "created_at"

    schema = type_schema(
        "instance-image-age",
        op={"$ref": "#/definitions/filters_common/comparison_operators"},
        days={"type": "number"},
    )

    def process(self, resources, event=None):
        self.prefetch_instance_images(resources)
        return super(ImageAgeFilter, self).process(resources, event)

    def get_resource_date(self, i):
        image = self.get_instance_image_created_at(i)
        return parse(image)


@Ecs.filter_registry.register("instance-image")
class InstanceImageFilter(ValueFilter, InstanceImageBase):
    """ECS Image filter

    :Example:

    .. code-block:: yaml

        policies:
          - name: instance-image
            resource: huaweicloud.ecs
            filters:
              - type: instance-image
    """

    schema = type_schema("instance-image", rinherit=ValueFilter.schema)
    schema_alias = False

    def process(self, resources, event=None):
        results = []
        image_ids = ",".join(
            list(item["metadata"]["metering.image_id"] for item in resources)
        )
        base_image_map = self.get_base_image_mapping(image_ids)
        for r in resources:
            if r["metadata"]["metering.image_id"] in base_image_map.keys():
                results.append(r)
        return results


@Ecs.filter_registry.register("ephemeral")
class InstanceEphemeralFilter(Filter):
    """ECS instances with ephemeral storage

    Filters ECS instances that have ephemeral storage

    :Example:

    .. code-block:: yaml

        policies:
          - name: ephemeral
            resource: huaweicloud.ecs
            filters:
              - type: ephemeral

    """

    schema = type_schema("ephemeral")

    def __call__(self, i):
        return self.is_ephemeral(i)

    def is_ephemeral(self, i):
        performancetype = self.get_resource_flavor_performancetype(i["flavor"]["id"])
        if performancetype in ("highio", "diskintensive"):
            return True
        return False

    def get_resource_flavor_performancetype(self, flavorId):
        request = NovaShowFlavorExtraSpecsRequest(flavor_id=flavorId)
        client = self.manager.get_client()
        try:
            response = client.nova_show_flavor_extra_specs(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response.extra_specs["ecs:performancetype"]


def deserialize_user_data(user_data):
    data = base64.b64decode(user_data)
    # try raw and compressed
    try:
        return data.decode("utf8")
    except UnicodeDecodeError:
        return zlib.decompress(data, 16).decode("utf8")


@Ecs.filter_registry.register("instance-user-data")
class InstanceUserData(ValueFilter):
    """Filter on ECS instances which have matching userdata.
    Note: It is highly recommended to use regexes with the ?sm flags, since Custodian
    uses re.match() and userdata spans multiple lines.

        :example:

        .. code-block:: yaml

            policies:
              - name: ecs-instance-user-data
                resource: huaweicloud.ecs
                filters:
                  - type: instance-user-data
                    op: regex
                    value: (?smi).*user=
                actions:
                  - instance-stop
    """

    schema = type_schema("instance-user-data", rinherit=ValueFilter.schema)
    schema_alias = False
    batch_size = 50
    annotation = "OS-EXT-SRV-ATTR:user_data"

    def __init__(self, data, manager):
        super(InstanceUserData, self).__init__(data, manager)
        self.data["key"] = "OS-EXT-SRV-ATTR:user_data"

    def process(self, resources, event=None):
        results = []
        with self.executor_factory(max_workers=3) as w:
            futures = {}
            for instance_set in utils.chunks(resources, self.batch_size):
                futures[w.submit(self.process_instance_user_data, instance_set)] = (
                    instance_set
                )

            for f in as_completed(futures):
                if f.exception():
                    self.log.error(
                        "Error processing userdata on instance set %s", f.exception()
                    )
                results.extend(f.result())
        return results

    def process_instance_user_data(self, resources):
        results = []
        for r in resources:
            try:
                result = self.get_instance_info_detail(r["id"])
            except exceptions.ClientRequestException as e:
                log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
                raise
            if result is None:
                r[self.annotation] = None
            else:
                r[self.annotation] = deserialize_user_data(result)
            if self.match(r):
                results.append(r)
        return results

    def get_instance_info_detail(self, serverId):
        request = ShowServerRequest(server_id=serverId)
        client = self.manager.get_client()
        try:
            response = client.show_server(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response.server.os_ext_srv_att_ruser_data


@Ecs.filter_registry.register("instance-evs")
class InstanceEvs(ValueFilter):
    """ECS instance with EVS volume.

    Filter ECS instances with EVS storage devices, not ephemeral

    :Example:

    .. code-block:: yaml

       policies:
         - name: instance-evs
           resource: huaweicloud.ecs
           filters:
             - type: instance-evs
               key: encrypted
               op: eq
               value: false
    """

    schema = type_schema(
        "instance-evs",
        rinherit=ValueFilter.schema,
        **{"skip-devices": {"type": "array", "items": {"type": "string"}}}
    )
    schema_alias = False

    def process(self, resources, event=None):
        self.volume_map = self.get_volume_mapping(resources)
        self.skip = self.data.get("skip-devices", [])
        self.operator = self.data.get("operator", "or") == "or" and any or all
        return list(filter(self, resources))

    def get_volume_mapping(self, resources):
        volume_map = {}
        evsResources = self.manager.get_resource_manager(
            "huaweicloud.evs-volume"
        ).resources()
        for resource in resources:
            for evs in evsResources:
                evsServerIds = list(item["server_id"] for item in evs["attachments"])
                if resource["id"] in evsServerIds:
                    volume_map.setdefault(resource["id"], evs)
                    break
        return volume_map

    def __call__(self, i):
        volumes = self.volume_map.get(i["id"])
        if not volumes:
            return False
        if self.skip:
            for v in list(volumes):
                for a in v.get("id", []):
                    if a["id"] in self.skip:
                        volumes.remove(v)
        return self.match(volumes)


@Ecs.filter_registry.register("instance-vpc")
class InstanceVpc(Filter):
    """ECS instance with VPC.

    Filter ECS instances with VPC id

    :Example:

    .. code-block:: yaml

       policies:
         - name: instance-vpc
           resource: huaweicloud.ecs
           filters:
             - type: instance-vpc
    """

    schema = type_schema("instance-vpc")
    schema_alias = False

    def process(self, resources, event=None):
        return self.get_vpcs(resources)

    def get_vpcs(self, resources):
        vpcs = self.manager.get_resource_manager("huaweicloud.vpc").resources()
        vpc_ids = {vpc["id"] for vpc in vpcs}
        return [
            resource for resource in resources
            if resource["metadata"]["vpc_id"] in vpc_ids
        ]


@Ecs.filter_registry.register("instance-volumes-not-compliance")
class InstanceVolumesNotCompliance(Filter):
    """ECS instance with volumes delete_on_termination is false.

    :Example:

    .. code-block:: yaml

       policies:
         - name: instance-volumes-not-compliance
           resource: huaweicloud.ecs
           filters:
             - type: instance-volumes-not-compliance
    """

    schema = type_schema("instance-volumes-not-compliance")

    def process(self, resources, event=None):
        results = []
        for resource in resources:
            volumes = list(resource["os-extended-volumes:volumes_attached"])
            for volume in volumes:
                if volume["delete_on_termination"] == "False":
                    results.append(resource)
                    break
        return results


@Ecs.filter_registry.register("instance-image-not-compliance")
class InstanceImageNotCompliance(Filter):
    """ECS instance with image is not compliance.

    :Example:

    .. code-block:: yaml

       policies:
         - name: instance-image-not-compliance
           resource: huaweicloud.ecs
           filters:
             - type: instance-image-not-compliance
               image_ids: ['your instance id']
               obs_url: ""
    """

    schema = type_schema("instance-image-not-compliance",
                         image_ids={"type": "array"},
                         obs_url={'type': 'string'})

    def process(self, resources, event=None):
        results = []
        image_ids = self.data.get("image_ids", [])
        obs_url = self.data.get('obs_url', None)
        obs_client = local_session(self.manager.session_factory).client("obs")
        if not image_ids and obs_url is None:
            log.error("image_ids or obs_url is required")
            return []
        if obs_url is not None:
            # 1. 提取第一个变量：从 "https://" 到最后一个 "obs" 的部分
            protocol_end = len("https://")
            # 去除协议头后的完整路径
            path_without_protocol = obs_url[protocol_end:]
            obs_bucket_name = self.get_obs_name(path_without_protocol)
            obs_server = self.get_obs_server(path_without_protocol)
            obs_file = self.get_file_path(path_without_protocol)
            obs_client.server = obs_server
            try:
                resp = obs_client.getObject(bucketName=obs_bucket_name,
                                            objectKey=obs_file,
                                            loadStreamInMemory=True)
                if resp.status < 300:
                    ids = json.loads(resp.body.buffer)['image_ids']
                    image_ids.extend(ids)
                    image_ids = list(set(image_ids))
                else:
                    log.error(f"get obs object failed: {resp.errorCode}, {resp.errorMessage}")
                    return []
            except exceptions.ClientRequestException as e:
                log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
                raise
        instance_image_map = {}
        for r in resources:
            instance_image_map.setdefault(
                r["metadata"]["metering.image_id"], []
            ).append(r)
        for id in instance_image_map.keys():
            if id not in image_ids:
                results.extend(instance_image_map[id])
        return results

    def get_obs_name(self, obs_url):
        # 找到最后一个 ".obs" 的索引位置
        last_obs_index = obs_url.rfind(".obs")
        return obs_url[:last_obs_index]

    def get_obs_server(self, obs_url):
        # 找到最后一个 ".obs" 的索引位置
        last_obs_index = obs_url.rfind(".obs")
        remaining_after_obs = obs_url[last_obs_index:]
        split_res = remaining_after_obs.split("/", 1)
        return split_res[0].lstrip(".")

    def get_file_path(self, obs_url):
        # 找到最后一个 ".obs" 的索引位置
        last_obs_index = obs_url.rfind(".obs")
        remaining_after_obs = obs_url[last_obs_index:]
        split_res = remaining_after_obs.split("/", 1)
        return split_res[1]


@Ecs.filter_registry.register("instance-tag")
class InstanceTag(ValueFilter):
    """ECS instance tag filter.

    :Example:

    .. code-block:: yaml

       policies:
         - name: instance-tag
           resource: huaweicloud.ecs
           filters:
             - type: instance-tag
               key: "CCE-Cluster-ID"
    """
    OPERATORS.setdefault("not-contains-all", None)
    OPERATORS.setdefault("contains-all", None)
    schema = type_schema("instance-tag",
                         op={'enum': list(OPERATORS.keys())},
                         rinherit=ValueFilter.schema)
    schema_alias = False
    annotation = "tags_map"

    def __init__(self, data, manager=None):
        super(InstanceTag, self).__init__(data, manager)
        self.data["key"] = "tags_map"

    def process(self, resources, event=None):
        results = []
        for resource in resources:
            tags = resource["tags"]
            tags_map = {}
            for tag in tags:
                map_key, sep, map_value = tag.partition('=')
                tags_map[map_key] = map_value if sep else ''
            resource["tags_map"] = tags_map
            resource[self.annotation] = tags_map
            op = self.data.get("op")
            if op == "not-contains-all":
                if set(self.data.get("value")).issubset(tags_map.keys()) is False:
                    results.append(resource)
                continue
            elif op == "contains-all":
                if set(self.data.get("value")).issubset(tags_map.keys()) is True:
                    results.append(resource)
                continue
            else:
                if self.match(resource):
                    results.append(resource)
        return results
