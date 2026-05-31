-- ============================================================
-- 兮易AI大脑 · 品质专员平台 · 产品级DDL（27张表）
-- 数据库：xiyi_quality（与stock_db完全独立）
-- 四层架构：数据采集层 → 数据治理层 → 数据应用层 → 展现层
-- ============================================================

-- ════════════════════════════════════════════════════════════
-- 第一层：数据采集层（7张表）
-- ════════════════════════════════════════════════════════════

-- 1. 数据源连接配置
CREATE TABLE ds_source_connection (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  source_code     VARCHAR(32) NOT NULL UNIQUE COMMENT '数据源编码',
  source_name     VARCHAR(100) NOT NULL COMMENT '数据源名称',
  source_type     VARCHAR(32) NOT NULL COMMENT '类型(mysql/http/api/file/csv/excel)',
  host            VARCHAR(255) COMMENT '连接地址',
  port            INT COMMENT '端口',
  db_name         VARCHAR(64) COMMENT '数据库名',
  config_json     JSON COMMENT '连接配置(json格式)',
  status          ENUM('active','inactive','error') DEFAULT 'active',
  last_connected  DATETIME COMMENT '最后连接时间',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据源连接配置';

-- 2. 数据表元数据
CREATE TABLE ds_table_metadata (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  source_id       INT NOT NULL COMMENT '所属数据源',
  table_name      VARCHAR(64) NOT NULL COMMENT '表名',
  table_alias     VARCHAR(100) COMMENT '表中文名',
  table_type      VARCHAR(32) DEFAULT 'TABLE' COMMENT '类型(TABLE/VIEW/SYSTEM)',
  row_count_est   BIGINT COMMENT '预估行数',
  description     TEXT COMMENT '表说明',
  sync_interval   INT DEFAULT 0 COMMENT '同步间隔(分钟,0=手动)',
  last_sync_time  DATETIME COMMENT '最后同步时间',
  sync_status     VARCHAR(16) DEFAULT 'pending' COMMENT '同步状态',
  status          ENUM('active','inactive') DEFAULT 'active',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_source (source_id),
  FOREIGN KEY (source_id) REFERENCES ds_source_connection(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据表元数据';

-- 3. 字段元数据
CREATE TABLE ds_column_metadata (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  table_id        INT NOT NULL COMMENT '所属数据表',
  column_name     VARCHAR(64) NOT NULL COMMENT '字段名',
  column_alias    VARCHAR(100) COMMENT '字段中文名',
  data_type       VARCHAR(32) COMMENT '数据类型',
  data_length     INT COMMENT '数据长度',
  is_nullable     TINYINT(1) DEFAULT 1,
  is_primary_key  TINYINT(1) DEFAULT 0,
  default_value   VARCHAR(200) COMMENT '默认值',
  enum_values     JSON COMMENT '枚举值列表',
  sample_data     VARCHAR(200) COMMENT '示例数据',
  description     TEXT COMMENT '字段说明',
  status          ENUM('active','inactive') DEFAULT 'active',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_table (table_id),
  FOREIGN KEY (table_id) REFERENCES ds_table_metadata(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='字段元数据';

-- 4. 字段映射规则
CREATE TABLE ds_mapping_rule (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  source_column_id INT NOT NULL COMMENT '源字段',
  target_std_code  VARCHAR(64) NOT NULL COMMENT '目标标准字段编码',
  mapping_type    VARCHAR(32) DEFAULT 'direct' COMMENT '映射类型(direct/expression/lookup)',
  expression      TEXT COMMENT '转换表达式',
  lookup_table    VARCHAR(64) COMMENT '对照表',
  priority        INT DEFAULT 0 COMMENT '优先级',
  status          ENUM('active','inactive') DEFAULT 'active',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_source (source_column_id),
  FOREIGN KEY (source_column_id) REFERENCES ds_column_metadata(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='字段映射规则';

-- 5. 模拟数据表（DEMO用 - 存放各场景模拟数据）
-- FIXED: P0-7 - 新增is_mock字段(0=CSV导入,1=模拟生成)
CREATE TABLE ds_mock_data (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  scene_id        INT NOT NULL COMMENT '场景编号',
  mock_date       DATE NOT NULL COMMENT '数据日期',
  data_category   VARCHAR(32) COMMENT '数据分类',
  data_json       JSON NOT NULL COMMENT '模拟数据(JSON)',
  is_mock         TINYINT(1) DEFAULT 1 COMMENT '是否模拟数据(0=CSV导入,1=模拟生成)',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模拟数据表(DEMO用)';

-- 6. 同步任务日志
CREATE TABLE ds_sync_log (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  table_id        INT NOT NULL,
  sync_type       VARCHAR(16) DEFAULT 'full' COMMENT '同步类型(full/incremental)',
  status          VARCHAR(16) DEFAULT 'running' COMMENT '状态',
  rows_processed  INT DEFAULT 0,
  rows_failed     INT DEFAULT 0,
  error_message   TEXT,
  started_at      DATETIME,
  completed_at    DATETIME,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_table (table_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='同步任务日志';

-- 7. 数据源心跳记录
CREATE TABLE ds_source_heartbeat (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  source_id       INT NOT NULL,
  status          VARCHAR(16) DEFAULT 'ok' COMMENT '状态(ok/error/timeout)',
  response_time_ms INT,
  error_message   TEXT,
  checked_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_source (source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据源心跳记录';


-- ════════════════════════════════════════════════════════════
-- 第二层：数据治理层（8张表）
-- ════════════════════════════════════════════════════════════

-- 8. 原子指标定义
CREATE TABLE dg_indicator_atom (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  indicator_code  VARCHAR(50) NOT NULL UNIQUE COMMENT '指标编码',
  indicator_name  VARCHAR(100) NOT NULL COMMENT '指标名称',
  category_id     INT COMMENT '分类ID',
  calc_logic      TEXT COMMENT '计算逻辑(SQL/表达式)',
  source_table_id INT COMMENT '源数据表',
  aggregation     VARCHAR(32) DEFAULT 'avg' COMMENT '聚合方式',
  unit            VARCHAR(20) COMMENT '单位',
  data_type       VARCHAR(16) DEFAULT 'decimal' COMMENT '值类型',
  threshold_upper DECIMAL(16,4) COMMENT '上限阈值',
  threshold_lower DECIMAL(16,4) COMMENT '下限阈值',
  alert_level     VARCHAR(8) DEFAULT 'warning' COMMENT '告警级别',
  is_active       TINYINT(1) DEFAULT 1,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_category (category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='原子指标定义';

-- 9. 指标分类
CREATE TABLE dg_indicator_category (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  category_code   VARCHAR(32) NOT NULL UNIQUE,
  category_name   VARCHAR(100) NOT NULL,
  parent_id       INT DEFAULT 0,
  sort_order      INT DEFAULT 0,
  is_active       TINYINT(1) DEFAULT 1,
  INDEX idx_parent (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='指标分类';

-- 10. 派生指标
CREATE TABLE dg_derived_indicator (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  indicator_code  VARCHAR(50) NOT NULL UNIQUE,
  indicator_name  VARCHAR(100) NOT NULL,
  category_id     INT,
  formula         TEXT NOT NULL COMMENT '计算公式(引用原子指标)',
  unit            VARCHAR(20),
  threshold_lower DECIMAL(16,4),
  threshold_upper DECIMAL(16,4),
  is_active       TINYINT(1) DEFAULT 1,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='派生指标';

-- 11. 标准字段定义
CREATE TABLE dg_standard_column (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  std_code        VARCHAR(64) NOT NULL UNIQUE COMMENT '标准编码',
  std_name        VARCHAR(100) NOT NULL COMMENT '标准名称',
  data_type       VARCHAR(32) COMMENT '数据类型',
  data_length     INT,
  enum_dict       JSON COMMENT '枚举字典',
  format_rule     VARCHAR(200) COMMENT '格式规则',
  description     TEXT,
  status          ENUM('active','inactive') DEFAULT 'active',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='标准字段定义';

-- 12. 数据标准字典
CREATE TABLE dg_data_standard (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  dict_code       VARCHAR(50) NOT NULL UNIQUE COMMENT '字典编码',
  dict_name       VARCHAR(100) NOT NULL COMMENT '字典名称',
  dict_type       VARCHAR(32) DEFAULT 'enum' COMMENT '字典类型(enum/table/range)',
  source_table    VARCHAR(64) COMMENT '来源表',
  items           JSON COMMENT '字典条目',
  status          ENUM('active','inactive') DEFAULT 'active',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据标准字典';

-- 13. 数据质量检查规则
CREATE TABLE dg_quality_check_rule (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  rule_code       VARCHAR(50) NOT NULL UNIQUE,
  rule_name       VARCHAR(100) NOT NULL,
  rule_type       VARCHAR(32) NOT NULL COMMENT '类型(completeness/accuracy/consistency/timeliness/uniqueness)',
  target_table_id INT COMMENT '目标表',
  target_column   VARCHAR(64) COMMENT '目标字段',
  check_condition TEXT COMMENT '检查条件(JSON)',
  severity        VARCHAR(8) DEFAULT 'warning' COMMENT '严重级别',
  schedule_cron   VARCHAR(64) COMMENT '调度cron',
  is_active       TINYINT(1) DEFAULT 1,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据质量检查规则';

-- 14. 数据质量检查日志
CREATE TABLE dg_quality_check_log (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  rule_id         INT NOT NULL,
  check_time      DATETIME DEFAULT CURRENT_TIMESTAMP,
  total_count     INT DEFAULT 0,
  pass_count      INT DEFAULT 0,
  fail_count      INT DEFAULT 0,
  pass_rate       DECIMAL(5,2) COMMENT '通过率',
  detail_data     JSON COMMENT '详细结果',
  status          VARCHAR(16) DEFAULT 'completed',
  duration_ms     INT,
  INDEX idx_rule (rule_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据质量检查日志';

-- 15. 指标值快照（历史）
CREATE TABLE dg_indicator_snapshot (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  indicator_code  VARCHAR(50) NOT NULL,
  snapshot_date   DATE NOT NULL,
  snapshot_value  DECIMAL(20,4) NOT NULL,
  scene_id        INT,
  data_source     VARCHAR(64),
  extra_info      JSON,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_indicator (indicator_code, snapshot_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='指标值快照';


-- ════════════════════════════════════════════════════════════
-- 第三层：数据应用层（8张表）
-- ════════════════════════════════════════════════════════════

-- 16. 场景配置
CREATE TABLE ap_scene_config (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  scene_code      VARCHAR(32) NOT NULL UNIQUE COMMENT '场景编码(QUAL_01~07)',
  scene_name      VARCHAR(200) NOT NULL COMMENT '场景名称',
  role_type       VARCHAR(32) NOT NULL DEFAULT 'quality' COMMENT '角色类型',
  category        VARCHAR(50) COMMENT '分类',
  icon            VARCHAR(50) DEFAULT 'chart-line',
  description     TEXT COMMENT '业务背景',
  tags            JSON COMMENT '标签',
  status          ENUM('draft','published','deprecated') DEFAULT 'published',
  sort_order      INT DEFAULT 0,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='场景配置';

-- 17. 场景步骤配置（七步流程）
CREATE TABLE ap_scene_step (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  scene_id        INT NOT NULL COMMENT '所属场景',
  step_code       VARCHAR(32) NOT NULL COMMENT '步骤编码',
  step_name       VARCHAR(100) NOT NULL COMMENT '步骤名称',
  step_type       VARCHAR(32) NOT NULL COMMENT '类型(definition/analysis/correlation/verification/attribution/solution/tracking)',
  sort_order      INT DEFAULT 0 COMMENT '步骤顺序',
  description     TEXT COMMENT '步骤说明',
  input_desc      TEXT COMMENT '输入说明',
  output_desc     TEXT COMMENT '输出说明',
  is_ai_required  TINYINT(1) DEFAULT 0 COMMENT '是否需AI推理',
  is_manual_input TINYINT(1) DEFAULT 0 COMMENT '是否需手工输入',
  analysis_model_id INT COMMENT '绑定的分析模型',
  report_tpl_id   INT COMMENT '绑定的报告模板',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_scene (scene_id),
  FOREIGN KEY (scene_id) REFERENCES ap_scene_config(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='场景步骤配置';

-- 18. 场景数据源绑定
CREATE TABLE ap_scene_ds_binding (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  scene_id        INT NOT NULL COMMENT '场景',
  step_id         INT COMMENT '步骤(可选)',
  indicator_code  VARCHAR(50) COMMENT '绑定指标',
  std_column_code VARCHAR(64) COMMENT '绑定标准字段',
  source_table_id INT COMMENT '源数据表',
  source_column_id INT COMMENT '源字段',
  filter_condition JSON COMMENT '过滤条件',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_scene (scene_id),
  FOREIGN KEY (scene_id) REFERENCES ap_scene_config(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='场景数据源绑定';

-- 19. 分析模型注册
CREATE TABLE ap_analysis_model (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  model_code      VARCHAR(50) NOT NULL UNIQUE,
  model_name      VARCHAR(100) NOT NULL,
  model_type      VARCHAR(32) NOT NULL COMMENT '类型(llm_reasoning/rule_engine/statistical/ml)',
  engine_config   JSON COMMENT '引擎配置',
  input_schema    JSON COMMENT '输入参数定义',
  output_schema   JSON COMMENT '输出参数定义',
  prompt_template TEXT COMMENT 'LLM Prompt模板',
  version         VARCHAR(20) DEFAULT '1.0',
  status          ENUM('draft','published','deprecated') DEFAULT 'published',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='分析模型注册';

-- 20. 分析实例（运行时）
CREATE TABLE ap_analysis_instance (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  scene_id        INT NOT NULL,
  instance_code   VARCHAR(50) NOT NULL UNIQUE COMMENT '实例编码',
  title           VARCHAR(200) COMMENT '分析标题',
  status          VARCHAR(16) DEFAULT 'init' COMMENT '状态(init/running/done/failed)',
  current_step    INT DEFAULT 1 COMMENT '当前步骤',
  initiator       VARCHAR(50) COMMENT '发起人',
  start_time      DATETIME,
  complete_time   DATETIME,
  conclusion      TEXT COMMENT '分析结论',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_scene (scene_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='分析实例';

-- 21. 分析步骤日志
CREATE TABLE ap_analysis_step_log (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  instance_id     BIGINT NOT NULL,
  step_id         INT NOT NULL COMMENT '步骤配置ID',
  step_status     VARCHAR(16) DEFAULT 'pending' COMMENT 'pending/running/done/skipped/failed',
  input_data      JSON COMMENT '输入数据快照',
  output_data     JSON COMMENT 'AI推理结果/分析结果',
  ai_response     TEXT COMMENT 'LLM原始响应',
  duration_ms     INT COMMENT '执行耗时',
  started_at      DATETIME,
  completed_at    DATETIME,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_instance (instance_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='分析步骤日志';

-- 22. CAPA方案
CREATE TABLE ap_capa_plan (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  plan_code       VARCHAR(50) NOT NULL UNIQUE,
  instance_id     BIGINT NOT NULL COMMENT '关联分析实例',
  title           VARCHAR(200) NOT NULL,
  root_cause      TEXT COMMENT '根因分析结论',
  plan_content    TEXT COMMENT '改善方案内容',
  priority        VARCHAR(8) DEFAULT 'medium' COMMENT '优先级',
  status          VARCHAR(16) DEFAULT 'draft' COMMENT '状态',
  created_by      VARCHAR(50),
  verified_by     VARCHAR(50),
  verify_result   VARCHAR(16) COMMENT '验证结果',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_instance (instance_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='CAPA方案';

-- 23. CAPA任务分解
CREATE TABLE ap_capa_task (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  plan_id         INT NOT NULL COMMENT '所属方案',
  task_code       VARCHAR(50) NOT NULL UNIQUE,
  title           VARCHAR(200) NOT NULL,
  description     TEXT,
  assignee        VARCHAR(50) COMMENT '责任人',
  deadline        DATE,
  priority        VARCHAR(8) DEFAULT 'medium',
  status          VARCHAR(16) DEFAULT 'open' COMMENT 'open/in_progress/done/closed',
  deliverables    TEXT COMMENT '交付物',
  remark          TEXT,
  created_by      VARCHAR(50),
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (plan_id) REFERENCES ap_capa_plan(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='CAPA任务分解';

-- 24. CAPA任务跟踪记录
CREATE TABLE ap_capa_task_track (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id         INT NOT NULL,
  track_time      DATETIME NOT NULL,
  track_type      VARCHAR(32) NOT NULL COMMENT '跟踪类型',
  content         TEXT NOT NULL,
  attachment_url  VARCHAR(500),
  verifier        VARCHAR(100),
  verify_result   VARCHAR(16),
  created_by      VARCHAR(50),
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_task (task_id),
  FOREIGN KEY (task_id) REFERENCES ap_capa_task(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='CAPA任务跟踪记录';


-- ════════════════════════════════════════════════════════════
-- 第四层：展现层（3张表）
-- ════════════════════════════════════════════════════════════

-- 25. 报告模板
CREATE TABLE ap_scene_report_tpl (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  tpl_code        VARCHAR(50) NOT NULL UNIQUE,
  tpl_name        VARCHAR(200) NOT NULL,
  scene_id        INT NOT NULL,
  report_type     VARCHAR(16) DEFAULT 'html' COMMENT '格式',
  tpl_content     TEXT NOT NULL COMMENT '模板内容',
  sections        JSON COMMENT '章节定义',
  tpl_vars        JSON COMMENT '变量定义',
  sort_order      INT DEFAULT 0,
  is_default      TINYINT(1) DEFAULT 0,
  status          ENUM('draft','published','deprecated') DEFAULT 'published',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (scene_id) REFERENCES ap_scene_config(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='报告模板';

-- 26. 告警记录
CREATE TABLE vw_alert_record (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  scene_id        INT,
  indicator_code  VARCHAR(50),
  alert_level     VARCHAR(8) DEFAULT 'warning',
  title           VARCHAR(200) NOT NULL,
  content         TEXT,
  alert_time      DATETIME DEFAULT CURRENT_TIMESTAMP,
  is_read         TINYINT(1) DEFAULT 0,
  handled_by      VARCHAR(50),
  handled_at      DATETIME,
  INDEX idx_scene (scene_id),
  INDEX idx_time (alert_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='告警记录';

-- 27. 系统配置
CREATE TABLE sys_config (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  config_key      VARCHAR(64) NOT NULL UNIQUE,
  config_value    TEXT,
  config_desc     TEXT,
  is_encrypted    TINYINT(1) DEFAULT 0,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统配置';


-- ════════════════════════════════════════════════════════════
-- 第五层：智能体层（13张表）
-- FIXED: P0-2 - 新增缺失表
-- ════════════════════════════════════════════════════════════

-- 28. 智能体任务追踪
CREATE TABLE ag_agent_task (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  trace_id        VARCHAR(64) NOT NULL UNIQUE COMMENT '追踪ID',
  scene_id        INT NOT NULL COMMENT '关联场景',
  skill_name      VARCHAR(64) COMMENT '技能名称',
  input_params    JSON COMMENT '输入参数',
  result          JSON COMMENT '输出结果',
  status          VARCHAR(16) DEFAULT 'running' COMMENT '状态(running/done/error)',
  started_at      DATETIME COMMENT '开始时间',
  completed_at    DATETIME COMMENT '完成时间',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_scene (scene_id),
  INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='智能体任务追踪';

-- 29. 规则配置
CREATE TABLE ag_rule_config (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  rule_code       VARCHAR(64) NOT NULL UNIQUE COMMENT '规则编码',
  scene_id        INT NOT NULL COMMENT '所属场景',
  rule_name       VARCHAR(200) COMMENT '规则名称',
  rule_type       VARCHAR(32) DEFAULT 'threshold' COMMENT '规则类型(threshold/expression/ml)',
  rule_expr       JSON NOT NULL COMMENT '规则表达式',
  priority        INT DEFAULT 0 COMMENT '优先级',
  enabled         TINYINT(1) DEFAULT 1 COMMENT '是否启用',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_scene (scene_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='规则配置';

-- 30. 提示词模板
CREATE TABLE ag_prompt_template (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  template_code   VARCHAR(64) NOT NULL UNIQUE COMMENT '模板编码',
  scene_id        INT COMMENT '关联场景',
  role            VARCHAR(64) DEFAULT 'quality_analyst' COMMENT '角色',
  system_prompt   TEXT COMMENT '系统提示词',
  user_prompt     TEXT COMMENT '用户提示词',
  output_format   VARCHAR(32) DEFAULT 'markdown' COMMENT '输出格式',
  temperature     DECIMAL(3,2) DEFAULT 0.70 COMMENT '温度参数',
  model           VARCHAR(64) DEFAULT 'deepseek-chat' COMMENT '模型名称',
  description     TEXT COMMENT '描述',
  is_active       TINYINT(1) DEFAULT 1 COMMENT '是否启用',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_scene (scene_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='提示词模板';

-- 31. 工具调用日志
CREATE TABLE ag_tool_call_log (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  trace_id        VARCHAR(64) NOT NULL COMMENT '追踪ID',
  tool_name       VARCHAR(64) COMMENT '工具名称',
  input_params    JSON COMMENT '输入参数',
  output_result   JSON COMMENT '输出结果',
  status          VARCHAR(16) DEFAULT 'success' COMMENT '状态',
  duration_ms     INT COMMENT '耗时(ms)',
  called_at       DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '调用时间',
  INDEX idx_trace (trace_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工具调用日志';

-- 32. 工具注册表
CREATE TABLE ag_tool_registry (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  tool_code       VARCHAR(64) NOT NULL UNIQUE COMMENT '工具编码',
  tool_name       VARCHAR(100) COMMENT '工具名称',
  tool_type       VARCHAR(32) NOT NULL COMMENT '工具类型(query/analysis/report/notification)',
  endpoint        VARCHAR(255) COMMENT '接口地址',
  input_schema    JSON COMMENT '输入参数定义',
  output_schema   JSON COMMENT '输出参数定义',
  description     TEXT COMMENT '描述',
  is_active       TINYINT(1) DEFAULT 1 COMMENT '是否启用',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工具注册表';

-- 33. 记忆存储
CREATE TABLE ag_memory_store (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  trace_id        VARCHAR(64) COMMENT '追踪ID',
  memory_type     VARCHAR(32) DEFAULT 'observation' COMMENT '记忆类型(observation/decision/context)',
  memory_key      VARCHAR(128) COMMENT '记忆键',
  memory_value    JSON NOT NULL COMMENT '记忆值',
  scene_id        INT COMMENT '关联场景',
  session_id      VARCHAR(64) COMMENT '会话ID',
  is_persistent   TINYINT(1) DEFAULT 0 COMMENT '是否持久化',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_trace (trace_id),
  INDEX idx_scene (scene_id),
  INDEX idx_key (memory_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='记忆存储';

-- 34. 知识库
CREATE TABLE ag_knowledge_base (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  kb_code         VARCHAR(64) NOT NULL UNIQUE COMMENT '知识编码',
  kb_type         VARCHAR(32) DEFAULT 'standard' COMMENT '知识类型(standard/experience/case)',
  title           VARCHAR(200) COMMENT '标题',
  content         TEXT COMMENT '内容',
  tags            JSON COMMENT '标签',
  scene_id        INT COMMENT '关联场景',
  is_active       TINYINT(1) DEFAULT 1 COMMENT '是否激活',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_scene (scene_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库';

-- 35. 工作流步骤
CREATE TABLE ag_workflow_step (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  workflow_code   VARCHAR(64) NOT NULL COMMENT '工作流编码',
  step_order      INT DEFAULT 0 COMMENT '步骤顺序',
  step_name       VARCHAR(100) COMMENT '步骤名称',
  handler         VARCHAR(64) COMMENT '处理器',
  input_schema    JSON COMMENT '输入参数定义',
  output_schema   JSON COMMENT '输出参数定义',
  timeout_seconds INT DEFAULT 60 COMMENT '超时秒数',
  is_active       TINYINT(1) DEFAULT 1 COMMENT '是否激活',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_workflow (workflow_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工作流步骤';

-- 36. 数据血缘
CREATE TABLE ds_data_lineage (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  source_table    VARCHAR(64) NOT NULL COMMENT '源表',
  source_column   VARCHAR(64) COMMENT '源字段',
  target_indicator VARCHAR(50) NOT NULL COMMENT '目标指标编码',
  transform_logic TEXT COMMENT '转换逻辑',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_target (target_indicator)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据血缘';

-- 37. 角色
CREATE TABLE sys_role (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  role_code       VARCHAR(32) NOT NULL UNIQUE COMMENT '角色编码',
  role_name       VARCHAR(100) NOT NULL COMMENT '角色名称',
  description     TEXT COMMENT '角色描述',
  is_active       TINYINT(1) DEFAULT 1 COMMENT '是否激活',
  sort_order      INT DEFAULT 0 COMMENT '排序',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色';

-- 38. 预警
CREATE TABLE sys_alert (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  alert_title     VARCHAR(200) NOT NULL COMMENT '预警标题',
  alert_content   TEXT COMMENT '预警内容',
  indicator_code  VARCHAR(50) COMMENT '关联指标',
  scene_id        INT COMMENT '关联场景',
  alert_level     VARCHAR(16) DEFAULT 'warning' COMMENT '级别(warning/critical/info)',
  source          VARCHAR(64) COMMENT '来源',
  status          VARCHAR(16) DEFAULT 'pending' COMMENT '状态(pending/processing/resolved/closed)',
  handled_by      VARCHAR(50) COMMENT '处理人',
  handled_at      DATETIME COMMENT '处理时间',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_scene (scene_id),
  INDEX idx_status (status),
  INDEX idx_time (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='预警';

-- 39. 任务
CREATE TABLE sys_task (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  task_title      VARCHAR(200) NOT NULL COMMENT '任务标题',
  task_content    TEXT COMMENT '任务内容',
  task_level      VARCHAR(16) DEFAULT 'medium' COMMENT '级别(urgent/high/medium/low)',
  status          VARCHAR(16) DEFAULT 'pending' COMMENT '状态(pending/inprogress/completed/overdue)',
  assignee        VARCHAR(50) COMMENT '负责人',
  deadline        DATETIME COMMENT '截止时间',
  progress        INT DEFAULT 0 COMMENT '进度(0-100)',
  completed_at    DATETIME COMMENT '完成时间',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_status (status),
  INDEX idx_deadline (deadline)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='任务';

-- 40. 新闻/消息
CREATE TABLE sys_news (
  id              INT PRIMARY KEY AUTO_INCREMENT,
  title           VARCHAR(200) NOT NULL COMMENT '标题',
  content         TEXT COMMENT '内容',
  news_type       VARCHAR(32) DEFAULT 'system' COMMENT '类型(system/alert/notice)',
  is_read         TINYINT(1) DEFAULT 0 COMMENT '是否已读',
  is_active       TINYINT(1) DEFAULT 1 COMMENT '是否激活',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_active (is_active),
  INDEX idx_time (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='新闻/消息';


