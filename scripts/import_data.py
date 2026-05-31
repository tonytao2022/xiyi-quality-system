#!/usr/bin/env python3
"""灌入品质专员场景基础数据"""
import openpyxl, pymysql, json
# P0-1 Hugo: 从环境变量读取MySQL密码,不再硬编码
pwd = __import__('os').environ.get('XIYI_MYSQL_PASS', '') or \
    [l.split('=')[1].strip() for l in open('/etc/mysql/debian.cnf') if 'password' in l][0]
wb = openpyxl.load_workbook("/root/.openclaw/media/qqbot/downloads/智能体应用需求表-品质（含数据源）_1780132027174_6e3b24.xlsx", data_only=True)
conn = pymysql.connect(host='127.0.0.1',port=3306,user='debian-sys-maint',password=pwd,database='xiyi_quality',charset='utf8mb4')
cur = conn.cursor()

# P0-4 Hugo: 用DELETE+事务包裹,避免TRUNCATE外键顺序问题
cur.execute("START TRANSACTION")
for t in ['ap_analysis_step_log','ap_analysis_instance','ap_capa_task_track','ap_capa_task','ap_capa_plan','ap_scene_ds_binding','ap_scene_step','ap_scene_report_tpl','ap_analysis_model','ap_scene_config','dg_indicator_snapshot','dg_derived_indicator','dg_indicator_atom','dg_indicator_category','dg_data_standard','dg_standard_column','ds_mapping_rule','ds_column_metadata','ds_table_metadata','ds_source_connection','ds_source_heartbeat','ds_sync_log','ds_mock_data','sys_config','vw_alert_record','dg_quality_check_log','dg_quality_check_rule']:
    try: cur.execute(f"DELETE FROM {t}")
    except Exception as _e: print(f"  WARN: DELETE {t}: {_e}")
cur.execute("COMMIT")

scenes = [
    (1,'QUAL_01','在线一次交验合格率管控 (深度优化版)','quality','品质监控','chart-line','集成MOM/MES/LIMS/SCADA数据，提供从全局监控、不合格结构分析到原料/设备关联分析的全景数据分析能力'),
    (2,'QUAL_02','磁物健康地图指标监控','quality','过程分析','map-location-dot','建立磁物检验指标与生产过程的关联，预测异常发生可能性'),
    (3,'QUAL_03','异常料情况跟踪分析','quality','库存预警','trash-can','分析库存异常料情况，与检验和生产过程进行关联分析'),
    (4,'QUAL_04','库存呆滞情况跟踪分析','quality','资产优化','hourglass-end','呆滞库存全流程闭环管理，降低库存资金占用'),
    (5,'QUAL_05','原料到货检验合格率管控(IQC)','quality','供应商质量','truck-fast','来料检验合格率监控与不合格批次处置建议'),
    (6,'QUAL_06','制造过程磁物合格率监控(PMP)','quality','过程品控','gear','监控制造过程FPY，薄弱产线诊断与改善排序'),
    (7,'QUAL_07','全业务质量损失成本(COQ)分析','quality','成本分析','coins','系统性监控内外质量损失成本'),
]
for s in scenes:
    cur.execute("INSERT INTO ap_scene_config(id,scene_code,scene_name,role_type,category,icon,description) VALUES(%s,%s,%s,%s,%s,%s,%s)",s)
print(f"场景配置: {len(scenes)}")

step_types = [('definition','问题定义与数据','明确质量问题的具体现象'),('analysis','现象分析与定位','分析质检数据趋势和分布'),('correlation','4M1E关联分析','人机料法环测六维度分析'),('verification','核心根因验证','数据交叉验证锁定根因'),('attribution','能力短板归因','识别品质管控体系薄弱环节'),('solution','解决方案CAPA','制定纠正与预防措施'),('tracking','任务落地跟踪','跟踪执行进度验证改善效果')]
sid = 1
for scid in range(1,8):
    for seq,(st,name,desc) in enumerate(step_types,1):
        cur.execute("INSERT INTO ap_scene_step(id,scene_id,step_code,step_name,step_type,sort_order,description) VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (sid,scid,f"QUAL_{scid:02d}_STEP_{seq:02d}",name,st,seq,desc))
        sid += 1
print(f"场景步骤: {sid-1}")

cats = [(1,'QUALITY_PRODUCT','产品品质指标',0),(2,'QUALITY_PROCESS','过程品质指标',0),(3,'QUALITY_COST','质量成本指标',0),(4,'QUALITY_SUPPLY','供应链品质指标',0)]
for c in cats:
    cur.execute("INSERT INTO dg_indicator_category(id,category_code,category_name,parent_id) VALUES(%s,%s,%s,%s)",c)
print(f"指标分类: {len(cats)}")

indicators = [
    ('FPY_RATE','在线一次交验合格率',1,'合格品数量/总检验数量*100%',1,'avg','%',97.0,0,'danger'),
    ('MAG_ABNORM_RATE','磁物检验异常率',2,'异常检验批次数/总批次数*100%',1,'avg','%',0,0,'danger'),
    ('ABN_STOCK_RATE','异常料库存占比',1,'异常料金额/总库存金额*100%',1,'avg','%',0.5,0,'warning'),
    ('DEAD_STOCK_RATE','呆滞库存占比',1,'呆滞金额/总库存金额*100%',1,'avg','%',3.0,0,'warning'),
    ('IQC_PASS_RATE','来料检验合格率',4,'来料合格批次/来料总批次*100%',1,'avg','%',95.0,0,'warning'),
    ('PMP_FPY','过程一次合格率',2,'工序合格数/工序总检验数*100%',1,'avg','%',95.0,0,'warning'),
    ('COQ_RATE','质量成本率',3,'(内损+外损+鉴定+预防)/销售额*100%',1,'avg','%',1.8,0,'warning'),
]
for i,(code,name,cid,logic,stbl,agg,unit,up,low,level) in enumerate(indicators,1):
    cur.execute("INSERT INTO dg_indicator_atom(id,indicator_code,indicator_name,category_id,calc_logic,source_table_id,aggregation,unit,threshold_upper,threshold_lower,alert_level) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (i,code,name,cid,logic,stbl,agg,unit,up,low,level))
print(f"原子指标: {len(indicators)}")

std_cols = [
    ('QUAL_INSPECT_RESULT','检验结果','varchar',10,json.dumps({'PASS':'合格','FAIL':'不合格','REWORK':'返工'}),None),
    ('QUAL_INSPECT_ITEM','检验项目','varchar',100,None,None),
    ('QUAL_DEFECT_CODE','不良代码','varchar',20,None,None),
    ('QUAL_BATCH_NO','批次号','varchar',50,None,None),
    ('QUAL_MACHINE_ID','设备编号','varchar',20,None,None),
    ('QUAL_MATERIAL_CODE','物料编码','varchar',20,None,None),
]
for i,(code,name,dtype,length,enum_dict,desc) in enumerate(std_cols,1):
    cur.execute("INSERT INTO dg_standard_column(id,std_code,std_name,data_type,data_length,enum_dict,description) VALUES(%s,%s,%s,%s,%s,%s,%s)",(i,code,name,dtype,length,enum_dict,desc))
print(f"标准字段: {len(std_cols)}")

conn.commit()
cur.close(); conn.close()
print("DONE")
