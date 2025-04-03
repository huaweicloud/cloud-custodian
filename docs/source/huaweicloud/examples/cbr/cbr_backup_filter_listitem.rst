policies:
    - name: cbr_backup_filter_listitem
      resource: huaweicloud.cbr-backup
      filters:
        - type: list-item
          key: replication_records
          attrs:
            - id: present
