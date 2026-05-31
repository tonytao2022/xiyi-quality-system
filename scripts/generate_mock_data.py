#!/usr/bin/env python3
"""生成模拟质检数据 — 展现四层架构中的采集层能力"""
# FIXED: P2-2 统一日志格式,替换print
import pymysql, json, random, math, logging, os, csv
from datetime import datetime, timedelta, date
random.seed(42)

logger = logging.getLogger('xiyi_generate')
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[logging.StreamHandler()]
    )

# P2-3: CSV导出目录
CSV_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'mock_csv')
os.makedirs(CSV_DIR, exist_ok=True)

def export_to_csv(scene_id, rows, category_label):
    """将场景数据导出为CSV文件"""
    today_str = date.today().strftime('%Y%m%d')
    filename = f'mock_{scene_id}_{today_str}.csv'
    filepath = os.path.join(CSV_DIR, filename)
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['scene_id', 'mock_date', 'data_category', 'data_json'])
        for row in rows:
            writer.writerow(row)
    logger.info(f"  [CSV] {filename} ({category_label}, {len(rows)}条)")

# P0-1 Hugo: 从环境变量读取MySQL密码
pwd = os.environ.get('XIYI_MYSQL_PASS', '') or \
    [l.split('=')[1].strip() for l in open('/etc/mysql/debian.cnf') if 'password' in l][0]
conn = pymysql.connect(host='127.0.0.1',port=3306,user='debian-sys-maint',password=pwd,database='xiyi_quality')
cur = conn.cursor()

# FIXED: P0-6 - TRUNCATE改为DELETE+事务包裹，避免误清CSV导入的真实数据
# FIXED: P0-7 - 只删除模拟数据(is_mock=1)，保留CSV导入数据(is_mock=0)
cur.execute("BEGIN")
cur.execute("DELETE FROM ds_mock_data WHERE is_mock=1")
cur.execute("COMMIT")

mock_count = 0
# P2-3: 收集每场景CSV行
csv_rows_by_scene = {i: [] for i in range(1, 8)}

# ===== 场景1: FPY合格率管控 =====
# 模拟30天各产线的FPY数据
base_date = date(2025, 10, 1)
for day in range(30):
    d = base_date + timedelta(days=day)
    for line in ['1#烧结线','2#烧结线','3#线']:
        # FPY在96.5~98.8之间波动，正常范围
        fpy = round(97.5 + random.uniform(-1.0, 1.3), 2)
        # W40批次有一次断崖下跌
        if day >= 15 and day <= 18 and line == '2#烧结线':
            fpy = round(95.0 + random.uniform(-0.5, 0.8), 2)
        total = random.randint(180, 250)
        ok = int(total * fpy / 100)
        defect = total - ok
        top_defects = ['粒度超标','磁性物超标','水分异常','外观瑕疵']
        defect_data = {k: random.randint(1, max(2, defect//len(top_defects))) for k in top_defects}
        data = {
            'date': str(d), 'line': line, 'fpy': fpy,
            'total_qty': total, 'ok_qty': ok, 'defect_qty': defect,
            'defect_analysis': defect_data,
            'machine_status': random.choice(['normal','normal','normal','warning','normal'])
        }
        # FIXED: P0-7 - 设置is_mock=1标识模拟数据
        cur.execute("INSERT INTO ds_mock_data(scene_id,mock_date,data_category,data_json,is_mock) VALUES(1,%s,'fpy_daily',%s,1)",
            (d, json.dumps(data, ensure_ascii=False)))
        csv_rows_by_scene[1].append((1, str(d), 'fpy_daily', json.dumps(data, ensure_ascii=False)))
        mock_count += 1
logger.info(f"场景1 FPY合格率: {mock_count}条 (累计)")

# ===== 场景2: 磁物健康地图 =====
for day in range(30):
    d = base_date + timedelta(days=day)
    for machine in ['2#烧结炉','3#回转窑','1#干燥窑','4#磨机']:
        mag_value = round(random.uniform(0.5, 3.5), 2)
        is_abnormal = mag_value > 2.8
        data = {
            'date': str(d), 'machine': machine,
            'mag_iron': round(random.uniform(0.3, 1.8), 2),
            'mag_alloy': round(random.uniform(0.2, 1.5), 2),
            'temp': random.randint(650, 750),
            'vibration': round(random.uniform(0.5, 3.0), 1),
            'is_abnormal': is_abnormal,
            'risk_level': 'high' if is_abnormal else ('medium' if mag_value > 2.0 else 'low')
        }
        cur.execute("INSERT INTO ds_mock_data(scene_id,mock_date,data_category,data_json,is_mock) VALUES(2,%s,'mag_health',%s,1)",
            (d, json.dumps(data, ensure_ascii=False)))
        csv_rows_by_scene[2].append((2, str(d), 'mag_health', json.dumps(data, ensure_ascii=False)))
        mock_count += 1
logger.info(f"场景2 磁物健康: {mock_count}条 (累计)")

# ===== 场景3: 异常料跟踪 =====
for batch in range(20):
    d = base_date - timedelta(days=random.randint(0, 60))
    data = {
        'batch_no': f'W40-B{batch+1:03d}',
        'material': random.choice(['正极材料NCM811','正极材料NCM523','负极材料','电解液','隔膜']),
        'discovery_date': str(d),
        'abnormal_type': random.choice(['磁物超标','粒度异常','水分超标','外观不良','包装破损']),
        'qty_kg': round(random.uniform(200, 2000), 0),
        'unit_price': round(random.uniform(50, 500), 2),
        'status': random.choice(['pending','pending','processing','resolved','resolved']),
        'stock_location': random.choice(['A区-01','A区-05','B区-03','C区-02']),
        'supplier': random.choice(['供应商A','供应商B','供应商C','供应商D']),
    }
    cur.execute("INSERT INTO ds_mock_data(scene_id,mock_date,data_category,data_json,is_mock) VALUES(3,%s,'abnormal_stock',%s,1)",
        (d, json.dumps(data, ensure_ascii=False)))
    csv_rows_by_scene[3].append((3, str(d), 'abnormal_stock', json.dumps(data, ensure_ascii=False)))
    mock_count += 1
logger.info(f"场景3 异常料: {mock_count}条 (累计)")

# ===== 场景4: 呆滞库存 =====
for item in range(15):
    d = base_date - timedelta(days=random.randint(90, 365))
    data = {
        'material_code': f'MAT-{item+100:04d}',
        'material_name': random.choice(['老款正极粉料','停产物料A','备品备件B','实验批次料','退货料']),
        'storage_date': str(d),
        'last_move_date': str(d - timedelta(days=random.randint(90, 180))),
        'qty_kg': round(random.uniform(500, 15000), 0),
        'unit_price': round(random.uniform(20, 300), 2),
        'total_value': 0,
        'aging_days': random.randint(90, 365),
        'reason': random.choice(['订单取消','工艺变更','客户退货','替代料导入','备料过多'])
    }
    data['total_value'] = round(data['qty_kg'] * data['unit_price'], 2)
    cur.execute("INSERT INTO ds_mock_data(scene_id,mock_date,data_category,data_json,is_mock) VALUES(4,%s,'dead_stock',%s,1)",
        (d, json.dumps(data, ensure_ascii=False)))
    csv_rows_by_scene[4].append((4, str(d), 'dead_stock', json.dumps(data, ensure_ascii=False)))
    mock_count += 1
logger.info(f"场景4 呆滞库存: {mock_count}条 (累计)")

# ===== 场景5: IQC来料检验 =====
for insp in range(50):
    d = base_date - timedelta(days=random.randint(0, 30))
    mat = random.choice(['正极材料','负极材料','电解液','隔膜','铜箔','铝箔'])
    pass_val = random.random()
    is_pass = pass_val > 0.15
    data = {
        'iqc_no': f'IQC-{d.strftime("%Y%m%d")}-{insp+1:03d}',
        'material': mat,
        'supplier': random.choice(['A供应商','B供应商','C供应商','D供应商']),
        'batch_no': f'BAT-{random.randint(1000,9999)}',
        'inspect_date': str(d),
        'total_qty': random.randint(500, 5000),
        'sample_qty': random.randint(10, 50),
        'defect_qty': random.randint(0, 5) if is_pass else random.randint(5, 30),
        'result': 'PASS' if is_pass else 'FAIL',
        'defect_items': random.choice(['','粒度','磁性物','水分','包装','标识'])
    }
    if not is_pass:
        data['disposition'] = random.choice(['退货','让步接收','挑选使用','报废'])
    cur.execute("INSERT INTO ds_mock_data(scene_id,mock_date,data_category,data_json,is_mock) VALUES(5,%s,'iqc_record',%s,1)",
        (d, json.dumps(data, ensure_ascii=False)))
    csv_rows_by_scene[5].append((5, str(d), 'iqc_record', json.dumps(data, ensure_ascii=False)))
    mock_count += 1
logger.info(f"场景5 IQC: {mock_count}条 (累计)")

# ===== 场景6: PMP过程监控 =====
for day in range(30):
    d = base_date + timedelta(days=day)
    for process in ['混料','烧结','粉碎','分级','包装']:
        fpy = round(96.0 + random.uniform(-1.5, 2.0), 2)
        if process == '烧结' and day >= 10 and day <= 12:
            fpy = round(94.0 + random.uniform(-0.5, 0.5), 2)
        data = {
            'date': str(d), 'process': process,
            'fpy': fpy,
            'input_qty': random.randint(200, 400),
            'output_qty': 0,
            'defect_rate': round(random.uniform(0.5, 4.0), 2),
            'alarm_count': random.randint(0, 3) if fpy < 96 else 0,
            'machine_id': f'MC-{random.choice(["01","02","03","04","05"])}'
        }
        data['output_qty'] = int(data['input_qty'] * data['fpy'] / 100)
        cur.execute("INSERT INTO ds_mock_data(scene_id,mock_date,data_category,data_json,is_mock) VALUES(6,%s,'pmp_fpy',%s,1)",
            (d, json.dumps(data, ensure_ascii=False)))
        csv_rows_by_scene[6].append((6, str(d), 'pmp_fpy', json.dumps(data, ensure_ascii=False)))
        mock_count += 1
logger.info(f"场景6 PMP: {mock_count}条 (累计)")

# ===== 场景7: COQ质量成本 =====
for month in range(6):
    m = base_date.month - 6 + month
    y = base_date.year
    if m < 1: m += 12; y -= 1
    d = date(y, m, 1)
    sales = round(random.uniform(8000, 12000), 0)
    data = {
        'month': f'{y}-{m:02d}',
        'sales_amount': int(sales),
        'internal_loss': int(random.uniform(50, 120)),
        'external_loss': int(random.uniform(20, 60)),
        'appraisal_cost': int(random.uniform(30, 70)),
        'prevention_cost': int(random.uniform(20, 50)),
        'total_coq': 0,
        'coq_rate': 0,
        'trend': 'up' if m >= 4 else 'down'
    }
    data['total_coq'] = data['internal_loss'] + data['external_loss'] + data['appraisal_cost'] + data['prevention_cost']
    data['coq_rate'] = round(data['total_coq'] / data['sales_amount'] * 100, 2)
    cur.execute("INSERT INTO ds_mock_data(scene_id,mock_date,data_category,data_json,is_mock) VALUES(7,%s,'coq_monthly',%s,1)",
        (d, json.dumps(data, ensure_ascii=False)))
    csv_rows_by_scene[7].append((7, str(d), 'coq_monthly', json.dumps(data, ensure_ascii=False)))
    mock_count += 1
logger.info(f"场景7 COQ: {mock_count}条 (累计)")

conn.commit()
cur.close(); conn.close()

# P2-3: 导出CSV
logger.info(f"📁 导出CSV到 {CSV_DIR}/")
scene_names = {1:'FPY合格率',2:'磁物健康',3:'异常料',4:'呆滞库存',5:'IQC',6:'PMP',7:'COQ'}
for sid, rows in csv_rows_by_scene.items():
    if rows:
        export_to_csv(sid, rows, scene_names.get(sid, f'场景{sid}'))

logger.info(f"🏁 全部完成! 共生成 {mock_count} 条模拟质检数据")
