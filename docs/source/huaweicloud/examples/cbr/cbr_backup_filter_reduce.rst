policies:
    - name: cbr_backup_filter_reduce
      resource: huaweicloud.cbr-backup
      filters:
        - type: reduce
          sort-by: updated_at
          order: desc

