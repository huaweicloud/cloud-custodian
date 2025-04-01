# Cloud Custodian - Huawei Cloud Support

This is a plugin to Cloud Custodian that adds Huawei Cloud support.

## Install Cloud Custodian and Huawei Cloud Plugin

The Huawei Cloud provider must be installed as a separate package in addition to c7n.

    $ pip install c7n_huaweicloud

## Write your first policy

Cloud Custodian policies are expressed in YAML and include the following:

* The type of resource to run the policy against
* Filters to narrow down the set of resources
* Actions to take on the filtered set of resources

Our first policy filters compute instance of a specific name, then adds the tag ``mark_deletion: true``.

Create a file named ``custodian.yml`` with the following content.

    policies:
        - name: filter-for-encrypted-volume
          resource: huaweicloud.evs-volume
          filters:
            - type: value
              key: metadata.__system__encrypted
              value: "0"
          actions:
            - delete

## Run your policy

    export HUAWEI_ACCESS_KEY_ID="YOUR_ACCESS_KEY_ID"
    export HUAWEI_SECRET_ACCESS_KEY="YOUR_SECRET_ACCESS_KEY"
    export HUAWEI_DEFAULT_REGION="YOUR_REGION"

    custodian run --output-dir=. custodian.yml

If successful, you should see output like the following on the command line::

    2025-03-14 16:44:00,553 - custodian.policy - INFO - policy:filter-for-encrypted-volume resource:huaweicloud.volume region: count:1 time:0.92
    2025-03-14 16:44:00,771 - custodian.huaweicloud.resources.volume - INFO - Received Job ID:90f0aed1b4ee443d80dc3faddc543ad9
    2025-03-14 16:44:00,771 - custodian.policy - INFO - policy:filter-for-encrypted-volume action:volumedelete resources:1 execution_time:0.22

You can find a new ``filter-for-encrypted-volume`` under --output-dir option value directory with a log and a ``resources.json`` file.

## Links
- [Getting Started](https://cloudcustodian.io/docs/huaweicloud/gettingstarted.html)
- [Example Scenarios](https://cloudcustodian.io/docs/huaweicloud/examples/index.html)
