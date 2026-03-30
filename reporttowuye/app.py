import streamlit as st
from fpdf import FPDF
import tempfile
import os
import re
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import matplotlib.pyplot as plt
import matplotlib
from matplotlib.font_manager import FontProperties
from matplotlib.ticker import MaxNLocator

# 设置 matplotlib 后端
matplotlib.use('Agg')
# 尝试设置系统字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'sans-serif'] 
plt.rcParams['axes.unicode_minus'] = False

# ==========================================
# 1. 核心 PDF 生成类 (基于 FPDF)
# ==========================================
class PDF(FPDF):
    def __init__(self, logo_path=None, stamp_path=None):
        super().__init__()
        self.set_margins(20, 20, 20)
        self.set_auto_page_break(auto=True, margin=20)
        self.logo_path = logo_path
        self.stamp_path = stamp_path
        self.brand_color = (66, 133, 244) 
        self.bg_gray = (248, 249, 250)
        self.highlight_bg = (232, 240, 254)
        
        # 字体加载逻辑
        try:
            if os.path.exists("SimHei.ttf"):
                self.add_font('SimHei', '', 'SimHei.ttf', uni=True)
            else:
                st.warning("⚠️ 警告: 未找到 SimHei.ttf 字体文件，中文可能无法显示。")
        except Exception as e:
            st.error(f"字体加载失败: {e}")

    def header(self):
        if self.page_no() == 1:
            self.set_fill_color(255, 255, 255)
            self.rect(0, 0, 210, 35, 'F')
            
            logo_width = 0
            if self.logo_path and os.path.exists(self.logo_path):
                try:
                    self.image(self.logo_path, x=15, y=6, w=22) 
                    logo_width = 22
                except:
                    pass
            
            # 使用已在 __init__ 中注册的字体
            try:
                self.set_font('SimHei', '', 20)
            except:
                self.set_font('Arial', 'B', 20)
            
            self.set_text_color(*self.brand_color)
            text_start_x = 15 + logo_width + 5 if logo_width > 0 else 15
            self.set_xy(text_start_x, 8)
            self.cell(0, 18, '智能有害生物防制报告', 0, 1, 'L')
            
            self.set_draw_color(*self.brand_color)
            self.set_line_width(1.0)
            self.line(15, 32, 195, 32)
            self.ln(3) 
        else:
            self.ln(2)

    def footer(self):
        self.set_y(-15)
        try:
            self.set_font('SimHei', '', 8)
        except:
            self.set_font('Arial', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'- {self.page_no()} -', 0, 0, 'C')

    def add_closing_banner(self):
        self.set_auto_page_break(False)
        
        # 电子印章
        if self.stamp_path and os.path.exists(self.stamp_path):
            try:
                self.image(self.stamp_path, x=20, y=245, w=35)
            except Exception as e:
                print(f"印章加载失败: {e}")

        y_pos = 282
        self.set_y(y_pos)
        self.set_fill_color(*self.brand_color)
        self.rect(0, y_pos, 210, 15, 'F') 
        
        try:
            self.set_font('SimHei', '', 10)
        except:
            self.set_font('Arial', 'B', 10)
            
        self.set_text_color(255, 255, 255)
        text_y = y_pos + 4
        self.set_xy(15, text_y)
        self.cell(80, 8, '科技改变 PCO', 0, 0, 'L')
        self.set_xy(100, text_y)
        self.cell(95, 8, '服务热线: 400-810-7733', 0, 0, 'R')
        self.set_auto_page_break(True, margin=20)

    # 章节标题样式：左侧强调条 + 浅灰背景
    def draw_section_header(self, title):
        self.ln(6) 
        
        # 1. 绘制背景条 (极浅灰)
        self.set_fill_color(245, 247, 250) 
        self.rect(15, self.get_y(), 180, 10, 'F')
        
        # 2. 绘制左侧强调条 (品牌蓝)
        self.set_fill_color(*self.brand_color)
        self.rect(15, self.get_y(), 4, 10, 'F')
        
        # 3. 绘制文字 (深灰)
        self.set_font('SimHei', '', 13)
        self.set_text_color(50, 50, 50) 
        
        self.set_x(22) 
        self.cell(170, 10, title, 0, 1, 'L')
        
        self.ln(2) 

    def draw_info_box(self, info_dict):
        rows = (len(info_dict) + 1) // 2
        line_height = 8
        box_height = rows * line_height + 6
        self.set_fill_color(*self.bg_gray)
        self.rect(15, self.get_y(), 180, box_height, 'F')
        self.set_y(self.get_y() + 3)
        self.set_font('SimHei', '', 10)
        items = list(info_dict.items())
        for i in range(0, len(items), 2):
            key1, val1 = items[i]
            self.set_x(20)
            self._print_kv_compact(key1, val1)
            if i + 1 < len(items):
                key2, val2 = items[i+1]
                self.set_x(110) 
                self._print_kv_compact(key2, val2)
            self.ln(line_height)
        self.ln(2)

    def _print_kv_compact(self, key, val):
        self.set_text_color(128, 128, 128)
        self.cell(20, 8, f"{key}:", 0, 0)
        self.set_text_color(0, 0, 0)
        self.cell(60, 8, str(val), 0, 0)

    def draw_sub_section_title(self, title):
        self.ln(2)
        # 背景改为极浅灰
        self.set_fill_color(250, 250, 250) 
        self.rect(15, self.get_y(), 180, 10, 'F')
        
        self.set_font('SimHei', '', 12)
        self.set_text_color(30, 30, 30) 
        self.set_x(20)
        self.cell(0, 10, title, 0, 1)

    def process_image_with_watermark(self, img_file, watermark_text):
        try:
            image = Image.open(img_file)
            if image.mode in ("RGBA", "P"): image = image.convert("RGB")
            
            draw = ImageDraw.Draw(image)
            w, h = image.size
            
            # 动态计算字体大小 (5%)
            font_size = int(w * 0.05) 
            if font_size < 20: font_size = 20 
            
            try:
                font = ImageFont.truetype("SimHei.ttf", font_size)
            except:
                font = ImageFont.load_default()

            bbox = draw.textbbox((0, 0), watermark_text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            x = w - text_w - (w * 0.02)
            y = h - text_h - (h * 0.02)
            
            stroke_width = max(1, int(font_size / 15))
            draw.text((x, y), watermark_text, font=font, fill="white", stroke_width=stroke_width, stroke_fill="black")
            
            return image
        except Exception as e:
            return None

    def add_image_grid(self, image_items):
        if not image_items: return
        x_start, img_w, img_h, txt_h = 15, 55, 41.25, 6
        margin_x, margin_y = 5, 6
        cell_total_h = img_h + txt_h
        col = 0
        y_start = self.get_y() + 1
        
        for item in image_items:
            img_file = item['file']
            caption = item['caption']
            watermark_text = item['watermark_text']

            if y_start + cell_total_h > 275:
                self.add_page()
                y_start = self.get_y() + 2
                col = 0

            tmp_path = None
            try:
                processed_img = self.process_image_with_watermark(img_file, watermark_text)
                
                if processed_img:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                        processed_img.save(tmp, format="JPEG", quality=90)
                        tmp_path = tmp.name
                    
                    x = x_start + (col * (img_w + margin_x))
                    self.image(tmp_path, x=x, y=y_start, w=img_w, h=img_h)
                    self.set_draw_color(230, 230, 230)
                    self.rect(x, y_start, img_w, img_h)
                    self.set_xy(x, y_start + img_h + 1) 
                    self.set_font('SimHei', '', 9) 
                    self.set_text_color(80, 80, 80)
                    self.cell(img_w, txt_h, caption, 0, 0, 'C')
            except Exception as e: pass
            finally:
                if tmp_path and os.path.exists(tmp_path): os.unlink(tmp_path)
            
            col += 1
            if col >= 3:
                col = 0
                y_start += (cell_total_h + margin_y)
        if col != 0: self.set_y(y_start + cell_total_h + margin_y)
        else: self.set_y(y_start)

    def draw_inspection_table(self, areas):
        # 表头样式: 浅灰背景，黑色文字
        self.set_font('SimHei', '', 10) 
        self.set_draw_color(220, 220, 220)
        self.set_fill_color(235, 235, 235) 
        self.set_text_color(0, 0, 0) 
        self.set_line_width(0.1)
        headers = ["监测点位", "图传状态", "AI 智能识别", "人工复核结论"]
        col_widths = [55, 30, 45, 50] 
        self.set_x(15) 
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 9, h, 1, 0, 'C', True)
        self.ln()
        
        self.set_font('SimHei', '', 9)
        self.set_text_color(0, 0, 0)
        for idx, area in enumerate(areas):
            self.set_x(15) 
            if idx % 2 == 0: self.set_fill_color(255, 255, 255) 
            else: self.set_fill_color(248, 249, 250) 
            self.cell(col_widths[0], 9, area['name'], 1, 0, 'C', True)
            self.set_text_color(0, 0, 0)
            self.cell(col_widths[1], 9, area['upload_status'], 1, 0, 'C', True) 
            ai_result = area['ai_status']
            if "风险" in ai_result or "异常" in ai_result: self.set_text_color(200, 0, 0) 
            else: self.set_text_color(0, 128, 0)
            self.cell(col_widths[2], 9, ai_result, 1, 0, 'C', True)
            self.set_text_color(0, 0, 0)
            self.cell(col_widths[3], 9, area['manual_check'], 1, 1, 'C', True)
        self.ln(5)

    def draw_suggestion_box(self, text):
        if self.get_y() + 30 > 270: self.add_page()
        self.set_fill_color(250, 250, 250) 
        self.rect(15, self.get_y(), 180, 25, 'F') 
        current_y = self.get_y()
        self.set_xy(20, current_y + 3) 
        self.set_font('SimHei', '', 10)
        self.set_text_color(80, 80, 80) 
        self.cell(0, 6, "专家整改建议", 0, 1)
        self.set_xy(20, current_y + 10)
        self.set_font('SimHei', '', 10)
        self.set_text_color(60, 60, 60)
        self.multi_cell(170, 5, text)
        self.set_y(current_y + 25 + 5) 

    def add_chart(self, chart_path):
        if chart_path and os.path.exists(chart_path):
            self.image(chart_path, x=15, w=180, h=70) 
            self.ln(5)

    def draw_materials_list(self):
        self.draw_section_header("现场使用物料")
        self.set_font('SimHei', '', 10)
        self.set_text_color(100, 100, 100) 
        self.cell(0, 8, "说明：本次采用厨芯智能终端监测未使用物料。", 0, 1, 'L')
        self.ln(2)
        materials = ["杀蟑胶饵", "高效氯氰菊酯", "吡虫啉", "粘鼠板", "蟑螂屋", "果蝇杯"]
        if self.get_y() + 25 > 270: self.add_page()
        self.set_font('SimHei', '', 10)
        self.set_text_color(0, 0, 0)
        start_x, col_width, line_height = 20, 45, 10
        for i, item in enumerate(materials):
            row, col = i // 4, i % 4
            curr_x = start_x + (col * col_width)
            if col == 0 and i > 0: self.ln(line_height)
            self.set_x(curr_x)
            checkbox_y = self.get_y() + 3
            self.set_draw_color(150, 150, 150) 
            self.rect(curr_x, checkbox_y, 4, 4) 
            self.set_xy(curr_x + 6, self.get_y())
            self.cell(col_width - 6, line_height, item, 0, 0, 'L')
        self.ln(line_height * 1.5) 

# ==========================================
# 2. 辅助函数：生成图表
# ==========================================
def generate_trend_chart(data_rat, data_roach, data_fly):
    plt.style.use('bmh') 
    fig, ax = plt.subplots(figsize=(10, 5), dpi=120)
    fig.patch.set_facecolor('#FFFFFF') 
    ax.set_facecolor('#FAFAFA')
    
    font_path = "SimHei.ttf"
    if os.path.exists(font_path):
        font_prop = FontProperties(fname=font_path)
    else:
        font_prop = None
    
    x = ["4天前", "3天前", "前天", "昨天", "今天"]
    
    def plot_line(data, color, label, marker):
        line, = ax.plot(x, data, marker=marker, linestyle='-', color=color, linewidth=2.5, label=label, markersize=8)
        ax.fill_between(x, data, color=color, alpha=0.1)
        for i, v in enumerate(data):
            ax.annotate(str(v), xy=(i, v), xytext=(0, 8), textcoords='offset points', ha='center', va='bottom', fontsize=9, color=color, fontweight='bold')
    
    plot_line(data_rat, '#FF5722', '鼠类', 'o')
    plot_line(data_roach, '#795548', '蟑螂', 's')
    plot_line(data_fly, '#4CAF50', '飞虫', '^')
    
    if font_prop:
        ax.set_title("各类虫害活动密度趋势 (AI智能分析)", fontsize=14, pad=15, color='#333333', fontweight='bold', fontproperties=font_prop)
        ax.legend(loc='upper right', frameon=True, facecolor='white', framealpha=0.9, prop=font_prop)
    else:
        ax.set_title("各类虫害活动密度趋势 (AI智能分析)", fontsize=14, pad=15, color='#333333', fontweight='bold')
        ax.legend(loc='upper right', frameon=True, facecolor='white', framealpha=0.9)

    ax.grid(True, linestyle='--', alpha=0.6, color='#CCCCCC')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_linewidth(0.5)
    
    # Y轴整数强制处理
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    
    max_val = max(max(data_rat), max(data_roach), max(data_fly))
    if max_val == 0:
        ax.set_ylim(0, 5) 
    else:
        ax.set_ylim(bottom=0) 
        ax.set_ylim(top=max_val * 1.15) 

    plt.tight_layout()
    tmp_chart = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    plt.savefig(tmp_chart, bbox_inches='tight')
    plt.close()
    return tmp_chart

# ==========================================
# 3. 辅助函数：图片数据预处理
# ==========================================
def prepare_image_data(files, base_date, interval_mins, mode, base_time_obj=None):
    result = []
    
    if base_time_obj:
        current_time = base_time_obj
    else:
        current_time = datetime.now()

    if not files: 
        return result, current_time

    for f in files:
        name_root = os.path.splitext(f.name)[0]
        caption = name_root
        
        match = re.search(r'_(\d{4})$', name_root)
        watermark_str = ""
        
        if match:
            time_part = match.group(1) 
            hh = time_part[:2]
            mm = time_part[2:]
            watermark_str = f"{base_date} {hh}:{mm}"
            caption = name_root[:match.start()]
        else:
            if mode == "fixed":
                watermark_str = base_time_obj.strftime('%Y-%m-%d %H:%M')
            else:
                watermark_str = current_time.strftime('%Y-%m-%d %H:%M')
                current_time += timedelta(minutes=interval_mins)
        
        result.append({
            'file': f,
            'caption': caption,
            'watermark_text': watermark_str
        })
        
    return result, current_time

# ==========================================
# 4. Streamlit 前端界面
# ==========================================
st.set_page_config(page_title="PCO 服务报告生成工具", layout="wide", page_icon="🛡️")

st.markdown("""
<style>
    .main .block-container { padding-top: 2rem; }
    h1 { color: #4285F4; }
    div.stButton > button { 
        background-color: #4285F4; color: white; border-radius: 6px; 
        font-weight: bold; border: none; padding: 0.5rem 1rem;
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ PCO 远程监测报告生成器 V5.0 (Smart)")

with st.sidebar:
    st.header("⚙️ 全局配置")
    
    # 调整 1：将报告日期放在侧边栏，作为全局时间基准
    service_date = st.date_input("📅 报告日期 (全局)", value=datetime.now())
    base_date_str = service_date.strftime('%Y-%m-%d')
    
    st.divider()
    
    default_logo_path = "logo.png"
    uploaded_logo = None
    if os.path.exists(default_logo_path): st.success(f"✅ 已加载默认Logo")
    else: uploaded_logo = st.file_uploader("上传Logo", type=['png', 'jpg'], key="logo")
    
    st.subheader("🔴 电子印章")
    default_stamp_path = "stamp.png"
    uploaded_stamp = None
    if os.path.exists(default_stamp_path): st.success(f"✅ 已加载默认印章")
    else: uploaded_stamp = st.file_uploader("上传印章 (透明PNG)", type=['png'], key="stamp")
        
    st.divider()
    
    st.subheader("💧 水印配置")
    watermark_mode = st.radio("生成模式", ["智能序列 (推荐)", "固定时间"], index=0)
    
    seq_start_time = None
    fixed_time_obj = None
    
    # 调整 2：默认时间改为 06:00，间隔 6 分钟
    if watermark_mode == "智能序列 (推荐)":
        start_time_str = st.text_input("起始时间 (HH:MM)", value="06:00")
        interval = st.number_input("自动递增间隔 (分钟)", value=6, min_value=1)
        try:
            # 组合全局日期 + 自定义时间
            seq_start_time = datetime.strptime(f"{base_date_str} {start_time_str}", "%Y-%m-%d %H:%M")
        except:
            st.error("时间格式错误，请使用 HH:MM")
            seq_start_time = datetime.now()
    else:
        fixed_time_str = st.text_input("统一时间 (HH:MM)", value=datetime.now().strftime('%H:%M'))
        try:
            fixed_time_obj = datetime.strptime(f"{base_date_str} {fixed_time_str}", "%Y-%m-%d %H:%M")
        except:
            fixed_time_obj = datetime.now()

    st.info("💡 文件名时间优先：如 `点位_1430.jpg` 将强制使用文件名中的 14:30，日期跟随全局日期。")
    st.divider()
    if not os.path.exists("SimHei.ttf"): st.error("❌ 缺失 SimHei.ttf")

# 调整 3：移除了 st.form，实现了实时交互
st.markdown("### 1. 监测基础信息")
with st.container():
    c1, c2, c3 = st.columns(3)
    with c1: client_name = st.text_input("客户名称", value="一图牛排小火锅")
    with c2: store_name = st.text_input("门店名称", value="北京朝阳大悦城店")
    with c3: service_type = st.selectbox("服务类型", ["智能监测服务", "专项远程诊断"])
    
    c4, c5 = st.columns(2)
    with c4: staff_name = st.text_input("监测专员", value="远程中心-张三")
    with c5: address = st.text_input("门店地址", value="朝阳大悦城 4F")

st.markdown("### 2. 虫害监测数据 (IoT)")
with st.container():
    tc1, tc2, tc3 = st.columns(3)
    with tc1: trend_rat_str = st.text_input("🐭 鼠类数据", value="0, 0, 0, 0, 0")
    with tc2: trend_roach_str = st.text_input("🪳 蟑螂数据", value="2, 1, 0, 0, 0")
    with tc3: trend_fly_str = st.text_input("🦟 飞虫数据", value="5, 3, 2, 1, 0")

st.markdown("### 3. 终端回传影像 & 风险标记")
st.info("👇 上传图片后，下方将**立即**显示风险勾选框，无需等待生成。")

col_img1, col_img2, col_img3 = st.columns(3)
with col_img1: imgs_mouse = st.file_uploader("🐭 粘鼠板监测图", type=['png', 'jpg'], accept_multiple_files=True, key="m")
with col_img2: imgs_roach = st.file_uploader("🪳 蟑螂屋监测图", type=['png', 'jpg'], accept_multiple_files=True, key="r")
with col_img3: imgs_fly = st.file_uploader("🦟 灭蝇灯监测图", type=['png', 'jpg'], accept_multiple_files=True, key="f")

# --- 实时处理图片逻辑 (移出表单) ---
mode_key = "sequence" if watermark_mode == "智能序列 (推荐)" else "fixed"
start_obj = seq_start_time if mode_key == "sequence" else fixed_time_obj
interv = interval if mode_key == "sequence" else 0

processed_mouse, next_time = prepare_image_data(imgs_mouse, base_date_str, interv, mode_key, start_obj)
processed_roach, next_time = prepare_image_data(imgs_roach, base_date_str, interv, mode_key, next_time)
processed_fly, _ = prepare_image_data(imgs_fly, base_date_str, interv, mode_key, next_time)

all_processed_items = processed_mouse + processed_roach + processed_fly

# --- 实时显示风险勾选 ---
areas_status = []
if all_processed_items:
    st.markdown("#### 📝 请勾选存在风险的点位：")
    risk_cols = st.columns(3)
    for i, item in enumerate(all_processed_items):
        point_name = item['caption']
        watermark = item['watermark_text'].split(' ')[1] 
        
        with risk_cols[i % 3]:
            # 使用 container 增加一点视觉隔离
            with st.container():
                st.write(f"🖼️ **{point_name}** ({watermark})")
                has_risk = st.checkbox(f"标记风险", key=f"risk_{item['file'].name}_{i}")
                
                status_data = {
                    "name": point_name,
                    "upload_status": "正常",
                    "ai_status": "发现风险" if has_risk else "画面正常",
                    "manual_check": "需门店配合检查" if has_risk else "复核确认/持续监测"
                }
                areas_status.append(status_data)
else:
    st.caption("（暂无上传图片）")

st.markdown("### 4. 监测结论与建议")
suggestion_text = st.text_area("结构与卫生整改建议", value="1. 02号设备回传画面显示洗碗间地面有积水，建议及时清理。\n2. 03号设备夜间监测到仓库门未关严，建议加强闭店管理。", height=80)
col_s1, col_s2, col_s3 = st.columns(3)
with col_s1: summary_rat = st.text_area("鼠类情况", value="监测正常，未发现活动轨迹", height=68)
with col_s2: summary_roach = st.text_area("蟑螂情况", value="监测正常，未发现活动轨迹", height=68)
with col_s3: summary_fly = st.text_area("飞虫情况", value="监测正常，未发现活动轨迹", height=68)

st.markdown("---")
# 提交按钮现在在表单之外
submitted = st.button("🚀 生成并预览报告", type="primary")

# --- 生成逻辑 ---
if submitted:
    if not os.path.exists("SimHei.ttf"):
        st.error("无法生成：请检查字体文件 SimHei.ttf")
    else:
        with st.spinner("正在智能排版中..."):
            try:
                # Logo & Stamp Logic
                logo_path_to_use = None
                logo_tmp_path = None
                
                if os.path.exists("logo.png"): logo_path_to_use = "logo.png"
                elif uploaded_logo:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                        tmp.write(uploaded_logo.getvalue())
                        logo_tmp_path = tmp.name
                    logo_path_to_use = logo_tmp_path

                stamp_path_to_use = None
                stamp_tmp_path = None
                if os.path.exists("stamp.png"): stamp_path_to_use = "stamp.png"
                elif uploaded_stamp:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                        tmp.write(uploaded_stamp.getvalue())
                        stamp_tmp_path = tmp.name
                    stamp_path_to_use = stamp_tmp_path

                pdf = PDF(logo_path=logo_path_to_use, stamp_path=stamp_path_to_use)
                pdf.add_page()
                
                pdf.draw_section_header("监测基础信息")
                info_data = {
                    "客户名称": client_name, "报告日期": base_date_str, # 使用全局日期
                    "门店名称": store_name, "监测专员": staff_name,
                    "门店地址": address, "服务类型": service_type
                }
                pdf.draw_info_box(info_data)
                
                pdf.draw_section_header("智能监测趋势分析")
                try:
                    d_rat = [int(x.strip()) for x in trend_rat_str.split(',')]
                    d_roach = [int(x.strip()) for x in trend_roach_str.split(',')]
                    d_fly = [int(x.strip()) for x in trend_fly_str.split(',')]
                    chart_path = generate_trend_chart(d_rat, d_roach, d_fly)
                    pdf.add_chart(chart_path)
                    os.unlink(chart_path) 
                except:
                    st.warning("趋势数据格式错误，已跳过图表生成")

                pdf.draw_section_header("智能终端监测日志")
                if areas_status: pdf.draw_inspection_table(areas_status)
                else: 
                    pdf.set_font('SimHei', '', 10)
                    pdf.cell(0, 10, "（暂无监测点位数据）", 0, 1, 'L')

                if suggestion_text: pdf.draw_suggestion_box(suggestion_text)

                pdf.draw_section_header("监测结论与建议")
                def print_summary_block(label, text):
                    h_box = 12
                    if pdf.get_y() + h_box > 275: pdf.add_page()
                    pdf.set_fill_color(248, 249, 250)
                    pdf.rect(15, pdf.get_y(), 180, h_box, 'F')
                    pdf.set_font('SimHei', '', 11)
                    pdf.set_x(20)
                    pdf.set_text_color(100, 100, 100)
                    pdf.cell(20, h_box, f"{label}：", 0, 0)
                    pdf.set_text_color(0, 0, 0)
                    pdf.cell(0, h_box, text, 0, 1)
                    pdf.ln(2) 
                print_summary_block("鼠类", summary_rat)
                print_summary_block("蟑螂", summary_roach)
                print_summary_block("飞虫", summary_fly)
                pdf.ln(2)

                if processed_mouse or processed_roach or processed_fly:
                    pdf.draw_section_header("终端现场监测情况")
                    if processed_mouse:
                        pdf.draw_sub_section_title("粘鼠板监测画面")
                        pdf.add_image_grid(processed_mouse)
                    if processed_roach:
                        pdf.draw_sub_section_title("蟑螂屋监测画面")
                        pdf.add_image_grid(processed_roach)
                    if processed_fly:
                        pdf.draw_sub_section_title("灭蝇灯监测画面")
                        pdf.add_image_grid(processed_fly)

                pdf.draw_materials_list()
                pdf.add_closing_banner()

                pdf_output = pdf.output(dest='S').encode('latin-1')
                st.success("✅ 智能监测报告生成成功！")
                
                # 调整 4：文件名包含日期
                file_date_suffix = base_date_str.replace("-", "")
                st.download_button(
                    label="📥 下载 PDF 报告",
                    data=pdf_output,
                    file_name=f"PCO报告_{store_name}_{file_date_suffix}.pdf",
                    mime="application/pdf"
                )
                
                # Cleanup
                if logo_tmp_path and os.path.exists(logo_tmp_path): os.unlink(logo_tmp_path)
                if stamp_tmp_path and os.path.exists(stamp_tmp_path): os.unlink(stamp_tmp_path)

            except Exception as e:
                st.error(f"发生错误: {e}")
                import traceback
                st.text(traceback.format_exc())