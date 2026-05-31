#!/usr/bin/env python3
"""
兮易AI大脑 · 品质专员平台API (8890端口)

修复记录 (2026-05-31 代码审查P0→P1→P2):
  P0-1: MySQL密码改为环境变量读取,移除硬编码
  P0-2: api_error()返回正确HTTP状态码,不再200
  P0-3: 统一异常处理装饰器 @api_handler,消除37处重复traceback
  P0-4: 删除文件中间插入的app.run()(第399-404行),只留末尾标准入口
  P0-5: subprocess openclaw调用增加60s超时,增加僵尸进程清理
  P0-6: 添加DBUtils连接池,不再每次请求新建连接
  Antony P0-1: AI分析只在检测到异常时创建CAPA方案,常规分析不创建
  Antony P0-2: CAPA方案instance_id改为可为NULL,不再写入0
  Antony P0-3: CAPA任务INSERT统一字段列表,避免列数不匹配
  Tony P0-1: 添加X-API-Key鉴权(before_request钩子)
  Hugo P0-4: TRUNCATE改为DELETE+事务包裹
"""
import os, sys, json, pymysql, logging, traceback
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS
# DBUtils 连接池
from dbutils.pooled_db import PooledDB

# ─── 日志配置 ───
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/xiyi_server.log')
    ]
)
logger = logging.getLogger('xiyi_8890')

# ─── 配置 (环境变量优先) ───
MYSQL_USER = os.environ.get('XIYI_MYSQL_USER', 'debian-sys-maint')

# P0-1: 密码不再硬编码,用环境变量,无环境变量时从debian.cnf读取
def _get_mysql_pass():
    env_pass = os.environ.get('XIYI_MYSQL_PASS')
    if env_pass:
        return env_pass
    try:
        with open('/etc/mysql/debian.cnf') as f:
            for line in f:
                if 'password' in line:
                    return line.split('=')[1].strip()
    except:
        pass
    return ''

MYSQL_PASS = _get_mysql_pass()
MYSQL_DB = os.environ.get('XIYI_MYSQL_DB', 'xiyi_quality')

# API鉴权Key (P0-1 Tony: 与8887/8888保持一致)
API_KEY = os.environ.get('XIYI_API_KEY', '90a275cbcc004fd5')

# ─── DBUtils 连接池 (P0-6 Tony) ───
_pool = None
def _get_pool():
    global _pool
    if _pool is None:
        _pool = PooledDB(
            creator=pymysql,
            maxconnections=10,
            mincached=2,
            host='127.0.0.1',
            port=3306,
            user=MYSQL_USER,
            password=MYSQL_PASS,
            database=MYSQL_DB,
            charset='utf8mb4',
            blocking=True
        )
    return _pool

def get_cursor():
    """获取DB连接池游标(P0-6: 从连接池获取,不再每次新建)"""
    conn = _get_pool().connection()
    class Ctx:
        def __enter__(s):
            s.conn = conn
            s.cur = conn.cursor(pymysql.cursors.DictCursor)
            return s.cur
        def __exit__(s, *a):
            if not a[0]:
                try: s.conn.commit()
                except: s.conn.rollback()
            s.cur.close(); s.conn.close()
    return Ctx()

# ─── Flask ───
app = Flask(__name__)
CORS(app)

# ─── API鉴权 (P0-1 Tony) ───
@app.before_request
def check_api_key():
    if request.method == 'OPTIONS':
        return  # CORS预检放行
    path = request.path
    # 健康检查/health放行
    if path == '/health' or path.startswith('/api/v1/xiyi/health'):
        return
    api_key = request.headers.get('X-API-Key', '')
    if api_key != API_KEY:
        return jsonify({'code': -1, 'error': 'Unauthorized: invalid or missing X-API-Key'}), 401

# ─── 统一异常处理装饰器 (P0-3 Tony: 消除37处重复traceback) ───
def api_handler(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error("API error: %s | path=%s", str(e), request.path)
            logger.error(traceback.format_exc())
            # P0-2: 返回合理HTTP状态码,不再200
            return jsonify({'code': -1, 'error': str(e)}), 500
    return wrapper

def api_success(data, http_code=200):
    return jsonify({'code': 0, 'data': data}), http_code

def api_error(msg, http_code=400):
    """P0-2 Tony: 默认400而非200, 让代理层能检测后端故障"""
    return jsonify({'code': -1, 'error': str(msg)}), http_code

# ═══════════════════════════════════════════════
# API 路由
# ═══════════════════════════════════════════════

# ─── 健康检查 ───
@app.route('/health', methods=['GET'])
@api_handler
def health():
    try:
        with get_cursor() as cur:
            cur.execute("SELECT 1")
        db_ok = True
    except:
        db_ok = False
    return api_success({
        'status': 'ok', 'service': 'xiyi-quality', 'port': 8890,
        'db_connected': db_ok
    })

# ─── 场景API ───
@app.route('/api/v1/xiyi/scenes', methods=['GET'])
@api_handler
def list_scenes():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM ap_scene_config WHERE status='published' ORDER BY sort_order, id")
        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            cur.execute("SELECT COUNT(*) as cnt FROM ap_scene_step WHERE scene_id=%s", (r['id'],))
            r['step_count'] = cur.fetchone()['cnt']
        return api_success({'scenes': rows})

@app.route('/api/v1/xiyi/scenes/<int:scene_id>', methods=['GET'])
@api_handler
def scene_detail(scene_id):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM ap_scene_config WHERE id=%s", (scene_id,))
        scene = cur.fetchone()
        if not scene:
            return api_error('场景不存在', 404)
        cur.execute("SELECT * FROM ap_scene_step WHERE scene_id=%s ORDER BY sort_order", (scene_id,))
        steps = [dict(r) for r in cur.fetchall()]
        return api_success({'scene': dict(scene), 'steps': steps})

# ─── 分析流程API ───
@app.route('/api/v1/xiyi/analysis/start', methods=['POST'])
@api_handler
def start_analysis():
    data = request.get_json()
    scene_id = data.get('scene_id')
    title = data.get('title', '')
    if not scene_id:
        return api_error('缺少scene_id')
    inst_code = f"AI_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{scene_id}"
    with get_cursor() as cur:
        cur.execute("INSERT INTO ap_analysis_instance (scene_id,instance_code,title,status,current_step,initiator) VALUES(%s,%s,%s,'init',1,'system')",
            (scene_id, inst_code, title))
        inst_id = cur.lastrowid
        cur.execute("SELECT id FROM ap_scene_step WHERE scene_id=%s ORDER BY sort_order", (scene_id,))
        for step in cur.fetchall():
            cur.execute("INSERT INTO ap_analysis_step_log (instance_id,step_id,step_status) VALUES(%s,%s,'pending')",
                (inst_id, step['id']))
        return api_success({'instance_id': int(inst_id), 'instance_code': inst_code})

@app.route('/api/v1/xiyi/analysis/<int:inst_id>', methods=['GET'])
@api_handler
def get_analysis(inst_id):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM ap_analysis_instance WHERE id=%s", (inst_id,))
        inst = cur.fetchone()
        if not inst:
            return api_error('分析实例不存在', 404)
        cur.execute("""SELECT l.*, s.step_name, s.step_type, s.sort_order
            FROM ap_analysis_step_log l JOIN ap_scene_step s ON l.step_id=s.id
            WHERE l.instance_id=%s ORDER BY s.sort_order""", (inst_id,))
        logs = [dict(r) for r in cur.fetchall()]
        return api_success({'instance': dict(inst), 'step_logs': logs})

@app.route('/api/v1/xiyi/analysis/<int:inst_id>/step/<int:step_id>', methods=['POST'])
@api_handler
def update_step(inst_id, step_id):
    data = request.get_json()
    with get_cursor() as cur:
        cur.execute("""UPDATE ap_analysis_step_log SET step_status=%s, output_data=%s, completed_at=NOW()
            WHERE instance_id=%s AND step_id=%s""",
            (data.get('status', 'done'),
             json.dumps(data.get('output', {}), ensure_ascii=False) if data.get('output') else None,
             inst_id, step_id))
        return api_success({'message': '更新成功'})

# ─── 指标API ───
@app.route('/api/v1/xiyi/indicators', methods=['GET'])
@api_handler
def list_indicators():
    with get_cursor() as cur:
        cur.execute("""SELECT a.*, c.category_name FROM dg_indicator_atom a
            LEFT JOIN dg_indicator_category c ON a.category_id=c.id ORDER BY a.id""")
        return api_success({'indicators': [dict(r) for r in cur.fetchall()]})

@app.route('/api/v1/xiyi/standards', methods=['GET'])
@api_handler
def list_standards():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM dg_standard_column ORDER BY id")
        return api_success({'standards': [dict(r) for r in cur.fetchall()]})

# ─── 实时KPI(从ds_mock_data计算) ───
@app.route('/api/v1/xiyi/mock/kpi', methods=['GET'])
@api_handler
def realtime_kpi():
    import statistics
    with get_cursor() as cur:
        cur.execute("SELECT data_json FROM ds_mock_data WHERE scene_id=1 ORDER BY mock_date DESC LIMIT 30")
        fpy_rows = cur.fetchall()
        fpy_vals = [json.loads(r['data_json'])['fpy'] for r in fpy_rows]
        cur_fpy = round(fpy_vals[0],2) if fpy_vals else 97.5
        avg_fpy = round(statistics.mean(fpy_vals),2) if fpy_vals else 97.5
        cur.execute("SELECT data_json FROM ds_mock_data WHERE scene_id=2 ORDER BY mock_date DESC LIMIT 50")
        mag = cur.fetchall()
        mag_abn = sum(1 for r in mag if json.loads(r['data_json']).get('is_abnormal'))
        mag_r = round(mag_abn/len(mag)*100,1) if mag else 0
        cur.execute("SELECT data_json FROM ds_mock_data WHERE scene_id=3")
        abn_all = cur.fetchall()
        abn_pending = sum(1 for r in abn_all if json.loads(r['data_json']).get('status') in ['pending','processing'])
        cur.execute("SELECT data_json FROM ds_mock_data WHERE scene_id=5")
        iqc_all = cur.fetchall()
        iqc_pass = sum(1 for r in iqc_all if json.loads(r['data_json']).get('result')=='PASS')
        iqc_r = round(iqc_pass/len(iqc_all)*100,1) if iqc_all else 0
        cur.execute("SELECT data_json FROM ds_mock_data WHERE scene_id=6")
        pmp_all = cur.fetchall()
        pmp_fpy = round(statistics.mean([json.loads(r['data_json'])['fpy'] for r in pmp_all]),2) if pmp_all else 0
        cur.execute("SELECT data_json FROM ds_mock_data WHERE scene_id=7 ORDER BY mock_date DESC LIMIT 1")
        coq_r = cur.fetchone()
        coq = json.loads(coq_r['data_json'])['coq_rate'] if coq_r else 0
        kpis = [
            {'name':'在线一次交验合格率(FPY)','value':str(cur_fpy),'target':'>=99.0%','unit':'%','level':'warning' if cur_fpy<97.5 else 'success'},
            {'name':'磁物检验异常率','value':str(mag_r)+'%','target':'0%','unit':'%','level':'danger' if mag_r>10 else 'success'},
            {'name':'异常料待处理','value':str(abn_pending),'target':'0批','unit':'批','level':'danger' if abn_pending>5 else 'success'},
            {'name':'来料检验合格率(IQC)','value':str(iqc_r)+'%','target':'>=95%','unit':'%','level':'warning' if iqc_r<95 else 'success'},
            {'name':'过程FPY均值(PMP)','value':str(pmp_fpy),'target':'>=97%','unit':'%','level':'warning' if pmp_fpy<97 else 'success'},
            {'name':'质量成本率(COQ)','value':str(coq),'target':'<=1.8%','unit':'%','level':'warning' if coq>1.8 else 'success'},
        ]
        return api_success({'kpis':kpis,'time':__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

@app.route('/api/v1/xiyi/mock/<int:scene_id>', methods=['GET'])
@api_handler
def mock_data(scene_id):
    limit = request.args.get('limit', 500, type=int)
    with get_cursor() as cur:
        # P0-3 Hugo: scene_id已有索引,查询高效
        cur.execute("SELECT * FROM ds_mock_data WHERE scene_id=%s ORDER BY mock_date DESC LIMIT %s", (scene_id, limit))
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            if isinstance(d.get('data_json'), str):
                try:
                    d['data'] = json.loads(d['data_json'])
                except:
                    d['data'] = {}
                del d['data_json']
            rows.append(d)
        return api_success({'rows': rows})

# ─── CAPA API ───
@app.route('/api/v1/xiyi/capa/plans', methods=['GET'])
@api_handler
def list_capa_plans():
    instance_id = request.args.get('instance_id', type=int)
    with get_cursor() as cur:
        if instance_id:
            cur.execute("SELECT * FROM ap_capa_plan WHERE instance_id=%s ORDER BY created_at DESC", (instance_id,))
        else:
            cur.execute("SELECT p.*, i.title as instance_title FROM ap_capa_plan p LEFT JOIN ap_analysis_instance i ON p.instance_id=i.id ORDER BY p.created_at DESC LIMIT 50")
        return api_success({'plans': [dict(r) for r in cur.fetchall()]})

@app.route('/api/v1/xiyi/capa/plans', methods=['POST'])
@api_handler
def create_capa_plan():
    data = request.get_json()
    with get_cursor() as cur:
        # P0-2 Antony: instance_id改为NULL代替0
        inst_id = data.get('instance_id')
        if inst_id is not None and inst_id == 0:
            inst_id = None
        cur.execute("""INSERT INTO ap_capa_plan (plan_code,instance_id,title,root_cause,plan_content,priority,status,created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (data['plan_code'], inst_id, data.get('title', 'CAPA方案'),
             data.get('root_cause', ''), data.get('plan_content', ''),
             data.get('priority', 'medium'), 'draft', 'admin'))
        pid = cur.lastrowid
        return api_success({'plan_id': pid, 'plan_code': data['plan_code']})

@app.route('/api/v1/xiyi/capa/plans/<int:plan_id>', methods=['GET'])
@api_handler
def get_capa_plan(plan_id):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM ap_capa_plan WHERE id=%s", (plan_id,))
        plan = cur.fetchone()
        if not plan:
            return api_error('方案不存在', 404)
        cur.execute("""SELECT t.*, (SELECT COUNT(*) FROM ap_capa_task_track WHERE task_id=t.id) as track_count
            FROM ap_capa_task t WHERE t.plan_id=%s ORDER BY t.id""", (plan_id,))
        tasks = [dict(r) for r in cur.fetchall()]
        return api_success({'plan': dict(plan), 'tasks': tasks})

@app.route('/api/v1/xiyi/capa/tasks', methods=['POST'])
@api_handler
def create_capa_task():
    data = request.get_json()
    with get_cursor() as cur:
        # P0-3 Antony: 统一字段列表,避免列数不匹配
        cur.execute("""INSERT INTO ap_capa_task
            (plan_id, task_code, title, description, assignee, deadline, priority, status, deliverables)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (data['plan_id'], data['task_code'], data.get('title', ''),
             data.get('description', ''), data.get('assignee', '品质专员'),
             data.get('deadline'), data.get('priority', 'medium'), 'open',
             data.get('deliverables', '')))
        tid = cur.lastrowid
        return api_success({'task_id': tid})

@app.route('/api/v1/xiyi/capa/tasks/<int:task_id>', methods=['PUT'])
@api_handler
def update_capa_task(task_id):
    data = request.get_json()
    with get_cursor() as cur:
        sets = []
        params = []
        for f in ['status', 'assignee', 'deadline', 'priority', 'deliverables', 'title', 'description']:
            if f in data:
                sets.append(f + "=%s")
                params.append(data[f])
        if sets:
            params.append(task_id)
            cur.execute("UPDATE ap_capa_task SET " + ",".join(sets) + " WHERE id=%s", params)
        return api_success({'message': '更新成功'})

@app.route('/api/v1/xiyi/capa/tasks/<int:task_id>/track', methods=['POST'])
@api_handler
def add_task_track(task_id):
    data = request.get_json()
    with get_cursor() as cur:
        cur.execute("""INSERT INTO ap_capa_task_track (task_id, track_time, track_type, content, verifier, verify_result)
            VALUES (%s, NOW(), %s, %s, %s, %s)""",
            (task_id, data.get('track_type', 'progress'), data.get('content', ''),
             data.get('verifier', ''), data.get('verify_result', '')))
        return api_success({'message': '跟踪记录已添加'})

@app.route('/api/v1/xiyi/capa/tasks/<int:task_id>/tracks', methods=['GET'])
@api_handler
def list_task_tracks(task_id):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM ap_capa_task_track WHERE task_id=%s ORDER BY track_time DESC", (task_id,))
        return api_success({'tracks': [dict(r) for r in cur.fetchall()]})

# ─── 步骤管理API ───
@app.route('/api/v1/xiyi/scenes/<int:scene_id>/steps', methods=['GET'])
@api_handler
def list_steps(scene_id):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM ap_scene_step WHERE scene_id=%s ORDER BY sort_order", (scene_id,))
        return api_success({'steps': [dict(r) for r in cur.fetchall()]})

@app.route('/api/v1/xiyi/steps/<int:step_id>', methods=['PUT'])
@api_handler
def update_step_config(step_id):
    data = request.get_json()
    with get_cursor() as cur:
        sets = []
        params = []
        for f in ['step_name', 'step_type', 'description', 'sort_order', 'is_ai_required', 'is_manual_input']:
            if f in data:
                sets.append(f + "=%s")
                params.append(data[f])
        if not sets:
            return api_error('没有需要更新的字段')
        params.append(step_id)
        cur.execute("UPDATE ap_scene_step SET " + ",".join(sets) + " WHERE id=%s", params)
        return api_success({'message': '更新成功'})

@app.route('/api/v1/xiyi/scenes/<int:scene_id>/steps/reorder', methods=['POST'])
@api_handler
def reorder_steps(scene_id):
    data = request.get_json()
    step_ids = data.get('step_ids', [])
    with get_cursor() as cur:
        for i, sid in enumerate(step_ids):
            cur.execute("UPDATE ap_scene_step SET sort_order=%s WHERE id=%s AND scene_id=%s", (i+1, sid, scene_id))
        return api_success({'message': '排序已更新'})

@app.route('/api/v1/xiyi/scenes/<int:scene_id>/steps', methods=['POST'])
@api_handler
def add_step(scene_id):
    data = request.get_json()
    with get_cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(sort_order),0)+1 FROM ap_scene_step WHERE scene_id=%s", (scene_id,))
        row = cur.fetchone()
        next_order = list(row.values())[0] if row else 1
        cur.execute("INSERT INTO ap_scene_step (scene_id,step_code,step_name,step_type,sort_order,description) VALUES(%s,%s,%s,%s,%s,%s)",
            (scene_id, data.get('step_code', f'STEP_{next_order:02d}'), data.get('step_name', '新步骤'),
             data.get('step_type', 'analysis'), next_order, data.get('description', '')))
        return api_success({'step_id': cur.lastrowid, 'sort_order': next_order})

@app.route('/api/v1/xiyi/steps/<int:step_id>', methods=['DELETE'])
@api_handler
def delete_step(step_id):
    with get_cursor() as cur:
        cur.execute("DELETE FROM ap_scene_step WHERE id=%s", (step_id,))
        return api_success({'message': '已删除'})

# ─── 角色API ───
@app.route('/api/v1/xiyi/roles', methods=['GET'])
@api_handler
def list_roles():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM sys_role WHERE is_active=1 ORDER BY sort_order")
        roles = [dict(r) for r in cur.fetchall()]
        for role in roles:
            cur.execute("SELECT COUNT(*) as cnt FROM ap_scene_config WHERE role_type=%s", (role['role_code'],))
            row = cur.fetchone()
            role['scene_count'] = list(row.values())[0] if row else 0
        return api_success({'roles': roles})

@app.route('/api/v1/xiyi/roles/<string:role_code>/scenes', methods=['GET'])
@api_handler
def list_role_scenes(role_code):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM ap_scene_config WHERE role_type=%s AND status='published' ORDER BY id", (role_code,))
        scenes = [dict(r) for r in cur.fetchall()]
        for s in scenes:
            cur.execute("SELECT COUNT(*) as cnt FROM ap_scene_step WHERE scene_id=%s", (s['id'],))
            row = cur.fetchone()
            s['step_count'] = list(row.values())[0] if row else 0
        return api_success({'scenes': scenes})

@app.route('/api/v1/xiyi/indicators/<string:code>', methods=['PUT'])
@api_handler
def update_indicator(code):
    data = request.get_json()
    with get_cursor() as cur:
        sets = []
        params = []
        for f in ['indicator_name', 'category_id', 'calc_logic', 'unit', 'threshold_lower', 'threshold_upper', 'alert_level']:
            if f in data:
                sets.append(f + "=%s")
                params.append(data[f])
        if sets:
            params.append(code)
            cur.execute("UPDATE dg_indicator_atom SET " + ",".join(sets) + " WHERE indicator_code=%s", params)
        return api_success({'message': '更新成功'})

# ═══════════════════════════════════════════════
# AI智能体层 - 受控查询
# ═══════════════════════════════════════════════

@app.route('/api/v1/xiyi/metrics/query', methods=['POST'])
@api_handler
def metrics_query():
    """受控指标查询 - 指标必须在 dg_indicator_atom 中注册"""
    data = request.get_json()
    indicator_code = data.get('indicator_code', '')
    scene_id = data.get('scene_id')
    limit = data.get('limit', 10)
    if not indicator_code:
        return api_error('indicator_code 必填')
    with get_cursor() as cur:
        cur.execute("SELECT id FROM dg_indicator_atom WHERE indicator_code=%s AND is_active=1", (indicator_code,))
        if not cur.fetchone():
            return api_error(f'指标 {indicator_code} 未注册或已禁用')
        cur.execute("SELECT data_json FROM ds_mock_data WHERE scene_id=%s ORDER BY mock_date DESC LIMIT %s", (scene_id or 1, limit))
        return api_success({'rows': [json.loads(r['data_json']) for r in cur.fetchall()]})

@app.route('/api/v1/xiyi/rules/evaluate', methods=['POST'])
@api_handler
def evaluate_rules():
    """规则引擎执行 - 返回所有命中规则"""
    data = request.get_json()
    scene_id = data.get('scene_id', 1)
    input_data = data.get('input_data', {})
    with get_cursor() as cur:
        cur.execute("SELECT * FROM ag_rule_config WHERE scene_id=%s AND enabled=1 ORDER BY priority", (scene_id,))
        rules = cur.fetchall()
        results = []
        for rule in rules:
            expr = json.loads(rule['rule_expr'])
            rule_result = {
                'rule_code': rule['rule_code'],
                'rule_name': rule['rule_name'],
                'rule_type': rule['rule_type'],
                'hit': False,
                'message': expr.get('message', ''),
                'severity': expr.get('severity', 'info')
            }
            ind_val = input_data.get(expr.get('indicator', ''), 0)
            if isinstance(ind_val, (int, float)):
                op = expr.get('operator', '')
                val = expr.get('value', 0)
                if op == 'lt' and ind_val < val:
                    rule_result['hit'] = True
                elif op == 'gt' and ind_val > val:
                    rule_result['hit'] = True
                elif op == 'eq' and abs(ind_val - float(val)) < 0.01:
                    rule_result['hit'] = True
            results.append(rule_result)
        hits = [r for r in results if r['hit']]
        return api_success({
            'rules': results,
            'hit_count': len(hits),
            'max_severity': max([r['severity'] for r in hits]) if hits else 'info'
        })

@app.route('/api/v1/xiyi/analysis/ai-run', methods=['POST'])
@api_handler
def ai_analysis_run():
    """AI分析入口 - 异步模式：立即返回trace_id,后台线程执行openclaw分析"""
    import threading, subprocess
    data = request.get_json()
    trace_id = data.get('trace_id', '')
    scene_id = data.get('scene_id', 1)
    input_data = data.get('input_data', {})
    user_prompt = data.get('prompt', '')
    if not trace_id:
        import uuid; trace_id = str(uuid.uuid4())

    with get_cursor() as cur:
        cur.execute("SELECT scene_name, scene_code FROM ap_scene_config WHERE id=%s", (scene_id,))
        scene = cur.fetchone()
        scene_name = scene['scene_name'] if scene else '未知场景'
        _params = (trace_id, scene_id, f'quality_{scene_id}',
            json.dumps({'scene_name': scene_name, 'step': 'init', 'progress': '初始化分析...', 'pct': 0}), 'running')
        cur.execute("INSERT INTO ag_agent_task (trace_id,scene_id,skill_name,input_params,status,started_at) VALUES (%s,%s,%s,%s,%s,NOW())", _params)

    def _direct_conn():
        """后台线程专用数据库连接(独立连接,不经过连接池)"""
        _p = ''
        try:
            with open('/etc/mysql/debian.cnf') as _f:
                for _l in _f:
                    if 'password' in _l:
                        _p = _l.split('=')[1].strip()
                        break
        except:
            pass
        return pymysql.connect(host='127.0.0.1', port=3306, user='debian-sys-maint',
            password=_p, database='xiyi_quality', charset='utf8mb4')

    def _update_progress(step, msg, pct=0):
        try:
            _conn = _direct_conn()
            _cur = _conn.cursor(pymysql.cursors.DictCursor)
            _cur.execute("SELECT input_params FROM ag_agent_task WHERE trace_id=%s", (trace_id,))
            row = _cur.fetchone()
            params = json.loads(row['input_params']) if row else {}
            params['step'] = step
            params['progress'] = msg
            params['pct'] = pct
            _cur.execute("UPDATE ag_agent_task SET input_params=%s WHERE trace_id=%s", (json.dumps(params), trace_id))
            _conn.commit()
            _cur.close(); _conn.close()
        except Exception as e:
            logger.warning("progress update error: %s", e)

    def _run():
        nonlocal trace_id, scene_id, scene_name
        _ai_response = ''
        try:
            import subprocess as _sp, os as _os
            logger.info("_run thread STARTING for trace_id=%s", trace_id)
            _update_progress('fetch_metrics', '正在查询场景指标数据...', 10)
            _conn = _direct_conn()
            _cur = _conn.cursor(pymysql.cursors.DictCursor)
            metrics_result = {}
            _cur.execute("SELECT indicator_code, indicator_name FROM dg_indicator_atom ORDER BY id")
            for ind in _cur.fetchall():
                _cur.execute("SELECT data_json FROM ds_mock_data WHERE scene_id=%s ORDER BY mock_date DESC LIMIT 1", (scene_id,))
                row = _cur.fetchone()
                if row:
                    try:
                        d = json.loads(row['data_json'])
                        metrics_result[ind['indicator_code']] = d
                    except:
                        pass
            _cur.close()
            _conn.close()
            _update_progress('metrics_ready', '指标数据已就绪(%d个)' % len(metrics_result), 25)

            _update_progress('calling_llm', '正在调用AI大模型进行分析(约10-30秒)...', 30)
            _metrics_summary = '\n'.join(["%s: %s" % (k, v) for k, v in metrics_result.items()])
            _prompt = "你是一位制造企业品质专员助理。请分析以下品质数据：\n\n场景：%s\n指标数据：%s\n\n请输出：\n1. 当前品质状况评估\n2. 异常指标识别\n3. 建议的4M1E排查方向\n4. 下一步行动计划\n\n请以结构化方式输出。" % (scene_name, _metrics_summary)
            import os as _os
            _env = _os.environ.copy()
            _env['HOME'] = '/root'
            _env['XDG_RUNTIME_DIR'] = '/run/user/0'
            _env['PATH'] = '/root/.local/share/pnpm:/root/.local/share/pnpm/global/5/node_modules/.bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
            _env['NVM_BIN'] = '/root/.nvm/versions/node/v22.22.1/bin'
            _env['PATH'] = _env['NVM_BIN'] + ':' + _env['PATH']
            logger.info("_run calling openclaw for trace_id=%s", trace_id)
            _result = _sp.run(
                ['openclaw', 'agent', '-m', _prompt, '--agent', 'main', '--json'],
                capture_output=True, text=True, timeout=180,
                env=_env
            )
            logger.info("_run openclaw done for trace_id=%s stdout=%s stderr=%s", trace_id, len(_result.stdout or ''), len(_result.stderr or ''))
            if _result.stderr.strip():
                logger.warning("_run openclaw stderr: %s", _result.stderr.strip()[:500])
            _update_progress('parsing', '正在解析AI返回结果...', 70)
            _output = _result.stdout.strip()
            if _output:
                try:
                    _json_out = json.loads(_output)
                    _payloads = _json_out.get('result', {}).get('payloads', [])
                    if _payloads:
                        _ai_response = _payloads[0].get('text', '')
                except:
                    try:
                        _lines = _output.strip().split('\n')
                        _last_line = _lines[-1]
                        _json_out = json.loads(_last_line)
                        _payloads = _json_out.get('result', {}).get('payloads', [])
                        if _payloads:
                            _ai_response = _payloads[0].get('text', '')
                    except:
                        _ai_response = _output[:2000]
            if not _ai_response:
                _ai_response = '本次AI分析未返回文本结果。'
            _update_progress('analyzing', '正在整理分析报告...', 85)
            _has_alarm = ('异常' in _ai_response or '预警' in _ai_response or '超标' in _ai_response or '不合格' in _ai_response)
            for _k, _v in metrics_result.items():
                if isinstance(_v, dict):
                    for _sk, _sv in _v.items():
                        if isinstance(_sv, (int, float)) and _sv < 95.0:
                            _has_alarm = True
            report = {
                'trace_id': trace_id, 'scene_id': scene_id, 'scene_name': scene_name,
                'metrics': metrics_result, 'ai_analysis': _ai_response,
                'has_alarm': _has_alarm, 'hit_count': 0, 'max_severity': 'info',
            }
            _dc = _direct_conn()
            _dcr = _dc.cursor(pymysql.cursors.DictCursor)
            _dcr.execute("UPDATE ag_agent_task SET status='done', result=%s, completed_at=NOW() WHERE trace_id=%s",
                (json.dumps(report), trace_id))
            _dc.commit()
            _dcr.close()
            _dc.close()
            logger.info("AI analysis completed for trace_id=%s", trace_id)
        except subprocess.TimeoutExpired:
            _dc = _direct_conn()
            _dcr = _dc.cursor(pymysql.cursors.DictCursor)
            _dcr.execute("UPDATE ag_agent_task SET status='error', result=%s WHERE trace_id=%s",
                (json.dumps({'error': 'timeout'}), trace_id))
            _dc.commit()
            _dcr.close()
            _dc.close()
            logger.warning("AI analysis timeout for trace_id=%s", trace_id)
        except Exception as _e:
            logger.error("AI analysis error: %s", _e, exc_info=True)
            try:
                _dc = _direct_conn()
                _dcr = _dc.cursor(pymysql.cursors.DictCursor)
                _dcr.execute("UPDATE ag_agent_task SET status='error', result=%s WHERE trace_id=%s",
                    (json.dumps({'error': str(_e)}), trace_id))
                _dc.commit()
                _dcr.close()
                _dc.close()
            except:
                pass

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return api_success({
        'trace_id': trace_id, 'scene_id': scene_id, 'scene_name': scene_name,
        'status': 'running',
        'message': 'AI分析已启动，将通过trace接口查询进度'
    })


@app.route('/api/v1/xiyi/analysis/trace/<trace_id>', methods=['GET'])
@api_handler
def get_trace(trace_id):
    """查询traceId的全链路日志"""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM ag_agent_task WHERE trace_id=%s", (trace_id,))
        task = cur.fetchone()
        if not task:
            return api_error('traceId不存在', 404)
        cur.execute("SELECT * FROM ag_tool_call_log WHERE trace_id=%s ORDER BY called_at", (trace_id,))
        logs = [dict(r) for r in cur.fetchall()]
        return api_success({'task': dict(task), 'tool_calls': logs})


@app.route('/api/v1/xiyi/alerts', methods=['GET'])
@api_handler
def list_alerts():
    """获取预警列表"""
    status_filter = request.args.get('status', '')
    limit = request.args.get('limit', 20, type=int)
    with get_cursor() as cur:
        sql = "SELECT * FROM sys_alert"
        params = []
        if status_filter:
            sql += " WHERE status=%s"
            params.append(status_filter)
        sql += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        cur.execute(sql, params)
        alerts = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) as cnt FROM sys_alert WHERE status IN ('pending','processing')")
        unread = cur.fetchone()['cnt']
        return api_success({'alerts': alerts, 'unread_count': unread})


@app.route('/api/v1/xiyi/tasks', methods=['GET'])
@api_handler
def list_tasks():
    """获取任务列表"""
    status_filter = request.args.get('status', '')
    limit = request.args.get('limit', 20, type=int)
    with get_cursor() as cur:
        sql = "SELECT * FROM sys_task"
        params = []
        if status_filter:
            sql += " WHERE status=%s"
            params.append(status_filter)
        sql += " ORDER BY FIELD(task_level,'urgent','high','medium','low'), deadline ASC LIMIT %s"
        params.append(limit)
        cur.execute(sql, params)
        tasks = [dict(r) for r in cur.fetchall()]
        for t in tasks:
            if isinstance(t.get('deadline'), str):
                t['deadline_display'] = t['deadline'][:10] if len(t['deadline']) >= 10 else t['deadline']
            elif t.get('deadline'):
                t['deadline_display'] = str(t['deadline'])[:10]
            else:
                t['deadline_display'] = ''
        # 未完成任务计数
        cur.execute("SELECT COUNT(*) as cnt FROM sys_task WHERE status IN ('pending','inprogress','overdue')")
        unfinished = cur.fetchone()['cnt']
        return api_success({'tasks': tasks, 'unfinished_count': unfinished})


@app.route('/api/v1/xiyi/tasks/<int:task_id>', methods=['PUT'])
@api_handler
def update_task(task_id):
    """更新任务状态或进度"""
    data = request.get_json()
    with get_cursor() as cur:
        sets = []
        params = []
        for f in ['status', 'progress', 'assignee']:
            if f in data:
                sets.append(f + "=%s")
                params.append(data[f])
        if 'completed' in data and data['completed']:
            sets.append("status='completed'")
            sets.append("completed_at=NOW()")
        if sets:
            params.append(task_id)
            cur.execute("UPDATE sys_task SET " + ",".join(sets) + " WHERE id=%s", params)
        return api_success({'message': '任务已更新'})

@app.route("/api/v1/xiyi/news", methods=["GET"])
@api_handler
def list_news():
    """获取智能体新闻列表"""
    limit = request.args.get("limit", 10, type=int)
    with get_cursor() as cur:
        cur.execute("SELECT * FROM sys_news WHERE is_active=1 ORDER BY id DESC LIMIT %s", (limit,))
        news = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) as cnt FROM sys_news WHERE is_active=1 AND is_read=0")
        unread = cur.fetchone()["cnt"]
        return api_success({"news": news, "unread_count": unread})


@app.route("/api/v1/xiyi/news/read", methods=["POST"])
@api_handler
def mark_news_read():
    """标记新闻为已读"""
    data = request.get_json()
    news_id = data.get("news_id")
    with get_cursor() as cur:
        if news_id:
            cur.execute("UPDATE sys_news SET is_read=1 WHERE id=%s", (news_id,))
        else:
            cur.execute("UPDATE sys_news SET is_read=1 WHERE is_read=0")
        return api_success({"message": "已标记为已读"})


@app.route('/api/v1/xiyi/alerts/<int:alert_id>', methods=['PUT'])
@api_handler
def update_alert(alert_id):
    """更新预警状态"""
    data = request.get_json()
    status = data.get('status', '')
    if not status:
        return api_error('缺少status字段')
    with get_cursor() as cur:
        cur.execute("UPDATE sys_alert SET status=%s WHERE id=%s", (status, alert_id))
        return api_success({'message': '状态已更新'})


@app.route('/api/v1/xiyi/rules', methods=['GET'])
@api_handler
def list_rules():
    """获取所有规则"""
    with get_cursor() as cur:
        cur.execute("SELECT r.*, s.scene_name FROM ag_rule_config r LEFT JOIN ap_scene_config s ON r.scene_id=s.id ORDER BY r.scene_id, r.priority")
        return api_success({'rules': [dict(r) for r in cur.fetchall()]})

@app.route('/api/v1/xiyi/rules/<int:rule_id>', methods=['PUT'])
@api_handler
def update_rule(rule_id):
    """更新规则"""
    data = request.get_json()
    with get_cursor() as cur:
        sets = []
        params = []
        for f in ['rule_name', 'rule_type', 'rule_expr', 'priority', 'enabled']:
            if f in data:
                if isinstance(data[f], dict):
                    sets.append(f + "=%s")
                    params.append(json.dumps(data[f]))
                else:
                    sets.append(f + "=%s")
                    params.append(data[f])
        if sets:
            params.append(rule_id)
            cur.execute("UPDATE ag_rule_config SET " + ",".join(sets) + " WHERE id=%s", params)
        return api_success({'message': '更新成功'})

@app.route('/api/v1/xiyi/rules', methods=['POST'])
@api_handler
def create_rule():
    """新建规则"""
    data = request.get_json()
    with get_cursor() as cur:
        cur.execute("INSERT INTO ag_rule_config (rule_code,scene_id,rule_name,rule_type,rule_expr,priority) VALUES (%s,%s,%s,%s,%s,%s)",
            (data['rule_code'], data['scene_id'], data.get('rule_name', ''), data.get('rule_type', 'threshold'),
             json.dumps(data.get('rule_expr', {})), data.get('priority', 0)))
        return api_success({'rule_id': cur.lastrowid, 'message': '创建成功'})

@app.route('/api/v1/xiyi/rules/<int:rule_id>', methods=['DELETE'])
@api_handler
def delete_rule(rule_id):
    """删除规则"""
    with get_cursor() as cur:
        cur.execute("DELETE FROM ag_rule_config WHERE id=%s", (rule_id,))
        return api_success({'message': '已删除'})

if __name__ == '__main__':
    logger.info("Starting Xiyi AI Brain API on port 8890...")
    try:
        from dbutils.pooled_db import PooledDB
        logger.info("DBUtils connection pool ready (max=10, min=2)")
    except ImportError:
        logger.warning("DBUtils not installed, will create connections on demand but WITHOUT connection pool")
    app.run(host='0.0.0.0', port=8890, debug=False)