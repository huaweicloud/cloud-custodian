OBS - Configuration Only Allow Https Request Access Bucket
========================

.. code-block:: yaml

  policies:
    - name: obs-bucket-https-request-only
      resource: huaweicloud.obs
      filters:
        - type: support-https-request
      actions:
          - type: set-statements
            statements:
              - Sid: DenyHttp
                Effect: Deny
                Principal: 
                  ID: "*"
                Action: "*"
                Resource: 
                  - "{bucket_name}"
                  - "{bucket_name}/*"
                Condition:
                  Bool:
                    SecureTransport: "false"
