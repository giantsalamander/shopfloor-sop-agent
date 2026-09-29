"""造 mock 数据：仪器面板图 / 工人回传CSV / 仪器资产库 / 危化SDS。
运行：python mock_gen.py  → 填 mock/
不需要 Step3-VL/Nemotron，纯本地。"""
from __future__ import annotations
import os, json, csv, random
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
MOCK = os.path.join(ROOT, "mock")
PANEL = os.path.join(MOCK, "panels")
os.makedirs(PANEL, exist_ok=True)

def instruments_csv():
    rows = [
        {"instrument_sn":"FLK-87V-001","model":"Fluke 87V","type":"multimeter","range_max":1000,"range_unit":"V","cal_expiry":(date.today()+timedelta(days=120)).isoformat()},
        {"instrument_sn":"CDZ-1001","model":"CD-1001TZ","type":"torque_wrench","range_max":100,"range_unit":"Nm","cal_expiry":(date.today()+timedelta(days=60)).isoformat()},
        {"instrument_sn":"TSC-DSO-22","model":"Tek DSO","type":"oscilloscope","range_max":200,"range_unit":"MHz","cal_expiry":(date.today()-timedelta(days=30)).isoformat()},  # 过期
        {"instrument_sn":"PT-100-T2","model":"PT100","type":"thermometer","range_max":400,"range_unit":"C","cal_expiry":(date.today()+timedelta(days=200)).isoformat()},
    ]
    with open(os.path.join(MOCK,"instruments_mock.csv"),"w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    print(f"instruments_mock.csv  {len(rows)} rows")

def sds_json():
    d = {
        "P_00001":{"product_id":"P_00001","name":"乙醇溶液","hazard_class":"3","flash_point_c":13.0},
        "P_00002":{"product_id":"P_00002","name":"氢氧化钠","hazard_class":"8","flash_point_c":None},
        "P_00003":{"product_id":"P_00003","name":"硝酸钠","hazard_class":"5.1","flash_point_c":None},
        "P_00004":{"product_id":"P_00004","name":"锂电池组","hazard_class":"9","flash_point_c":None},
    }
    json.dump(d, open(os.path.join(MOCK,"sds_mock.json"),"w"), ensure_ascii=False, indent=2)
    print(f"sds_mock.json  {len(d)} products")

def _panel_multimeter(ax, measured, unit, label, ok=True):
    ax.set_xlim(0,10); ax.set_ylim(0,6); ax.set_facecolor("#102030")
    ax.text(5,5.2,"DIGITAL MULTIMETER",ha="center",color="#00ff88",fontsize=12,weight="bold")
    ax.add_patch(plt.Rectangle((1.5,1.5),7,2.6,fill=False,edgecolor="#00ff88",lw=2))
    ax.text(5,2.8,f"{measured} {unit}",ha="center",color="#00ffaa",fontsize=22,weight="bold")
    ax.text(5,0.6,label,ha="center",color="white",fontsize=9)
    if not ok:
        ax.text(8.5,5.2,"⚠",ha="center",color="red",fontsize=14)

def _panel_torque(ax, measured, unit, label):
    ax.set_xlim(0,10); ax.set_ylim(0,6); ax.set_facecolor("#202020")
    ax.text(5,5.2,"TORQUE WRENCH",ha="center",color="white",fontsize=12,weight="bold")
    ax.text(5,2.8,f"{measured} {unit}",ha="center",color="#ffcc00",fontsize=22,weight="bold")
    ax.text(5,0.6,label,ha="center",color="white",fontsize=9)

def panels():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    global plt
    specs = [
        ("panel_ok.png","multimeter",12.4,"V","Step S1: 绝缘电压",True),
        ("panel_overrange.png","multimeter",1250,"V","Step S1: 超量程",False),
        ("panel_wrongunit.png","multimeter",12400,"mV","Step S1: 单位错",True),
        ("panel_torque_ok.png","torque",45.0,"Nm","Step S2: 扭矩",True),
    ]
    for fn,kind,val,unit,label,ok in specs:
        fig,ax=plt.subplots(figsize=(6,3.2),dpi=110)
        if kind=="multimeter": _panel_multimeter(ax,val,unit,label,ok)
        else: _panel_torque(ax,val,unit,label)
        fig.savefig(os.path.join(PANEL,fn)); plt.close(fig)
    print(f"panels  {len(specs)} png -> {PANEL}")
    return specs

def worker_csv(specs):
    rows=[
        {"step_id":"S1","param_name":"insulation_voltage","setpoint":12,"measured":12.4,"unit":"V","instrument_sn":"FLK-87V-001","instrument_model":"Fluke 87V","timestamp":"2026-09-29T09:10:00","photo_path":"panels/panel_ok.png"},
        {"step_id":"S1","param_name":"insulation_voltage","setpoint":12,"measured":1250,"unit":"V","instrument_sn":"TSC-DSO-22","instrument_model":"Tek DSO","timestamp":"2026-09-29T09:12:00","photo_path":"panels/panel_overrange.png"},
        {"step_id":"S1","param_name":"insulation_voltage","setpoint":12,"measured":12400,"unit":"mV","instrument_sn":"FLK-87V-001","instrument_model":"Fluke 87V","timestamp":"2026-09-29T09:13:00","photo_path":"panels/panel_wrongunit.png"},
        {"step_id":"S2","param_name":"torque","setpoint":45,"measured":45.0,"unit":"Nm","instrument_sn":"CDZ-1001","instrument_model":"CD-1001TZ","timestamp":"2026-09-29T09:20:00","photo_path":"panels/panel_torque_ok.png"},
    ]
    with open(os.path.join(MOCK,"worker_batch.csv"),"w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    print(f"worker_batch.csv  {len(rows)} rows (含 合格/超量程/单位错/扭矩合格)")

def sop_txt():
    txt = """设备点检与校准 SOP v3
1. 绝缘电阻测试：使用万用表，量程 ≥ 1000V，测试电压 12V ±5%，记录实测值。
2. 扭矩校验：使用扭矩枪，设定 45 Nm，公差 ±5%，记录实测扭矩。
3. 安全：操作前佩戴绝缘手套；仪器必须在校准有效期内。
4. 仪器校准过期或量程不符，禁止使用并退回 Step3 重选仪器。
5. 危化品收货参照 SDS：闪点 < 23°C 的 III 类以上液体不得空运客机。"""
    open(os.path.join(MOCK,"sop_sample.txt"),"w").write(txt)
    print("sop_sample.txt  written")

if __name__ == "__main__":
    instruments_csv(); sds_json(); specs=panels(); worker_csv(specs); sop_txt()
    print("DONE →", MOCK)
