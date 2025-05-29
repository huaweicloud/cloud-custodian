import logging

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkcbr.v1 import (
    CreateVaultRequest, BillingCreate,
    VaultCreate, VaultCreateReq,
    ResourceCreate, ListVaultRequest,
    AddVaultResourceRequest, VaultAddResourceReq,
    ListPoliciesRequest
)

from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo


log = logging.getLogger("custodian.huaweicloud.resources.cbr-protectable")


@resources.register('cbr-protectable')
class CbrProtectable(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'cbr-protectable'
        enum_spec = ('list_protectable', 'instances', 'offset')
        id = 'id'
        tag_resource_type = ''


@CbrProtectable.action_registry.register('associate_server_with_vault')
class CbrAssociateServerVault(HuaweiCloudBaseAction):
    '''
        Checks if the legally tagged servers is protected by a vault.
        if not, associate it with an existing vault.
        if the number of instances in all existing vaults has reached the upper limit,
        create a new vaults with periodical backup policy to protect them.
    : Example:

    .. code-block:: yaml

        policies:
          - name: cbr_protectable_associate_server_with_vault
            resource: huaweicloud.cbr-protectable
            filters:
              - and:
                - type: value
                  op: contains
                  key: detail.tags
                  value: "backup_policy=45Dd"
                - type: value
                  key: protectable.vault
                  value: empty
            actions:
              - type: associate_server_with_vault
                backup_policy_id: "bc715c62-f4ed-4fc0-9e78-ce43b9409a39"
                consistent_level: "crash_consistent"
                object_type: "server"
                protect_type: "backup"
                size: 100
                charging_mode: "post_paid"
                period_type: "year"
                period_num: 1
                is_auto_renew: true
                is_auto_pay: true
                name: "new_vault"

    '''
    max_count = 200  # the maximum count of instance of vault

    schema = type_schema('associate_server_with_vault',
                         backup_policy_id={'type': 'string'},
                         consistent_level={'type': 'string'},
                         object_type={'type': 'string'},
                         protect_type={'type': 'string'},
                         size={'type': 'integer'},
                         charging_mode={'type': 'string'},
                         period_type={'type': 'string'},
                         period_num={'type': 'integer'},
                         is_auto_renew={'type': 'boolean'},
                         is_auto_pay={'type': 'boolean'},
                         name={'type': 'string'},
                         )

    def process(self, resources):
        try:
            self.perform_action(resources)
        except exceptions.ClientRequestException as ex:
            res = len(resources)
            log.exception(
                f"Unable to submit action against the resource - {res} servers"
                f" RequestId: {ex.request_id}, Reason: {ex.error_msg}"
            )
            self.handle_exception(resources)
            raise
        return self.process_result(resources)

    def handle_exception(self, resources):
        self.failed_resources.extend(resources)

    def perform_action(self, resources):
        client = self.manager.get_client()
        try:
            request = ListVaultRequest()
            request.object_type = "server"
            response = client.list_vault(request)
            vaults = response.to_dict()['vaults']
        except exceptions.ClientRequestException as e:
            log.exception(
                f"Unable to list vaults. RequestId: {e.request_id}, Reason: {e.error_msg}"
            )

        try:
            request = ListPoliciesRequest()
            request.operation_type = "backup"
            if len(vaults) > 0:
                request.vault_id = vaults[0]['id']
            response = client.list_policies(request)
            policy_id = response.to_dict()['policies'][0]['id']
        except exceptions.ClientRequestException as e:
            log.exception(
                f"Unable to list policies. RequestId: {e.request_id}, Reason: {e.error_msg}"
            )
            raise

        vault_num = 0
        while resources and vault_num < len(vaults):
            try:
                request = AddVaultResourceRequest()
                request.vault_id = vaults[vault_num]['id']
                num_resource = len(vaults[vault_num]['resources'])
                space = self.max_count - num_resource
                if space <= 0:
                    log.info(
                        f"Unable to add resource to {vaults[vault_num]['id']}. "
                        f"Because the number of instances in the vault {vaults[vault_num]['id']}"
                        "has reached the upper limit."
                    )
                else:
                    listResourcesbody = []
                    for _ in range(min(space, len(resources))):
                        server = resources.pop()
                        listResourcesbody.append(
                            ResourceCreate(
                                id=server['id'],
                                type="OS::Nova::Server"
                            )
                        )
                    request.body = VaultAddResourceReq(
                        resources=listResourcesbody
                    )
                    response = client.add_vault_resource(request)
            except exceptions.ClientRequestException as e:
                log.info(
                    f"Unable to add resource to {vaults[vault_num]['id']}. "
                    f"RequestId: {e.request_id},"
                    f" Reason: {e.error_msg}"
                )
            vault_num += 1

        offset = 1
        while resources:
            log.info("All existing vaults are unable to be associated, "
                     "a new vault will be created.")
            server_list = []
            for _ in range(self.max_count):
                if resources:
                    server_list.append(resources.pop())
            valut_name = self.get_new_vault_name(vaults, offset)
            offset += 1
            response = self.create_new_vault(server_list, policy_id, valut_name)
        return response

    def create_new_vault(self, resources, policy_id, value_name):
        client = self.manager.get_client()
        try:
            request = CreateVaultRequest()
            listResourcesVault = []
            for server in resources:
                listResourcesVault.append(
                    ResourceCreate(
                        id=server['id'],
                        type="OS::Nova::Server"
                    )
                )
            billingVault = BillingCreate(
                consistent_level=self.data.get('consistent_level'),
                object_type=self.data.get('object_type'),
                protect_type=self.data.get('protect_type'),
                size=self.data.get('size'),
                charging_mode=self.data.get('charging_mode'),
                period_type=self.data.get('period_type'),
                period_num=self.data.get('period_num'),
                is_auto_renew=self.data.get('is_auto_renew'),
                is_auto_pay=self.data.get('is_auto_pay'),
            )
            if policy_id is None or policy_id == "":
                raise Exception("no backup_policy_id specified.")
            vaultbody = VaultCreate(
                backup_policy_id=self.data.get('backup_policy_id', policy_id),
                billing=billingVault,
                name=value_name,
                resources=listResourcesVault
            )
            request.body = VaultCreateReq(
                vault=vaultbody
            )
            response = client.create_vault(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        except Exception as e:
            log.error(f"{e}")
            raise
        return response

    def get_new_vault_name(self, vaults, offset):
        """根据输入的前缀，生成下一个存储库的名称"""
        valut_prefix = self.data.get('name')
        new_index = 0
        for vault in vaults:
            if str(vault['name']).startswith(valut_prefix):
                suffix = str(vault['name'])[len(valut_prefix):]
                if suffix.isdigit():
                    index = int(suffix)
                    if new_index <= index:
                        new_index = index
        new_index += offset
        valut_name = f"{valut_prefix}{new_index:04d}"
        log.info(f"create new vault name {valut_name}")
        return valut_name
