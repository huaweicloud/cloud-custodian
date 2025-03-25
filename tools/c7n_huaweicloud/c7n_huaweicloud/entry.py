# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

# register Huawei Cloud provider
from c7n_huaweicloud.provider import HuaweiCloud  # noqa


def initialize_huaweicloud():
    # load shared filters for all Huawei Cloud resources
    import c7n_huaweicloud.filters

    # load shared actions for all Huawei Cloud resources
    import c7n_huaweicloud.actions

    import c7n_huaweicloud.output  # noqa

    import c7n_huaweicloud.policy  # noqa
