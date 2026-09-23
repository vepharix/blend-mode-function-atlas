#!/usr/bin/env python3
"""Build a bilingual (Chinese-English) PDF atlas of blend-mode functions."""

from __future__ import annotations

from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "figures"
OUTPUT = REPO_ROOT / "docs" / "blend_mode_function_atlas_zh_en.pdf"
TMP = REPO_ROOT / "tmp" / "pdfs"

MODES = [
    ("Darken", "变暗", "min(B, S)", "逐通道选择较小值。", "Select the smaller value per channel."),
    ("Multiply", "正片叠底", "B*S", "总是不亮于任一输入。", "Never brighter than either input."),
    ("Color Burn", "颜色加深", "S=0: 0; else max(0, 1-(1-B)/S)", "S=0 单独定义为 0，并在下界截断。", "S=0 is defined as 0; clamp at the lower bound."),
    ("Linear Burn", "线性加深", "clamp(B+S-1)", "在线性相加后减 1，并截断到 [0,1]。", "Add linearly, subtract 1, then clamp to [0,1]."),
    ("Darker Color (grayscale)", "深色（灰度）", "min(B, S)", "RGB 版本比较整像素；灰度图退化为 Darken。", "The RGB mode compares whole pixels; grayscale reduces to Darken."),
    ("Lighten", "变亮", "max(B, S)", "逐通道选择较大值。", "Select the larger value per channel."),
    ("Screen", "滤色", "1-(1-B)(1-S)", "对补色相乘后再取补色。", "Multiply complements, then take the complement."),
    ("Color Dodge", "颜色减淡", "S=1: 1; else min(1, B/(1-S))", "S=1 单独定义为 1，并在上界截断。", "S=1 is defined as 1; clamp at the upper bound."),
    ("Linear Dodge (Add)", "线性减淡（添加）", "clamp(B+S)", "直接相加，并截断到 [0,1]。", "Add directly, then clamp to [0,1]."),
    ("Lighter Color (grayscale)", "浅色（灰度）", "max(B, S)", "RGB 版本比较整像素；灰度图退化为 Lighten。", "The RGB mode compares whole pixels; grayscale reduces to Lighten."),
    ("Overlay", "叠加", "B<=.5: 2BS; else 1-2(1-B)(1-S)", "分支由底层 B 决定；B=.5 时结果等于 S。", "The backdrop B selects the branch; at B=.5 the result equals S."),
    ("Soft Light", "柔光", "S<=.5: B-(1-2S)B(1-B); else B+(2S-1)(D(B)-B)", "采用 PDF/W3C 分段定义；D(B) 还在 B=.25 处分段。", "Uses the PDF/W3C piecewise definition; D(B) has another split at B=.25."),
    ("Hard Light", "强光", "S<=.5: 2BS; else 1-2(1-B)(1-S)", "分支由上层 S 决定；等价于交换输入后的 Overlay。", "The source S selects the branch; equivalent to Overlay with inputs exchanged."),
    ("Vivid Light", "亮光", "S<.5: Burn(B,2S); else Dodge(B,2S-1)", "下半区使用颜色加深，上半区使用颜色减淡。", "Uses Color Burn below the midpoint and Color Dodge above it."),
    ("Linear Light", "线性光", "clamp(B+2S-1)", "以 S=.5 为中性点的线性加减。", "Linear addition/subtraction with S=.5 as the neutral point."),
    ("Pin Light", "点光", "S<.5: min(B,2S); else max(B,2S-1)", "在中点两侧分别以 min 和 max 替换像素。", "Uses min below the midpoint and max above it."),
    ("Hard Mix", "实色混合", "VividLight(B,S)<.5: 0; else 1", "对亮光结果在 .5 处二值化；等于 .5 时取 1。", "Threshold Vivid Light at .5; equality maps to 1."),
]


def safe_name(name: str) -> str:
    return name.lower().replace(" ", "_").replace("(", "").replace(")", "")


def downsample(source: Path, target: Path, max_width=1000):
    target.parent.mkdir(parents=True, exist_ok=True)
    with PILImage.open(source) as im:
        if im.width > max_width:
            height = round(im.height * max_width / im.width)
            im = im.resize((max_width, height), PILImage.Resampling.LANCZOS)
        im.save(target, optimize=True)


def page_decor(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(colors.HexColor("#17324d"))
    canvas.rect(0, height - 13 * mm, width, 13 * mm, fill=1, stroke=0)
    canvas.setFont("STSong-Light", 8.5)
    canvas.setFillColor(colors.white)
    canvas.drawString(16 * mm, height - 8.5 * mm, "混合模式函数图谱 | Blend Mode Function Atlas")
    canvas.setFillColor(colors.HexColor("#5b6b7a"))
    canvas.drawRightString(width - 16 * mm, 9 * mm, f"{doc.page}")
    canvas.setStrokeColor(colors.HexColor("#d9e1e8"))
    canvas.line(16 * mm, 13 * mm, width - 16 * mm, 13 * mm)
    canvas.restoreState()


def mode_card(mode, styles):
    en, zh, formula, zh_note, en_note = mode
    img_path = TMP / f"{safe_name(en)}.png"
    downsample(SOURCE / "single_modes" / f"{safe_name(en)}.png", img_path)
    title = Paragraph(f"<b>{zh}</b>  {en}", styles["card_title"])
    formula_p = Paragraph(formula, styles["formula"])
    note = Paragraph(f"{zh_note}<br/><font color='#536273'>{en_note}</font>", styles["note"])
    picture = Image(str(img_path), width=50 * mm, height=43.1 * mm)
    card = Table([[title], [formula_p], [picture], [note]], colWidths=[82 * mm])
    card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf2f8")),
        ("BOX", (0, 0), (-1, -1), .65, colors.HexColor("#b8c7d4")),
        ("LINEBELOW", (0, 1), (-1, 1), .35, colors.HexColor("#d8e1e8")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (0, 2), (0, 2), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return card


def build():
    registerFont(UnicodeCIDFont("STSong-Light"))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CNTitle", fontName="STSong-Light", fontSize=25, leading=33,
                              textColor=colors.HexColor("#17324d"), alignment=TA_CENTER, spaceAfter=10))
    styles.add(ParagraphStyle(name="CNSub", fontName="STSong-Light", fontSize=12, leading=19,
                              textColor=colors.HexColor("#536273"), alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="Section", fontName="STSong-Light", fontSize=17, leading=23,
                              textColor=colors.HexColor("#17324d"), spaceAfter=8))
    styles.add(ParagraphStyle(name="BodyCN", fontName="STSong-Light", fontSize=10, leading=17,
                              textColor=colors.HexColor("#253746"), alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="card_title", fontName="STSong-Light", fontSize=10.5, leading=14,
                              textColor=colors.HexColor("#17324d")))
    styles.add(ParagraphStyle(name="formula", fontName="Courier", fontSize=7.4, leading=10,
                              textColor=colors.HexColor("#334e68")))
    styles.add(ParagraphStyle(name="note", fontName="STSong-Light", fontSize=7.5, leading=10.5,
                              textColor=colors.HexColor("#263746")))

    doc = BaseDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
                          topMargin=19 * mm, bottomMargin=17 * mm,
                          title="Blend Mode Function Atlas - Chinese-English Edition",
                          author="Blend Mode Function Atlas")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates(PageTemplate(id="atlas", frames=[frame], onPage=page_decor))

    story = [Spacer(1, 19 * mm),
             Paragraph("混合模式函数图谱", styles["CNTitle"]),
             Paragraph("Blend Mode Function Atlas", styles["CNTitle"]),
             Spacer(1, 4 * mm),
             Paragraph("中英文对照版 | Bilingual Chinese-English Edition", styles["CNSub"]),
             Spacer(1, 11 * mm)]

    overview_small = TMP / "overview.png"
    downsample(SOURCE / "blend_modes_overview.png", overview_small, max_width=1500)
    story += [Image(str(overview_small), width=166 * mm, height=199.2 * mm), PageBreak()]

    story += [Paragraph("阅读方法 | How to Read the Maps", styles["Section"]),
              Paragraph("每张图都把底层（背景）值 B 放在横轴，把上层（源）值 S 放在纵轴。两者与输出 R 均已归一化到 [0,1]。颜色由深紫到黄色，对应 R 从 0 到 1；白色等值线标出 R=.25、.5 和 .75。", styles["BodyCN"]),
              Spacer(1, 3 * mm),
              Paragraph("Each map places backdrop value B on the horizontal axis and source value S on the vertical axis. B, S, and result R are normalized to [0,1]. The shared color scale runs from dark purple at R=0 to yellow at R=1; white contours mark R=.25, .5, and .75.", styles["BodyCN"]),
              Spacer(1, 6 * mm),
              Paragraph("边界与截断 | Boundaries and Clamping", styles["Section"]),
              Paragraph("除法类模式需要显式处理分母为零的边界。Color Burn 在 S=0 时定义为 0；Color Dodge 在 S=1 时定义为 1。Linear Burn、Linear Dodge、Linear Light 以及所有可能越界的中间结果均截断到 [0,1]。Soft Light 采用 PDF/W3C 的分段函数，其中 D(B)=((16B-12)B+4)B（B<=.25），否则 D(B)=sqrt(B)。", styles["BodyCN"]),
              Spacer(1, 3 * mm),
              Paragraph("Division-based modes require explicit zero-denominator boundaries. Color Burn is defined as 0 at S=0; Color Dodge is defined as 1 at S=1. Linear Burn, Linear Dodge, Linear Light, and all potentially out-of-range intermediate results are clamped to [0,1]. Soft Light uses the PDF/W3C piecewise function, with D(B)=((16B-12)B+4)B for B<=.25 and D(B)=sqrt(B) otherwise.", styles["BodyCN"]),
              Spacer(1, 6 * mm),
              Paragraph("关于 Darker Color / Lighter Color | Whole-pixel Comparison", styles["Section"]),
              Paragraph("Darker Color 与 Lighter Color 在 RGB 图像中比较整像素的亮度并整体选择一个像素，因此无法由单通道二维函数完整表达。本图谱展示灰度情形；此时它们分别与 Darken、Lighten 相同。", styles["BodyCN"]),
              Spacer(1, 3 * mm),
              Paragraph("In RGB images, Darker Color and Lighter Color compare whole-pixel luminosity and select one complete pixel. A scalar 2D function cannot fully represent that behavior. The atlas therefore shows the grayscale case, where they reduce to Darken and Lighten respectively.", styles["BodyCN"]),
              PageBreak()]

    group_titles = [
        "变暗组 | Darken Group",
        "变亮组 | Lighten Group",
        "对比与光照组 I | Contrast and Light Group I",
        "对比与光照组 II | Contrast and Light Group II",
        "阈值模式 | Threshold Mode",
    ]
    groups = [MODES[0:5], MODES[5:10], MODES[10:14], MODES[14:16], MODES[16:17]]
    for group_title, group in zip(group_titles, groups):
        story.append(Paragraph(group_title, styles["Section"]))
        rows = []
        for i in range(0, len(group), 2):
            left = mode_card(group[i], styles)
            right = mode_card(group[i + 1], styles) if i + 1 < len(group) else ""
            rows.append([left, right])
        grid = Table(rows, colWidths=[88 * mm, 88 * mm], hAlign="CENTER")
        grid.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story += [grid, PageBreak()]

    story += [Paragraph("校验摘要 | Verification Summary", styles["Section"]),
              Paragraph("函数使用 1001 x 1001 的规则网格采样。所有模式的输出均为有限值，范围均落在 [0,1]。自动断言覆盖了 Overlay 与 Hard Light 的分支方向和中点连续性、Soft Light 的两个 D(B) 区间、Color Burn / Dodge 的除零边界、Vivid Light 的端点与中性点、Pin Light 的上下分支，以及 Hard Mix 的 .5 阈值约定。", styles["BodyCN"]),
              Spacer(1, 3 * mm),
              Paragraph("Functions were sampled on a regular 1001 x 1001 grid. Every mode produced finite values within [0,1]. Automated assertions cover Overlay and Hard Light branch orientation and midpoint continuity, both D(B) regions of Soft Light, the zero-denominator boundaries of Color Burn and Dodge, Vivid Light endpoints and neutral point, both Pin Light branches, and the .5 threshold convention of Hard Mix.", styles["BodyCN"]),
              Spacer(1, 7 * mm),
              Paragraph("复现 | Reproduction", styles["Section"]),
              Paragraph("运行 generate_blend_mode_maps.py 可重新生成总览图、全部单图与文本校验报告。PDF 由 build_bilingual_pdf.py 从这些图像构建。", styles["BodyCN"]),
              Spacer(1, 3 * mm),
              Paragraph("Run generate_blend_mode_maps.py to regenerate the overview, individual maps, and text verification report. The PDF is assembled from those figures by build_bilingual_pdf.py.", styles["BodyCN"])]
    doc.build(story)
    print(OUTPUT)


if __name__ == "__main__":
    build()
