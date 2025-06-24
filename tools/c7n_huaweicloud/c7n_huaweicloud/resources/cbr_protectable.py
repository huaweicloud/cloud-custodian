import logging
import random
import time
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
                name: "new_vault"

    '''
    max_count = 200  # the maximum count of instance of vault

    schema = type_schema('associate_server_with_vault',
                         name={'type': 'string'}
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
        random_time = random.randint(0, 6)
        time.sleep(random_time * 30)
        client = self.manager.get_client()
        try:
            request = ListVaultRequest()
            request.object_type = "server"
            response = client.list_vault(request)
            vaults = response.to_dict()['vaults']
            log.info(f"find vault: {vaults}")
        except exceptions.ClientRequestException as e:
            log.exception(
                f"Unable to list vaults. RequestId: {e.request_id}, Reason: {e.error_msg}"
            )
            raise

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
        vault_billing = {}
        if len(vaults) > 0:
            vault_billing['consistent_level'] = vaults[0]['billing']['consistent_level']
            vault_billing['object_type'] = vaults[0]['billing']['object_type']
            vault_billing['protect_type'] = vaults[0]['billing']['protect_type']
            vault_billing['size'] = vaults[0]['billing']['size']
            vault_billing['charging_mode'] = vaults[0]['billing']['charging_mode']
            vault_billing['is_multi_az'] = vaults[0]['billing']['is_multi_az']

        offset = 1
        while resources:
            log.info("All existing vaults are unable to be associated, "
                     "a new vault will be created.")
            server_list = []
            for _ in range(self.max_count):
                if resources:
                    server_list.append(resources.pop())
            vault_name = self.get_new_vault_name(vaults, offset)
            offset += 1
            response = self.create_new_vault(server_list, policy_id, vault_name, vault_billing)
        return response

    def create_new_vault(self, resources, policy_id, vault_name, vault_billing):
        client = self.manager.get_client()
        if (policy_id is None or policy_id == '' or
                vault_name is None or vault_name == '' or
                vault_billing is None or vault_billing == ''):
            error_msg = "param error, policy_id:{}, vault_name:{}, vault_billing:{}".format(
                policy_id, vault_name, vault_billing
            )
            log.error(error_msg)
            raise Exception(error_msg)
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
            billing_vault = BillingCreate(
                consistent_level=vault_billing['consistent_level'],
                object_type=vault_billing['object_type'],
                protect_type=vault_billing['protect_type'],
                size=vault_billing['size'],
                charging_mode=vault_billing['charging_mode'],
                is_multi_az=vault_billing['is_multi_az']
            )
            vault_body = VaultCreate(
                backup_policy_id=policy_id,
                billing=billing_vault,
                name=vault_name,
                resources=listResourcesVault
            )
            request.body = VaultCreateReq(
                vault=vault_body
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
        vault_prefix = self.data.get('name')
        if vault_prefix is None or vault_prefix == '':
            vault_prefix = 'vault'
        new_index = 0
        for vault in vaults:
            if str(vault['name']).startswith(vault_prefix):
                suffix = str(vault['name'])[len(vault_prefix):]
                if suffix.isdigit():
                    index = int(suffix)
                    if new_index <= index:
                        new_index = index
        new_index += offset
        vault_name = f"{vault_prefix}{new_index:04d}"
        log.info(f"create new vault name {vault_name}")
        return vault_name
