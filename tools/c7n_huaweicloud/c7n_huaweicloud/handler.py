# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import os
import uuid

from c7n.config import Config
from c7n.policy import PolicyCollection
from c7n.resources import load_resources
from c7n.structure import StructureParser
from c7n.utils import reset_session_cache
# Load resource plugins
from c7n_huaweicloud.entry import initialize_huaweicloud
from c7n_huaweicloud.provider import HuaweiCloud

initialize_huaweicloud()

log = logging.getLogger('custodian.huaweicloud.functions')

logging.getLogger().setLevel(logging.INFO)


def run(event, context=None):
    # policies file should always be valid in functions so do loading naively
    with open('/opt/function/code/config.json') as f:
        policy_config = json.load(f)

    if not policy_config or not policy_config.get('policies'):
        log.error('Invalid policy config')
        return False

    options_overrides = \
        policy_config['policies'][0].get('mode', {}).get('execution-options', {})

    # if output_dir specified use that, otherwise make a temp directory
    if 'output_dir' not in options_overrides:
        options_overrides['output_dir'] = get_tmp_output_dir()

    options_overrides['access_key_id'] = context.getSecurityAccessKey()
    options_overrides['secret_access_key'] = context.getSecuritySecretKey()
    options_overrides['security_token'] = context.getSecurityToken()
    options_overrides['region'] = context.getUserData('HUAWEI_DEFAULT_REGION')
    options_overrides['domain_id'] = context.getUserData('DOMAIN_ID')
    options_overrides['account_id'] = context.getUserData('DOMAIN_ID')

    # merge all our options in
    options = Config.empty(**options_overrides)

    load_resources(StructureParser().get_resource_types(policy_config))

    options = HuaweiCloud().initialize(options)
    policies = PolicyCollection.from_data(policy_config, options)
    if policies:
        for p in policies:
            log.info(f'[{p.execution_mode}]-User with account_id: '
                     f'[{context.getUserData("DOMAIN_ID")}] influenced the [{p.resource_type}], '
                     f'and triggered the policy [{p.name}].')
            p.expand_variables(p.get_variables({'resource_details': '{resource_details}'}))
            p.validate()
            p.push(event, context)

    reset_session_cache()
    return True


def get_tmp_output_dir():
    output_dir = '/tmp/' + str(uuid.uuid4())  # nosec
    if not os.path.exists(output_dir):
        try:
            os.mkdir(output_dir)
        except OSError as error:
            log.warning("Unable to make output directory: {}".format(error))
    return output_dir
