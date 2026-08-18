import os
import socket
import subprocess
import sys
import tempfile
from datetime import date
from typing import Dict, List, Optional

import streamlit as st
from fpdf import FPDF
from PIL import Image


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, "SimHei.ttf")
LOGO_PATH = os.path.join(BASE_DIR, "logo.png")
SERVER_PORT = 8502

PEST_OPTIONS = ["未见异常", "鼠迹", "蟑迹", "飞虫", "其他"]
AREA_ROWS = ["门店及外围", "客区", "前场", "后场", "仓库"]
SERVICE_TYPES = ["常规", "勘查", "紧急"]
CHECK_ITEMS = [
    "清理垃圾、积水、食物残渣及卫生死角",
    "堵塞缝隙、窗纱、门帘、地漏加设防护",
    "请保持灭蝇灯长期开启并定期更换粘捕纸",
    "请高危食品、货架、料箱长期离地堆放",
]


class OnsiteReportPDF(FPDF):
    def __init__(self, logo_path: Optional[str] = None):
        super().__init__()
        self.logo_path = logo_path
        self.set_auto_page_break(auto=True, margin=12)
        self.set_margins(10, 10, 10)
        self.add_font("SimHei", "", FONT_PATH, uni=True)

    def header(self):
        # Y轴基准线：将三者统一对齐
        base_y = 10

        # 1. 绘制公司 Logo（左侧）
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                self.image(self.logo_path, x=10, y=base_y, w=24)
            except Exception:
                pass

        # 2. 绘制主标题（居中，和Logo在同一水平线）
        self.set_xy(10, base_y + 8)
        self.set_font("SimHei", "", 20)
        self.cell(0, 10, "有害生物防制作业报告", 0, 1, "C")

        # 3. 绘制公司名称和热线（右侧对齐）
        self.set_xy(140, base_y + 4)
        self.set_font("SimHei", "", 10)
        self.set_text_color(80, 80, 80)
        self.cell(60, 5, "苏州厨芯科技", 0, 1, "R")

        self.set_xy(140, base_y + 9)
        self.cell(60, 5, "服务热线：400-810-7733", 0, 1, "R")

        # 恢复默认黑色，并留出垂直空间，避免与下方表格重叠
        self.set_text_color(0, 0, 0)
        self.set_y(base_y + 24)

    def footer(self):
        self.set_y(-10)
        self.set_font("SimHei", "", 8)
        self.cell(0, 5, f"第 {self.page_no()} 页", 0, 0, "C")

    def section_title(self, text: str):
        self.set_fill_color(240, 240, 240)
        self.set_font("SimHei", "", 11)
        self.cell(0, 8, text, border=1, ln=1, align="L", fill=True)

    def kv_row(self, key: str, value: str, width: float):
        self.set_font("SimHei", "", 10)
        self.cell(width, 8, f"{key}：{value}", border=1, ln=0)

    def simple_table_header(self, columns: List[str], widths: List[float]):
        self.set_fill_color(245, 245, 245)
        self.set_font("SimHei", "", 10)
        for idx, col in enumerate(columns):
            self.cell(widths[idx], 8, col, border=1, ln=0, align="C", fill=True)
        self.ln()

    def simple_row(self, values: List[str], widths: List[float], row_height: int = 10):
        self.set_font("SimHei", "", 10)

        # 1. 首先计算这一行中，最高的单元格需要多少高度
        max_h = row_height
        for idx, val in enumerate(values):
            # 获取文本需要的行数（每行约5个单位高）
            lines = len(self.multi_cell(widths[idx], 5, val, split_only=True))
            cell_h = lines * 5 + 2 # 留出2的内边距
            if cell_h > max_h:
                max_h = cell_h

        # 2. 判断是否需要换页
        if self.get_y() + max_h > self.page_break_trigger:
            self.add_page()

        # 3. 记录当前起点的 Y 坐标
        start_y = self.get_y()
        start_x = self.get_x()

        # 4. 绘制每一列
        for idx, val in enumerate(values):
            # 绘制外边框 (高为 max_h)
            self.rect(start_x, start_y, widths[idx], max_h)

            # 使用 multi_cell 绘制内容，确保长文本自动换行
            self.set_xy(start_x, start_y + 1)  # 稍微下移一点，作为内边距
            self.multi_cell(widths[idx], 5, val, align="L")

            # 移动 X 到下一列的起点
            start_x += widths[idx]

        # 5. 将 Y 指针移动到这一行结束的位置
        self.set_y(start_y + max_h)


def area_result_text(area_item: Dict) -> str:
    values = area_item["pests"][:]
    if "其他" in values and area_item.get("other"):
        values = [x for x in values if x != "其他"]
        values.append(f"其他({area_item['other']})")
    return "、".join(values) if values else "未填写"


def generate_pdf(data: Dict, image_files) -> bytes:
    pdf = OnsiteReportPDF(logo_path=LOGO_PATH if os.path.exists(LOGO_PATH) else None)
    pdf.add_page()

    pdf.kv_row("客户名称", data["client_name"], 95)
    pdf.kv_row("门店名称", data["store_name"], 95)
    pdf.ln()

    pdf.kv_row("服务地址", data["address"], 130)
    pdf.kv_row("服务日期", data["service_date"], 60)
    pdf.ln()

    pdf.kv_row("服务时间", f"{data['start_time']} - {data['end_time']}", 65)
    pdf.kv_row("服务类型", data["service_type"], 45)
    pdf.kv_row("服务人员", data["staff_name"], 80)
    pdf.ln(10)

    pdf.section_title("一、现场检查与作业记录")
    widths_1 = [28, 35, 63, 64]
    pdf.simple_table_header(["检查区域", "虫害情况", "风险情况", "整改建议"], widths_1)
    for item in data["area_records"]:
        row = [
            item["area"],
            area_result_text(item),
            (item["risk"] or "无"),
            (item["advice"] or "无"),
        ]
        pdf.simple_row(row, widths_1, row_height=10)

    pdf.ln(3)
    pdf.section_title("二、制剂/药剂使用记录")
    widths_2 = [120, 35, 35]
    pdf.simple_table_header(["物料/药剂名称", "数量", "单位"], widths_2)
    rows = data["materials"] if data["materials"] else [{"name": "无", "qty": "-", "unit": "-"}]
    for row in rows:
        pdf.simple_row([row["name"], row["qty"], row["unit"]], widths_2, row_height=9)

    pdf.ln(3)
    pdf.section_title("三、现场图片")
    if image_files:
        col = 0
        y_start = pdf.get_y() + 2

        # 定义单张图片的尺寸 (竖版 9:16)
        # 一行放3张比较合适，A4纸可用宽度约190mm，间距留足
        box_w = 58
        box_h = box_w * (16 / 9)  # 约 103

        for idx, file in enumerate(image_files):
            file.seek(0)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                try:
                    # 使用 PIL 打开并统一转为 RGB JPEG，防止 fpdf 不兼容某些 PNG/WEBP
                    img = Image.open(file)
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    orig_w, orig_h = img.size
                    img.save(tmp.name, format="JPEG", quality=90)
                    tmp_path = tmp.name

                    # 动态计算 X 坐标，改为一行3列排布，间距均分
                    x = 12 + col * (box_w + 8)

                    # 1. 绘制带有浅色背景和明显边框的底框
                    pdf.set_fill_color(248, 249, 250) # 浅灰背景
                    pdf.set_draw_color(180, 180, 180) # 明显的灰色边框
                    pdf.set_line_width(0.4)           # 加粗边框
                    pdf.rect(x, y_start, box_w, box_h, 'FD')

                    # 2. 计算等比例缩放后的尺寸 (预留 2mm 内边距)
                    max_w, max_h = box_w - 4, box_h - 4
                    ratio = min(max_w / orig_w, max_h / orig_h)
                    img_w = orig_w * ratio
                    img_h = orig_h * ratio

                    # 3. 居中绘制图片，保持原图比例
                    img_x = x + (box_w - img_w) / 2
                    img_y = y_start + (box_h - img_h) / 2
                    pdf.image(tmp_path, x=img_x, y=img_y, w=img_w, h=img_h)

                    # 恢复默认线宽和颜色
                    pdf.set_draw_color(0, 0, 0)
                    pdf.set_line_width(0.2)
                except Exception as e:
                    pdf.set_xy(12 + col * (box_w + 8), y_start)
                    pdf.cell(box_w, 10, f"加载失败", border=1, ln=0, align="C")
                finally:
                    if 'tmp_path' in locals() and os.path.exists(tmp_path):
                        os.unlink(tmp_path)

            col += 1
            has_more = idx < len(image_files) - 1
            if col == 3 and has_more:  # 满3张换行，且后面还有图片时才续行/续页
                col = 0
                y_start += box_h + 4  # 换行间距
                if y_start + box_h > pdf.page_break_trigger:
                    pdf.add_page()
                    pdf.section_title("三、现场图片（续）")
                    y_start = pdf.get_y() + 2
        pdf.set_y(y_start + box_h + 4)
    else:
        pdf.cell(0, 8, "无现场图片", border=1, ln=1)

    pdf.ln(3)
    return pdf.output(dest="S").encode("latin-1")


def collect_form_data() -> Dict:
    st.subheader("基础信息")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        client_name = st.text_input("客户名称", value="")
    with c2:
        store_name = st.text_input("门店名称", value="")
    with c3:
        address = st.text_input("服务地址", value="")
    with c4:
        service_date = st.date_input("服务日期", value=date.today())

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        start_time = st.text_input("服务开始时间", value="09:00")
    with c6:
        end_time = st.text_input("服务结束时间", value="10:00")
    with c7:
        service_type = st.radio("服务类型", SERVICE_TYPES, horizontal=True)
    with c8:
        staff_name = st.text_input("服务人员", value="")

    st.subheader("一、现场检查与作业记录")
    area_records: List[Dict] = []
    for area in AREA_ROWS:
        with st.expander(f"{area}", expanded=True):
            cc1, cc2, cc3 = st.columns(3)
            with cc1:
                pests = st.multiselect(
                    "虫害情况",
                    PEST_OPTIONS,
                    default=["未见异常"],
                    key=f"pest_{area}",
                )
                other = ""
                if "其他" in pests:
                    other = st.text_input("其他虫害描述", value="", key=f"other_{area}")
            with cc2:
                risk = st.text_area("风险情况", value="", key=f"risk_{area}", height=80)
            with cc3:
                advice = st.text_area("整改建议", value="", key=f"advice_{area}", height=80)
            area_records.append(
                {
                    "area": area,
                    "pests": pests,
                    "other": other,
                    "risk": risk,
                    "advice": advice,
                }
            )

    st.subheader("二、制剂/药剂使用记录")
    material_rows = st.data_editor(
        [
            {"name": "", "qty": "", "unit": ""},
            {"name": "", "qty": "", "unit": ""},
            {"name": "", "qty": "", "unit": ""},
            {"name": "", "qty": "", "unit": ""},
        ],
        column_config={
            "name": "物料/药剂名称",
            "qty": "数量",
            "unit": "单位",
        },
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
    )
    materials = [
        {"name": x["name"], "qty": x["qty"], "unit": x["unit"]}
        for x in material_rows
        if x["name"] or x["qty"] or x["unit"]
    ]

    st.subheader("三、现场图片")
    image_files = st.file_uploader(
        "上传现场图片",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
    )

    return {
        "client_name": client_name.strip(),
        "store_name": store_name.strip(),
        "address": address.strip(),
        "service_date": service_date.strftime("%Y-%m-%d"),
        "start_time": start_time.strip(),
        "end_time": end_time.strip(),
        "service_type": service_type,
        "staff_name": staff_name.strip(),
        "area_records": area_records,
        "materials": materials,
        "image_names": [x.name for x in image_files] if image_files else [],
        "image_files": image_files or [],
    }


def main():
    st.set_page_config(page_title="PCO 现场作业报告生成工具", layout="wide")
    st.title("PCO 现场作业报告快速生成工具")
    st.caption("按现场表单填写后，一键导出 PDF 报告。")

    if not os.path.exists(FONT_PATH):
        st.error("缺少中文字体文件 SimHei.ttf，无法生成中文 PDF。")
        st.stop()

    form_data = collect_form_data()

    if st.button("生成报告", type="primary"):
        if not form_data["client_name"] or not form_data["store_name"]:
            st.error("请至少填写客户名称和门店名称。")
            st.stop()
        try:
            pdf_bytes = generate_pdf(form_data, form_data["image_files"])
            date_part = form_data["service_date"].replace("-", "")
            file_stub = f"PCO作业报告_{form_data['store_name']}_{date_part}"

            st.success("报告生成完成。")
            st.download_button(
                "下载 PDF",
                data=pdf_bytes,
                file_name=f"{file_stub}.pdf",
                mime="application/pdf",
            )
        except Exception as exc:
            st.error(f"生成失败：{exc}")


def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def print_access_urls():
    local_ip = get_local_ip()
    print("=" * 51)
    print("服务已启动，局域网内其他设备可通过以下地址访问：")
    print(f"本机访问：   http://127.0.0.1:{SERVER_PORT}")
    print(f"局域网访问： http://{local_ip}:{SERVER_PORT}")
    print("=" * 51)


def launch_lan_server():
    print_access_urls()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            __file__,
            f"--server.address=0.0.0.0",
            f"--server.port={SERVER_PORT}",
            "--browser.gatherUsageStats=false",
        ],
        check=True,
    )


def is_streamlit_runtime() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except Exception:
        return False


if __name__ == "__main__":
    if is_streamlit_runtime():
        main()
    else:
        launch_lan_server()
