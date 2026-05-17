"""
环境公益机构 AI 应用需求调研 — Web 问卷系统
FastAPI + SQLite + Jinja2 | 单文件部署
"""

import csv
import hashlib
import io
import json
import os
import re
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

import jieba
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

# ── App Setup ──────────────────────────────────────────────

BASE = Path(__file__).parent
DB_PATH = BASE / "survey.db"
ADMIN_PASSWORD_HASH = "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"  # default: "password"

app = FastAPI(title="环境公益AI需求调研")
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

env = Environment(
    loader=FileSystemLoader(str(BASE / "templates")),
    autoescape=select_autoescape(["html"]),
)


def render(name: str, **kwargs) -> HTMLResponse:
    template = env.get_template(name)
    return HTMLResponse(template.render(**kwargs))

# ── Database ───────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT (datetime('now','localtime')),

            -- Module 1: Basic Info
            q1_org_name TEXT DEFAULT '',
            q2_role TEXT DEFAULT '',
            q3_reg_type TEXT DEFAULT '',
            q4_years TEXT DEFAULT '',
            q5_staff TEXT DEFAULT '',
            q6_fields TEXT DEFAULT '[]',

            -- Module 2: Digital Status
            q7_devices TEXT DEFAULT '[]',
            q8_network TEXT DEFAULT '',
            q9_digital_level TEXT DEFAULT '',
            q10_ai_familiarity TEXT DEFAULT '',
            q11_data_storage TEXT DEFAULT '[]',
            q12_pain_points TEXT DEFAULT '[]',

            -- Module 3-A: Content Generation
            q3a_1_writing INTEGER DEFAULT 0,
            q3a_2_news INTEGER DEFAULT 0,
            q3a_3_video INTEGER DEFAULT 0,
            q3a_4_proposal INTEGER DEFAULT 0,
            q3a_5_report INTEGER DEFAULT 0,
            q3a_6_grant INTEGER DEFAULT 0,
            q3a_7_fundraising INTEGER DEFAULT 0,

            -- Module 3-B: Data Processing
            q3b_1_activity_data INTEGER DEFAULT 0,
            q3b_2_env_monitor INTEGER DEFAULT 0,
            q3b_3_attention_check INTEGER DEFAULT 0,
            q3b_4_viz INTEGER DEFAULT 0,
            q3b_5_eval INTEGER DEFAULT 0,
            q3b_6_desensitize INTEGER DEFAULT 0,

            -- Module 3-C: Operations
            q3c_1_volunteer_schedule INTEGER DEFAULT 0,
            q3c_2_volunteer_notify INTEGER DEFAULT 0,
            q3c_3_supplies INTEGER DEFAULT 0,
            q3c_4_donor_comms INTEGER DEFAULT 0,
            q3c_5_route_planning INTEGER DEFAULT 0,

            -- Module 3-D: Environmental Professional
            q3d_1_species_data INTEGER DEFAULT 0,
            q3d_2_pollution_plan INTEGER DEFAULT 0,
            q3d_3_waste_sorting INTEGER DEFAULT 0,
            q3d_4_eco_education INTEGER DEFAULT 0,
            q3d_5_policy_check INTEGER DEFAULT 0,
            q3d_6_env_benefit INTEGER DEFAULT 0,

            q13_other_needs TEXT DEFAULT '',

            -- Module 4-A: General Knowledge Base
            q4a_1_law INTEGER DEFAULT 0,
            q4a_2_tax INTEGER DEFAULT 0,
            q4a_3_fundraising_kb INTEGER DEFAULT 0,
            q4a_4_project_mgmt INTEGER DEFAULT 0,
            q4a_5_volunteer_mgmt INTEGER DEFAULT 0,
            q4a_6_comms_templates INTEGER DEFAULT 0,
            q4a_7_best_cases INTEGER DEFAULT 0,
            q4a_8_failure_cases INTEGER DEFAULT 0,

            -- Module 4-B: Environmental Knowledge Base
            q4b_1_national_policy INTEGER DEFAULT 0,
            q4b_2_local_policy INTEGER DEFAULT 0,
            q4b_3_grant_guide INTEGER DEFAULT 0,
            q4b_4_species INTEGER DEFAULT 0,
            q4b_5_pollution_tech INTEGER DEFAULT 0,
            q4b_6_waste_recycling INTEGER DEFAULT 0,
            q4b_7_eco_restore INTEGER DEFAULT 0,
            q4b_8_env_cases INTEGER DEFAULT 0,

            -- Module 5: Preferences
            q14_learning TEXT DEFAULT '[]',
            q15_template_type TEXT DEFAULT '',
            q16_concerns TEXT DEFAULT '[]',
            q17_payment TEXT DEFAULT '',

            -- Module 6: Open
            q18_pain_point TEXT DEFAULT '',
            q19_feedback TEXT DEFAULT '',
            q20_suggestions TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY,
            password_hash TEXT NOT NULL
        );

    """)
    conn.execute(
        "INSERT OR IGNORE INTO admins (id, password_hash) VALUES (1, ?)",
        (ADMIN_PASSWORD_HASH,),
    )
    conn.commit()
    conn.close()


init_db()

# ── Helpers ────────────────────────────────────────────────

RATING_LABELS = {
    "3a": {
        "q3a_1_writing": "活动宣传文案自动生成",
        "q3a_2_news": "新闻稿/通讯稿自动撰写",
        "q3a_3_video": "短视频脚本自动生成",
        "q3a_4_proposal": "项目立项书框架生成",
        "q3a_5_report": "项目结项报告自动撰写",
        "q3a_6_grant": "资助申请书初稿生成",
        "q3a_7_fundraising": "筹款文案自动生成",
    },
    "3b": {
        "q3b_1_activity_data": "活动参与数据自动统计",
        "q3b_2_env_monitor": "环保监测数据整理分析",
        "q3b_4_viz": "数据可视化图表/看板",
        "q3b_5_eval": "项目效果量化评估",
        "q3b_6_desensitize": "敏感信息自动脱敏",
    },
    "3c": {
        "q3c_1_volunteer_schedule": "志愿者排班计划生成",
        "q3c_2_volunteer_notify": "志愿者通知自动发送",
        "q3c_3_supplies": "环保物资需求测算与分配",
        "q3c_4_donor_comms": "捐赠人维护话术生成",
        "q3c_5_route_planning": "活动路线与资源调度",
    },
    "3d": {
        "q3d_1_species_data": "物种调查数据整理与识别",
        "q3d_2_pollution_plan": "污染治理方案框架生成",
        "q3d_3_waste_sorting": "垃圾分类知识问答辅助",
        "q3d_4_eco_education": "环保科普内容生成",
        "q3d_5_policy_check": "政策法规自动比对审查",
        "q3d_6_env_benefit": "环境效益量化估算",
    },
    "4a": {
        "q4a_1_law": "公益法律法规库",
        "q4a_2_tax": "财税优惠政策库",
        "q4a_3_fundraising_kb": "筹款运营知识库",
        "q4a_4_project_mgmt": "项目管理知识库",
        "q4a_5_volunteer_mgmt": "志愿者管理知识库",
        "q4a_6_comms_templates": "公益传播素材模板库",
        "q4a_7_best_cases": "行业优秀案例库",
        "q4a_8_failure_cases": "项目失败经验库",
    },
    "4b": {
        "q4b_1_national_policy": "国家环保政策法规库",
        "q4b_2_local_policy": "地方环保条例库",
        "q4b_3_grant_guide": "环保项目申报指南库",
        "q4b_4_species": "动植物识别图谱库",
        "q4b_5_pollution_tech": "污染治理技术方案库",
        "q4b_6_waste_recycling": "垃圾分类标准方案库",
        "q4b_7_eco_restore": "生态修复技术方案库",
        "q4b_8_env_cases": "环保公益项目案例库",
    },
}

PAIN_POINT_LABELS = {
    "writing": "文案/传播内容撰写",
    "data": "项目数据收集与分析",
    "grant": "资助申请/报告撰写",
    "volunteer": "志愿者排班调度",
    "knowledge": "环保专业知识查找",
    "policy": "政策法规跟踪合规",
    "fundraising": "筹款与捐赠人沟通",
    "experience": "内部经验知识沉淀",
}


def compute_stats():
    """Compute aggregate statistics for the dashboard."""
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0]

    if total == 0:
        conn.close()
        return {"total": 0, "ready": False}

    # ── Rating module top-N ──
    rating_results = {}
    for module, items in RATING_LABELS.items():
        scores = []
        for col, label in items.items():
            rows = conn.execute(
                f"SELECT {col} FROM responses WHERE {col} > 0"
            ).fetchall()
            if rows:
                vals = [r[0] for r in rows]
                avg = round(sum(vals) / len(vals), 2)
                pct5 = round(sum(1 for v in vals if v >= 4) / total * 100, 1)
                scores.append({"label": label, "avg": avg, "pct_high": pct5, "n": len(vals)})
        scores.sort(key=lambda x: x["avg"], reverse=True)
        rating_results[module] = scores

    # ── Pain points (Q12) ──
    pain_rows = conn.execute("SELECT q12_pain_points FROM responses").fetchall()
    pain_counter = Counter()
    for row in pain_rows:
        try:
            items = json.loads(row[0])
            for item in items:
                pain_counter[item] += 1
        except (json.JSONDecodeError, TypeError):
            pass
    pain_data = []
    for key, label in PAIN_POINT_LABELS.items():
        pain_data.append({"key": key, "label": label, "count": pain_counter.get(key, 0)})
    pain_data.sort(key=lambda x: x["count"], reverse=True)

    # ── AI familiarity (Q10) ──
    ai_fam_rows = conn.execute(
        "SELECT q10_ai_familiarity, COUNT(*) FROM responses WHERE q10_ai_familiarity != '' GROUP BY 1"
    ).fetchall()
    ai_fam_data = [{"label": r[0], "count": r[1]} for r in ai_fam_rows]

    # ── Digital level (Q9) ──
    dig_rows = conn.execute(
        "SELECT q9_digital_level, COUNT(*) FROM responses WHERE q9_digital_level != '' GROUP BY 1"
    ).fetchall()
    dig_data = [{"label": r[0], "count": r[1]} for r in dig_rows]

    # ── Word cloud from Q18 ──
    open_rows = conn.execute(
        "SELECT q18_pain_point FROM responses WHERE q18_pain_point != ''"
    ).fetchall()
    all_text = " ".join(r[0] for r in open_rows)
    words = jieba.lcut(all_text)
    stopwords = {
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
        "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
        "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那", "些",
        "什么", "怎么", "如何", "为什么", "可以", "需要", "希望", "能够",
        "现在", "目前", "我们", "他们", "你们", "这个", "那个", "比较",
        "非常", "特别", "觉得", "认为", "因为", "所以", "但是", "不过",
        "还是", "已经", "可能", "应该", "如果", "虽然", "而且", "然后",
        "问题", "工作", "方面", "进行", "通过", "使用", "对于", "以及",
        "等", "之", "或", "与", "及", "其", "所", "以", "于", "被", "把",
        "从", "向", "对", "让", "将", "为", "更", "还", "只", "又", "才",
        "中", "啊", "吧", "呢", "吗", "哦", "嗯", "啦", "的", "地", "得",
    }
    word_freq = Counter()
    for w in words:
        w = w.strip()
        if len(w) >= 2 and w not in stopwords and not re.match(r'^[\d\.\s\W]+$', w):
            word_freq[w] += 1
    word_cloud = [{"text": w, "weight": c} for w, c in word_freq.most_common(80)]

    conn.close()
    return {
        "total": total,
        "ready": True,
        "rating_results": rating_results,
        "pain_data": pain_data,
        "ai_fam_data": ai_fam_data,
        "dig_data": dig_data,
        "word_cloud": word_cloud,
    }


def parse_int(val, default=0):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def parse_json_array(val):
    """Parse comma-separated or JSON array string."""
    if not val:
        return "[]"
    val = val.strip()
    if val.startswith("["):
        return val
    items = [v.strip() for v in val.split(",") if v.strip()]
    return json.dumps(items, ensure_ascii=False)


# ── Routes: Survey ─────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def survey_form(request: Request):
    return render("survey.html", request=request)


@app.post("/submit")
async def submit_survey(request: Request):
    form = await request.form()

    def get(key, default=""):
        v = form.get(key, default)
        return v if v else default

    def get_json(key):
        return parse_json_array(form.get(key, ""))

    conn = get_db()
    cols = [
        "q1_org_name", "q2_role", "q3_reg_type", "q4_years", "q5_staff",
        "q6_fields", "q7_devices", "q8_network", "q9_digital_level",
        "q10_ai_familiarity", "q11_data_storage", "q12_pain_points",
        "q3a_1_writing", "q3a_2_news", "q3a_3_video", "q3a_4_proposal",
        "q3a_5_report", "q3a_6_grant", "q3a_7_fundraising",
        "q3b_1_activity_data", "q3b_2_env_monitor", "q3b_3_attention_check",
        "q3b_4_viz", "q3b_5_eval", "q3b_6_desensitize",
        "q3c_1_volunteer_schedule", "q3c_2_volunteer_notify",
        "q3c_3_supplies", "q3c_4_donor_comms", "q3c_5_route_planning",
        "q3d_1_species_data", "q3d_2_pollution_plan", "q3d_3_waste_sorting",
        "q3d_4_eco_education", "q3d_5_policy_check", "q3d_6_env_benefit",
        "q13_other_needs",
        "q4a_1_law", "q4a_2_tax", "q4a_3_fundraising_kb", "q4a_4_project_mgmt",
        "q4a_5_volunteer_mgmt", "q4a_6_comms_templates",
        "q4a_7_best_cases", "q4a_8_failure_cases",
        "q4b_1_national_policy", "q4b_2_local_policy",
        "q4b_3_grant_guide", "q4b_4_species", "q4b_5_pollution_tech",
        "q4b_6_waste_recycling", "q4b_7_eco_restore", "q4b_8_env_cases",
        "q14_learning", "q15_template_type", "q16_concerns", "q17_payment",
        "q18_pain_point", "q19_feedback", "q20_suggestions",
    ]

    vals = [
        get("q1_org_name"), get("q2_role"), get("q3_reg_type"),
        get("q4_years"), get("q5_staff"),
        get_json("q6_fields"), get_json("q7_devices"), get("q8_network"),
        get("q9_digital_level"), get("q10_ai_familiarity"),
        get_json("q11_data_storage"), get_json("q12_pain_points"),
        parse_int(get("q3a_1")), parse_int(get("q3a_2")),
        parse_int(get("q3a_3")), parse_int(get("q3a_4")),
        parse_int(get("q3a_5")), parse_int(get("q3a_6")),
        parse_int(get("q3a_7")),
        parse_int(get("q3b_1")), parse_int(get("q3b_2")),
        parse_int(get("q3b_3")), parse_int(get("q3b_4")),
        parse_int(get("q3b_5")), parse_int(get("q3b_6")),
        parse_int(get("q3c_1")), parse_int(get("q3c_2")),
        parse_int(get("q3c_3")), parse_int(get("q3c_4")),
        parse_int(get("q3c_5")),
        parse_int(get("q3d_1")), parse_int(get("q3d_2")),
        parse_int(get("q3d_3")), parse_int(get("q3d_4")),
        parse_int(get("q3d_5")), parse_int(get("q3d_6")),
        get("q13_other_needs"),
        parse_int(get("q4a_1")), parse_int(get("q4a_2")),
        parse_int(get("q4a_3")), parse_int(get("q4a_4")),
        parse_int(get("q4a_5")), parse_int(get("q4a_6")),
        parse_int(get("q4a_7")), parse_int(get("q4a_8")),
        parse_int(get("q4b_1")), parse_int(get("q4b_2")),
        parse_int(get("q4b_3")), parse_int(get("q4b_4")),
        parse_int(get("q4b_5")), parse_int(get("q4b_6")),
        parse_int(get("q4b_7")), parse_int(get("q4b_8")),
        get_json("q14_learning"), get("q15_template_type"),
        get_json("q16_concerns"), get("q17_payment"),
        get("q18_pain_point"), get("q19_feedback"), get("q20_suggestions"),
    ]

    assert len(cols) == len(vals), f"Column/value mismatch: {len(cols)} cols vs {len(vals)} vals"

    placeholders = ",".join(["?"] * len(cols))
    sql = f"INSERT INTO responses ({','.join(cols)}) VALUES ({placeholders})"
    conn.execute(sql, vals)
    conn.commit()
    conn.close()
    return RedirectResponse(url="/stats?thanks=1", status_code=303)


# ── Routes: Statistics ─────────────────────────────────────

@app.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request):
    stats = compute_stats()
    thanks = request.query_params.get("thanks", "0")
    return render("stats.html", request=request, stats=stats, thanks=thanks == "1")


@app.get("/api/stats")
async def api_stats():
    return compute_stats()


# ── Routes: Admin ──────────────────────────────────────────

ADMIN_COOKIE = "survey_admin_session"


def check_admin(request: Request) -> bool:
    session = request.cookies.get(ADMIN_COOKIE)
    return session == ADMIN_PASSWORD_HASH


@app.get("/admin", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    if check_admin(request):
        return RedirectResponse(url="/admin/dashboard")
    return render("admin_login.html", request=request)


@app.post("/admin/login")
async def admin_login(request: Request, password: str = Form(...)):
    h = hashlib.sha256(password.encode()).hexdigest()
    conn = get_db()
    stored = conn.execute("SELECT password_hash FROM admins WHERE id=1").fetchone()
    conn.close()
    if stored and h == stored[0]:
        resp = RedirectResponse(url="/admin/dashboard", status_code=303)
        resp.set_cookie(key=ADMIN_COOKIE, value=h, httponly=True, max_age=86400)
        return resp
    return render("admin_login.html", request=request, error="密码错误")


@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    if not check_admin(request):
        return RedirectResponse(url="/admin")
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM responses ORDER BY created_at DESC"
    ).fetchall()
    total = len(rows)
    conn.close()
    stats = compute_stats()
    return render("admin_dashboard.html", request=request, responses=rows, total=total, stats=stats)


@app.get("/admin/export")
async def admin_export(request: Request):
    if not check_admin(request):
        return RedirectResponse(url="/admin")
    conn = get_db()
    rows = conn.execute("SELECT * FROM responses ORDER BY created_at ASC").fetchall()
    conn.close()

    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows([dict(r) for r in rows])
    else:
        output.write("no data\n")

    output.seek(0)
    filename = f"survey_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/admin/logout")
async def admin_logout():
    resp = RedirectResponse(url="/admin")
    resp.delete_cookie(ADMIN_COOKIE)
    return resp


# ── Run ────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 12222))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
