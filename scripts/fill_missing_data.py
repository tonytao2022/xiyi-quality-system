#!/usr/bin/env python3
"""补充数据层空表数据 (P1修复: Hugo P1-1~P1-9, P1-11 + P0-3列名统一)
修复全部P1数据层问题：空表补充 + 数据标准 + 派生指标 + 快照 + 质量规则 + 告警等
FIXED: P0-3 - 列名统一，INSERT列名与schema_full.sql DDL完全一致
"""
import pymysql, json, os
from datetime import datetime, timedelta

MYSQL_PASS = os.environ.get('XIYI_MYSQL_PASS', '') or \
    [l.split('=')[1].strip() for l in open('/etc/mysql/debian.cnf') if 'password' in l][0]

conn = pymysql.connect(host='127.0.0.1', port=3306, user='debian-sys-maint',
    password=MYSQL_PASS, database='xiyi_quality', charset='utf8mb4')
cur = conn.cursor()

print("=== 补充数据源配置 (Hugo P1-1) ===")

# ds_source_connection (先插连接表，获取ID供后续外键使用)
# FIXED: P0-3 - 列名统一: conn_code->source_code, db_type->source_type, database_name->db_name, description->source_name
conns = [
    ('FW_MOM_MYSQL', '生产系统主库', 'MySQL', '127.0.0.1', 3306, 'mom_db', None),
    ('FW_MOM_REDIS', '缓存服务', 'Redis', '127.0.0.1', 6379, '', None),
]
conn_ids = []
for c in conns:
    cur.execute("INSERT IGNORE INTO ds_source_connection (source_code,source_name,source_type,host,port,db_name,config_json) VALUES (%s,%s,%s,%s,%s,%s,%s)", c)
    if cur.lastrowid and cur.lastrowid > 0:
        conn_ids.append(cur.lastrowid)
print(f"  ds_source_connection: {len(conns)}条 ✓")

# 回查刚插入的记录ID（兼容INSERT IGNORE已有数据的情况）
cur.execute("SELECT id FROM ds_source_connection WHERE source_code IN ('FW_MOM_MYSQL','FW_MOM_REDIS') ORDER BY id")
conn_ids = [r[0] for r in cur.fetchall()]
mom_id = conn_ids[0] if len(conn_ids) > 0 else 1
redis_id = conn_ids[1] if len(conn_ids) > 1 else 2

# ds_source_heartbeat
# FIXED: P0-3 - 列名统一: conn_code->source_id, latency_ms->response_time_ms
for sid in conn_ids:
    cur.execute("INSERT IGNORE INTO ds_source_heartbeat (source_id, status, response_time_ms) VALUES (%s,'ok',12)", (sid,))
print(f"  ds_source_heartbeat: {len(conn_ids)}条 ✓")

# ds_table_metadata
# FIXED: P0-3 - 列名统一: table_code->table_name, source_system->去掉(DDL无此列), business_domain->table_alias
tables_data = [
    (mom_id, 'T_MOM_QUALITY_INSPECT', '质量检验结果表', 'TABLE', '生产检验'),
    (mom_id, 'T_MOM_MAGNETIC_CHECK', '磁物检验表', 'TABLE', '过程检验'),
    (mom_id, 'T_MOM_INVENTORY_ABNORMAL', '异常库存表', 'TABLE', '库存管理'),
    (mom_id, 'T_MOM_IQC_RESULT', '来料检验结果表', 'TABLE', '供应商管理'),
    (mom_id, 'T_MOM_PMP_RESULT', '过程FPY统计表', 'TABLE', '过程品控'),
    (mom_id, 'T_MOM_COQ_SUMMARY', '质量成本汇总表', 'TABLE', '质量成本'),
]
for t in tables_data:
    cur.execute("INSERT IGNORE INTO ds_table_metadata (source_id,table_name,table_alias,table_type,description) VALUES (%s,%s,%s,%s,%s)", t)
print(f"  ds_table_metadata: {len(tables_data)}条 ✓")

# 获取刚插入的表ID
cur.execute("SELECT id, table_name FROM ds_table_metadata WHERE source_id=%s ORDER BY id", (mom_id,))
table_id_map = {r[1]: r[0] for r in cur.fetchall()}

# ds_column_metadata
# FIXED: P0-3 - 列名统一: std_code->column_name, source_table->table_id, source_column->column_name(已在column_name), description->column_alias(改为)
cols = [
    ('T_MOM_QUALITY_INSPECT', 'result', '检验结果', 'varchar', 10),
    ('T_MOM_QUALITY_INSPECT', 'batch_no', '批次号', 'varchar', 50),
    ('T_MOM_QUALITY_INSPECT', 'machine_id', '设备编号', 'varchar', 20),
]
for tn, col_name, alias, dtype, dlen in cols:
    tbl_id = table_id_map.get(tn)
    if tbl_id:
        cur.execute("INSERT IGNORE INTO ds_column_metadata (table_id,column_name,column_alias,data_type,data_length) VALUES (%s,%s,%s,%s,%s)",
            (tbl_id, col_name, alias, dtype, dlen))
print(f"  ds_column_metadata: {len(cols)}条 ✓")

# ds_mapping_rule
# FIXED: P0-3 - 列名统一: rule_code->target_std_code, source_table->source_column_id(改为FK), rule_name->映射类型, mapping_rule->expression, domain->去掉
# 用第一个column的ID做FK
first_col_id = None
cur.execute("SELECT id FROM ds_column_metadata LIMIT 1")
row = cur.fetchone()
if row:
    first_col_id = row[0]
if first_col_id:
    rules = [
        (first_col_id, 'FPY_STD_CODE', 'direct', 'SUM(case when result=\'PASS\' then 1 else 0 end)/COUNT(*)', None, 0),
        (first_col_id, 'MAG_ABN_STD_CODE', 'direct', 'COUNT(case when is_abnormal=1 then 1 end)/COUNT(*)', None, 0),
    ]
    for r in rules:
        cur.execute("INSERT IGNORE INTO ds_mapping_rule (source_column_id,target_std_code,mapping_type,expression,lookup_table,priority) VALUES (%s,%s,%s,%s,%s,%s)", r)
    print(f"  ds_mapping_rule: {len(rules)}条 ✓")
else:
    print("  ds_mapping_rule: 跳过(无column元数据) ✗")

print("\n=== 补充数据标准字典 (Hugo P1-2) ===")
# FIXED: P0-3 - 列名统一: standard_code->dict_code, standard_name->dict_name, scope_json->items, standard_rule->去掉(转为items合并)
standards = [
    ('PROD_QUAL_STD', '产品品质标准', 'enum', None, json.dumps([
        {'indicator': 'FPY', 'target': '>=99%', 'method': '抽检'},
        {'indicator': '不良率', 'target': '<1%', 'method': '全检'},
        {'scope': '最终产品', 'version': 'V2.1', 'effective_date': '2026-01-01'}
    ])),
    ('MAG_QUAL_STD', '磁物检验标准', 'enum', None, json.dumps([
        {'indicator': '异常率', 'target': '0%', 'method': '批次检验'},
        {'scope': '磁物检测', 'version': 'V1.3', 'effective_date': '2026-03-15'}
    ])),
    ('IQC_STD', '来料检验标准', 'enum', None, json.dumps([
        {'indicator': '合格率', 'target': '>=95%', 'method': 'AQL抽检'},
        {'scope': '原料入厂', 'version': 'V3.0', 'effective_date': '2026-02-01'}
    ])),
]
for s in standards:
    cur.execute("INSERT IGNORE INTO dg_data_standard (dict_code, dict_name, dict_type, source_table, items) VALUES (%s,%s,%s,%s,%s)", s)
print(f"  dg_data_standard: {len(standards)}条 ✓")

print("\n=== 补充派生指标 (Hugo P1-2) ===")
# FIXED: P0-3 - 列名统一: derived_code->indicator_code, derived_name->indicator_name, base_indicator_code->去掉(公式里体现), calc_method->formula, calc_params->去掉
derived = [
    ('FPY_TREND', 'FPY趋势指标', None, '线性回归趋势(基于FPY_RATE)', '%'),
    ('MAG_TREND', '磁物异常趋势', None, '移动平均(基于MAG_ABNORM_RATE)', '%'),
    ('COQ_TREND', '质量成本趋势', None, '移动平均(基于COQ_RATE)', '%'),
]
for d in derived:
    cur.execute("INSERT IGNORE INTO dg_derived_indicator (indicator_code, indicator_name, category_id, formula, unit) VALUES (%s,%s,%s,%s,%s)", d)
print(f"  dg_derived_indicator: {len(derived)}条 ✓")

print("\n=== 补充指标快照 (Hugo P1-3) ===")
# FIXED: P0-3 - 列名统一: data_source->data_source(保留), source_batch->extra_info(json中存batch信息)
today = datetime.now()
snapshot_count = 0
for i in range(1, 13):
    snap_date = (today - timedelta(weeks=i)).strftime('%Y-%m-%d')
    for ind_code, base_val in [('FPY_RATE', 97.5), ('MAG_ABNORM_RATE', 3.2), ('COQ_RATE', 1.5),
                                ('IQC_PASS_RATE', 96.8), ('PMP_FPY', 97.1)]:
        val = round(base_val + (i-6)*0.1, 2)
        extra_info = json.dumps({'source_batch': 'BATCH_mock', 'week': i})
        cur.execute("INSERT IGNORE INTO dg_indicator_snapshot (indicator_code, snapshot_date, snapshot_value, data_source, extra_info) VALUES (%s,%s,%s,'mock',%s)",
            (ind_code, snap_date, val, extra_info))
        snapshot_count += 1
print(f"  dg_indicator_snapshot: {snapshot_count}条 ✓")

print("\n=== 补充质量检查规则 (Hugo P1-4) ===")
# FIXED: P0-3 - 列名统一: target_indicator->target_column, check_params->check_condition, severity->severity(保留), 增加rule_type
qc_rules = [
    ('QC_FPY_NON_NEG', 'FPY非负检查', 'completeness', None, 'FPY_RATE', json.dumps({'check_type': 'range', 'min': 0, 'max': 100}), '严重'),
    ('QC_MAG_RANGE', '磁物异常率范围', 'accuracy', None, 'MAG_ABNORM_RATE', json.dumps({'check_type': 'range', 'min': 0, 'max': 100}), '严重'),
    ('QC_DATE_FRESH', '数据新鲜度', 'timeliness', None, None, json.dumps({'check_type': 'freshness', 'max_age_hours': 48}), '中等'),
]
for q in qc_rules:
    cur.execute("INSERT IGNORE INTO dg_quality_check_rule (rule_code, rule_name, rule_type, target_table_id, target_column, check_condition, severity) VALUES (%s,%s,%s,%s,%s,%s,%s)", q)
print(f"  dg_quality_check_rule: {len(qc_rules)}条 ✓")

print("\n=== 补充告警记录 (Hugo P1-5) ===")
# FIXED: P0-3 - 列名统一: alert_title->title, alert_content->content, source->去掉(DDL无此列), created_at->alert_time
# DDL: (scene_id, indicator_code, alert_level, title, content, alert_time, is_read, handled_by, handled_at)
alerts = [
    (1, 'FPY_RATE', 'warning', 'FPY低于阈值', 'FPY 97.2% 低于阈值 97.0%'),
    (1, 'MAG_ABNORM_RATE', 'critical', '磁物异常率上升', '磁物异常率15.5%超过警戒线'),
]
now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
for a in alerts:
    cur.execute("INSERT IGNORE INTO vw_alert_record (scene_id, indicator_code, alert_level, title, content, alert_time) VALUES (%s,%s,%s,%s,%s,%s)",
        (a[0], a[1], a[2], a[3], a[4], now_str))
print(f"  vw_alert_record: {len(alerts)}条 ✓")

print("\n=== 补充分析模型注册 (Hugo P1-6) ===")
# FIXED: P0-3 - 列名统一: model_config->engine_config, description->保留
models = [
    ('gpt4o-mini', 'OpenAI GPT-4o Mini', 'llm_reasoning', json.dumps({'model': 'gpt-4o-mini', 'provider': 'openai'}), None, None, None, '通用品质分析'),
    ('deepseek-chat', 'DeepSeek Chat', 'llm_reasoning', json.dumps({'model': 'deepseek-chat', 'provider': 'deepseek'}), None, None, None, '深度根因分析'),
]
for m in models:
    cur.execute("INSERT IGNORE INTO ap_analysis_model (model_code, model_name, model_type, engine_config, input_schema, output_schema, prompt_template, description) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", m)
print(f"  ap_analysis_model: {len(models)}条 ✓")

print("\n=== 补充场景数据源绑定 (Hugo P1-7) ===")
# FIXED: P0-3 - 列名统一: conn_code->indicator_code, table_code->std_column_code, binding_config->filter_condition(无则NULL)
for scene_id in range(1, 8):
    cur.execute("INSERT IGNORE INTO ap_scene_ds_binding (scene_id, filter_condition) VALUES (%s,'{}')", (scene_id,))
print(f"  ap_scene_ds_binding: 7场景 ✓")

print("\n=== 补充报告模板 (Hugo P1-8) ===")
# FIXED: P0-3 - 列名统一: role_type->scene_id, tpl_config->sections+tpl_vars(拆分)
# DDL: (tpl_code, tpl_name, scene_id, report_type, tpl_content, sections, tpl_vars, sort_order, is_default, status, ...)
templates = [
    ('TMPL_QUAL_DAILY', '品质日报模板', 1, 'html', '', json.dumps({'sections': ['指标总览', '异常汇总', '改善跟踪'], 'format': 'html'}), '{}'),
    ('TMPL_QUAL_WEEKLY', '品质周报模板', 1, 'html', '', json.dumps({'sections': ['周度趋势', '根因分析', 'CAPA进展'], 'format': 'html'}), '{}'),
]
for t in templates:
    cur.execute("INSERT IGNORE INTO ap_scene_report_tpl (tpl_code, tpl_name, scene_id, report_type, tpl_content, sections, tpl_vars) VALUES (%s,%s,%s,%s,%s,%s,%s)", t)
print(f"  ap_scene_report_tpl: {len(templates)}条 ✓")

print("\n=== 补充系统配置 (Hugo P1-9) ===")
# FIXED: P0-3 - description->config_desc(DDL兼容)
sys_cfgs = [
    ('xiyi.version', '1.0.0', '系统版本'),
    ('xiyi.alert.email_enabled', 'false', '邮件告警开关'),
    ('xiyi.ai.default_model', 'deepseek-chat', '默认AI模型'),
    ('xiyi.trace.max_days', '30', 'trace保留天数'),
]
for c in sys_cfgs:
    cur.execute("INSERT IGNORE INTO sys_config (config_key, config_value, config_desc) VALUES (%s,%s,%s)", c)
print(f"  sys_config: {len(sys_cfgs)}条 ✓")

conn.commit()
cur.close()
conn.close()
print("\n✅ 全部数据补充完成! (P0-3列名已统一)")
