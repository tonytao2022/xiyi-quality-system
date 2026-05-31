-- 兮易AI智体平台 · 增量迁移脚本 (MySQL 8.0兼容)
-- 生产库执行: mysql -u debian-sys-maint xiyi_quality < scripts/migration_p0_p1.sql

-- P0-7: ds_mock_data 增加 is_mock 标志
SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='xiyi_quality' AND TABLE_NAME='ds_mock_data' AND COLUMN_NAME='is_mock');
SET @sql = IF(@col_exists=0, 'ALTER TABLE ds_mock_data ADD COLUMN is_mock TINYINT(1) DEFAULT 1 COMMENT ''1=模拟数据 0=CSV导入数据''', 'SELECT ''is_mock already exists''');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- P1-3: ds_source_connection 补充字段
SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='xiyi_quality' AND TABLE_NAME='ds_source_connection' AND COLUMN_NAME='sync_frequency');
SET @sql = IF(@col_exists=0, 'ALTER TABLE ds_source_connection ADD COLUMN sync_frequency VARCHAR(32) DEFAULT ''daily'' COMMENT ''同步频率'', ADD COLUMN retry_count INT DEFAULT 3 COMMENT ''重试次数''', 'SELECT ''sync_frequency already exists''');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- P1-1: 外键级联删除
ALTER TABLE ap_scene_step DROP FOREIGN KEY IF EXISTS ap_scene_step_ibfk_1;
ALTER TABLE ap_scene_step ADD CONSTRAINT ap_scene_step_ibfk_1 FOREIGN KEY (scene_id) REFERENCES ap_scene_config(id) ON DELETE CASCADE;

ALTER TABLE ap_capa_task DROP FOREIGN KEY IF EXISTS ap_capa_task_ibfk_1;
ALTER TABLE ap_capa_task ADD CONSTRAINT ap_capa_task_ibfk_1 FOREIGN KEY (plan_id) REFERENCES ap_capa_plan(id) ON DELETE CASCADE;

ALTER TABLE ap_capa_task_track DROP FOREIGN KEY IF EXISTS ap_capa_task_track_ibfk_1;
ALTER TABLE ap_capa_task_track ADD CONSTRAINT ap_capa_task_track_ibfk_1 FOREIGN KEY (task_id) REFERENCES ap_capa_task(id) ON DELETE CASCADE;

ALTER TABLE ds_column_metadata DROP FOREIGN KEY IF EXISTS ds_column_metadata_ibfk_1;
ALTER TABLE ds_column_metadata ADD CONSTRAINT ds_column_metadata_ibfk_1 FOREIGN KEY (table_id) REFERENCES ds_table_metadata(id) ON DELETE CASCADE;

ALTER TABLE ds_mapping_rule DROP FOREIGN KEY IF EXISTS ds_mapping_rule_ibfk_1;
ALTER TABLE ds_mapping_rule ADD CONSTRAINT ds_mapping_rule_ibfk_1 FOREIGN KEY (source_column_id) REFERENCES ds_column_metadata(id) ON DELETE CASCADE;

ALTER TABLE ap_scene_ds_binding DROP FOREIGN KEY IF EXISTS ap_scene_ds_binding_ibfk_1;
ALTER TABLE ap_scene_ds_binding ADD CONSTRAINT ap_scene_ds_binding_ibfk_1 FOREIGN KEY (scene_id) REFERENCES ap_scene_config(id) ON DELETE CASCADE;

ALTER TABLE ds_table_metadata DROP FOREIGN KEY IF EXISTS ds_table_metadata_ibfk_1;
ALTER TABLE ds_table_metadata ADD CONSTRAINT ds_table_metadata_ibfk_1 FOREIGN KEY (source_id) REFERENCES ds_source_connection(id) ON DELETE CASCADE;

ALTER TABLE ap_scene_report_tpl DROP FOREIGN KEY IF EXISTS ap_scene_report_tpl_ibfk_1;
ALTER TABLE ap_scene_report_tpl ADD CONSTRAINT ap_scene_report_tpl_ibfk_1 FOREIGN KEY (scene_id) REFERENCES ap_scene_config(id) ON DELETE CASCADE;

SELECT '✅ 迁移完成' as status;
