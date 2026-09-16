"""
Professional Agri-Input Tax Invoice Generator (Maharashtra Crystal Reports Layout).
Supports bilingual Marathi / English Devanagari typography, licensing details, and statutory declarations.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Optional, Union
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from src.models.sales import Sale
from src.models.system import CompanySettings

# Register Unicode Devanagari Fonts
FONTS_DIR = Path(__file__).resolve().parent / "fonts"
REG_FONT_PATH = FONTS_DIR / "NotoSansDevanagari-Regular.ttf"
BOLD_FONT_PATH = FONTS_DIR / "NotoSansDevanagari-Bold.ttf"

HAS_DEVANAGARI_FONT = False
if REG_FONT_PATH.exists() and BOLD_FONT_PATH.exists():
    try:
        pdfmetrics.registerFont(TTFont("DevaRegular", str(REG_FONT_PATH)))
        pdfmetrics.registerFont(TTFont("DevaBold", str(BOLD_FONT_PATH)))
        HAS_DEVANAGARI_FONT = True
    except Exception as e:
        print(f"Warning: Could not register Devanagari font: {e}")

FONT_NAME = "DevaRegular" if HAS_DEVANAGARI_FONT else "Helvetica"
FONT_BOLD = "DevaBold" if HAS_DEVANAGARI_FONT else "Helvetica-Bold"


class InvoicePrinter:
    """Generates authentic Maharashtra Agri-Retail GST Tax Invoices in Crystal Reports style."""

    def __init__(self, company_settings: Optional[CompanySettings] = None):
        self.settings = company_settings or CompanySettings(
            company_name="कृषीधन कृषी उद्योग समूह",
            mobile="9503573620 / 7218409780",
            address="गट नं. १/७, घर नं. २५२, नागोबा कट्ट्याशेजारी, विसापूर, ता. तासगाव, जि. सांगली",
            city="विसापूर, ता. तासगाव, जि. सांगली",
            state="Maharashtra",
            email="akashlengare15@gmail.com",
            gstin="27BSXPL3414R1Z5",
            dl_fertilizer="LCFRD0920250506SNG",
            dl_pesticide="LCID0920250497SNG",
            dl_seed="LCSD0920250506SNG",
        )

    def _number_to_words(self, number: float) -> str:
        """Converts Indian Rupee amount to words."""
        units = ["", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE"]
        teens = ["TEN", "ELEVEN", "TWELVE", "THIRTEEN", "FOURTEEN", "FIFTEEN", "SIXTEEN", "SEVENTEEN", "EIGHTEEN", "NINETEEN"]
        tens = ["", "", "TWENTY", "THIRTY", "FORTY", "FIFTY", "SIXTY", "SEVENTY", "EIGHTY", "NINETY"]

        def convert_less_than_thousand(n: int) -> str:
            res = ""
            if n >= 100:
                res += units[n // 100] + " HUNDRED "
                n %= 100
            if n >= 20:
                res += tens[n // 10] + " "
                n %= 10
            elif n >= 10:
                res += teens[n - 10] + " "
                n = 0
            if n > 0:
                res += units[n] + " "
            return res.strip()

        amount_int = int(round(number))
        if amount_int == 0:
            return "ZERO RUPEES ONLY"

        crore = amount_int // 10000000
        amount_int %= 10000000
        lakh = amount_int // 100000
        amount_int %= 100000
        thousand = amount_int // 1000
        amount_int %= 1000
        hundreds = amount_int

        parts = []
        if crore > 0:
            parts.append(f"{convert_less_than_thousand(crore)} CRORE")
        if lakh > 0:
            parts.append(f"{convert_less_than_thousand(lakh)} LAKH")
        if thousand > 0:
            parts.append(f"{convert_less_than_thousand(thousand)} THOUSAND")
        if hundreds > 0:
            parts.append(convert_less_than_thousand(hundreds))

        return f"RS. {' '.join(parts)} ONLY"

    def generate_invoice_pdf(
        self,
        sale: Sale,
        output_path: Optional[Union[str, Path]] = None,
        page_size=A4,
    ) -> bytes:
        """
        Generates a PDF Tax Invoice in authentic Crystal Reports Agri layout.
        """
        buffer = io.BytesIO()
        target_file = str(output_path) if output_path else buffer

        # Page setup with compact 8mm margins to fit dense invoice layout
        doc = SimpleDocTemplate(
            target_file,
            pagesize=page_size,
            leftMargin=8 * mm,
            rightMargin=8 * mm,
            topMargin=8 * mm,
            bottomMargin=8 * mm,
        )

        story = []
        styles = getSampleStyleSheet()

        # Custom Typography Styles
        title_style = ParagraphStyle(
            "ShopTitle",
            parent=styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=16,
            leading=18,
            alignment=1,  # Center
            textColor=colors.HexColor("#b91c1c"),  # Authentic Red Title
        )
        tagline_style = ParagraphStyle(
            "ShopTagline",
            parent=styles["Normal"],
            fontName=FONT_NAME,
            fontSize=8.5,
            leading=11,
            alignment=1,
            textColor=colors.HexColor("#15803d"),  # Forest Green
        )
        owner_style = ParagraphStyle(
            "ShopOwner",
            parent=styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=9,
            leading=12,
            alignment=1,
            textColor=colors.HexColor("#111827"),
        )
        small_text = ParagraphStyle(
            "SmallText",
            parent=styles["Normal"],
            fontName=FONT_NAME,
            fontSize=8,
            leading=10.5,
        )
        small_bold = ParagraphStyle(
            "SmallBold",
            parent=styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=8,
            leading=10.5,
        )
        table_hdr_style = ParagraphStyle(
            "TableHdr",
            parent=styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=8,
            leading=10,
            alignment=1,
        )
        table_cell = ParagraphStyle(
            "TableCell",
            parent=styles["Normal"],
            fontName=FONT_NAME,
            fontSize=8,
            leading=10,
        )
        table_cell_bold = ParagraphStyle(
            "TableCellBold",
            parent=styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=8,
            leading=10,
            alignment=2,  # Right
        )
        disclaimer_style = ParagraphStyle(
            "Disclaimer",
            parent=styles["Normal"],
            fontName=FONT_NAME,
            fontSize=7,
            leading=9,
            textColor=colors.HexColor("#374151"),
        )

        # -------------------------------------------------------------------------
        # 1. TOP HEADER (Licenses Box on Left + Shop Banner on Right)
        # -------------------------------------------------------------------------
        pay_mode_label = sale.payment_mode.upper() if sale.payment_mode else "CASH"
        lic_box_html = f"""
        <b>TAX INVOICE : {pay_mode_label}</b><br/>
        Fertilizer L. No : {self.settings.dl_fertilizer or 'LCFRD0920250506SNG'}<br/>
        Insectiside L. No: {self.settings.dl_pesticide or 'LCID0920250497SNG'}<br/>
        Seeds L. No &nbsp;&nbsp;&nbsp;&nbsp;: {self.settings.dl_seed or 'LCSD0920250506SNG'}<br/>
        GSTIN : {self.settings.gstin or '27BSXPL3414R1Z5'}
        """
        lic_p = Paragraph(lic_box_html, small_text)

        shop_banner_html = f"""
        <div align="center">
            <font size="16" color="#b91c1c"><b>कृषीधन कृषी उद्योग समूह</b></font><br/>
            <font size="8" color="#15803d"><b>विसापूर • विश्वासनीय ठिकाण...</b></font><br/>
            <font size="7" color="#15803d">आमचेकडे नामांकित कंपनीची शेती औषधे, रासायनिक खते, बी-बियाणे, किटकनाशके, तणनाशके, बुरशीनाशके योग्य दरात मिळतील.</font><br/>
            <font size="8.5"><b>👤 प्रोपा. श्री. आकाश लेंगारे &nbsp;|&nbsp; 📞 ९५०३५७३६२० / ७२१८४०९७८०</b></font><br/>
            <font size="7.5">पत्ता: {self.settings.address or 'नागोबा कट्ट्याशेजारी, विसापूर, ता. तासगाव.'} &nbsp;|&nbsp; E-mail: {self.settings.email or 'akashlengare15@gmail.com'}</font>
        </div>
        """
        banner_p = Paragraph(shop_banner_html, styles["Normal"])

        header_table_data = [[lic_p, banner_p]]
        header_table = Table(header_table_data, colWidths=[62 * mm, 132 * mm])
        header_table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 1, colors.black),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(header_table)

        # -------------------------------------------------------------------------
        # 2. CUSTOMER & INVOICE META ROW
        # -------------------------------------------------------------------------
        time_str = "11:30 AM"
        clean_inv_no = sale.invoice_no.replace('INV-', '')
        cust_box_html = f"""
        <b>Cust Name :</b> {(sale.customer_name or 'CASH CUSTOMER').upper()}<br/>
        <b>Address &nbsp;&nbsp;:</b> {(sale.customer_village or 'SHOP / LOCAL').upper()}<br/>
        <b>Mobile &nbsp;&nbsp;&nbsp;&nbsp;:</b> {sale.customer_mobile or '-'}<br/>
        <b>Crop Details :</b> {sale.doctor_or_officer or 'ऊस / सर्व पिके'}
        """
        inv_box_html = f"""
        <b>Invoice No. :</b> S/2026-27/{clean_inv_no}<br/>
        <b>Date & Time :</b> {sale.sale_date} {time_str}<br/>
        <b>Payment Mode:</b> {pay_mode_label}<br/>
        <b>Farmer GSTIN:</b> {sale.customer_gstin or 'URP'}
        """

        cust_p = Paragraph(cust_box_html, small_text)
        inv_p = Paragraph(inv_box_html, small_text)

        meta_table_data = [[cust_p, inv_p]]
        meta_table = Table(meta_table_data, colWidths=[118 * mm, 76 * mm])
        meta_table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 1, colors.black),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(meta_table)

        # -------------------------------------------------------------------------
        # 3. ITEM TABLE (Crystal Reports Marathi Column Headers)
        # -------------------------------------------------------------------------
        headers = [
            Paragraph("<b>मालाचा तपशील<br/>(Description)</b>", table_hdr_style),
            Paragraph("<b>कंपनीचे नाव<br/>(Company)</b>", table_hdr_style),
            Paragraph("<b>वाण<br/>(Crop)</b>", table_hdr_style),
            Paragraph("<b>बॅच नंबर<br/>(Batch)</b>", table_hdr_style),
            Paragraph("<b>अंतिम मुदत<br/>(Exp)</b>", table_hdr_style),
            Paragraph("<b>पॅकिंग<br/>(Packing)</b>", table_hdr_style),
            Paragraph("<b>दर<br/>(Rate)</b>", table_hdr_style),
            Paragraph("<b>एकूण नग<br/>(Qty)</b>", table_hdr_style),
            Paragraph("<b>एकूण रक्कम<br/>(Amount)</b>", table_hdr_style),
        ]

        item_rows = [headers]
        for item in sale.items:
            comp_name = "KRUSHIDHAN AGRO"
            p_name_upper = (item.product_name or "").upper()
            if "BAYER" in p_name_upper or "XIVANA" in p_name_upper:
                comp_name = "BAYER CROP"
            elif "CRYSTAL" in p_name_upper or "BAVISTIN" in p_name_upper:
                comp_name = "CRYSTAL CROP"
            elif "SYNGENTA" in p_name_upper:
                comp_name = "SYNGENTA"
            elif "MAHADHAN" in p_name_upper:
                comp_name = "MAHADHAN"
            elif "MAHYCO" in p_name_upper:
                comp_name = "MAHYCO SEEDS"
            elif "IFFCO" in p_name_upper:
                comp_name = "IFFCO LTD"
            elif "UPL" in p_name_upper:
                comp_name = "UPL LIMITED"

            item_rows.append(
                [
                    Paragraph(f"<b>{item.product_name}</b>", table_cell),
                    Paragraph(comp_name, table_cell),
                    Paragraph("-", table_cell),
                    Paragraph(item.batch_no or "-", table_cell),
                    Paragraph(item.exp_date or "-", table_cell),
                    Paragraph(item.unit_name or "NOS", table_cell),
                    Paragraph(f"{item.sale_rate:.2f}", ParagraphStyle("R", parent=table_cell, alignment=2)),
                    Paragraph(f"{item.qty:g}", ParagraphStyle("C", parent=table_cell, alignment=1)),
                    Paragraph(f"<b>{item.total_amount:.2f}</b>", table_cell_bold),
                ]
            )

        # Pad empty rows to give standard receipt height if fewer than 5 items
        min_rows = 5
        curr_items_count = len(sale.items)
        if curr_items_count < min_rows:
            for _ in range(min_rows - curr_items_count):
                item_rows.append([Paragraph("&nbsp;", table_cell) for _ in range(9)])

        # Columns total width = 194mm (Full printable width)
        col_widths = [
            46 * mm,  # Product Description
            28 * mm,  # Company Name
            14 * mm,  # Crop/Variety
            22 * mm,  # Batch No
            18 * mm,  # Exp Date
            16 * mm,  # Packing/Unit
            16 * mm,  # Rate
            14 * mm,  # Qty
            20 * mm,  # Amount
        ]

        items_table = Table(item_rows, colWidths=col_widths)
        items_table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 1, colors.black),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(items_table)

        # -------------------------------------------------------------------------
        # 4. BOTTOM FOOTER & STATUTORY MARATHI DECLARATION
        # -------------------------------------------------------------------------
        amount_words_str = self._number_to_words(sale.net_amount)
        sub_total = sale.net_amount - sale.extra_charges
        due_bal = max(0.0, sale.net_amount - sale.paid_amount)

        left_footer_html = f"""
        <b>{amount_words_str}</b>
        <br/><br/>
        <font size="6.5" color="#374151">
        बिलामधील नमूद केलेली कीटकनाशके मी माझ्या मर्जीने घेतलेली आहेत. त्यास फवारणीचे वापर करताना घ्यावयाची संपूर्ण दक्षतेबाबत मला माहिती दिलेली असून पुढील सर्व जबाबदारी माझी राहील. ही औषधे फक्त शेती उपयोगासाठी घेतली आहेत.
        </font>
        <br/><br/>
        <table width="100%">
            <tr>
                <td align="left"><b>ग्राहकाची सही (Customer Sign)</b></td>
                <td align="right"><b>आपल्या भेटीबद्दल आभारी आहोत. धन्यवाद !</b></td>
            </tr>
        </table>
        """
        left_footer_p = Paragraph(left_footer_html, small_text)

        totals_table_data = [
            [Paragraph("Sub Total :", small_bold), Paragraph(f"₹ {sub_total:.2f}", ParagraphStyle("TR", parent=small_text, alignment=2))],
            [Paragraph("Freight & Postage :", small_text), Paragraph(f"₹ {sale.extra_charges:.2f}", ParagraphStyle("TR", parent=small_text, alignment=2))],
            [Paragraph("<b>NET BILL AMT :</b>", small_bold), Paragraph(f"<b>₹ {sale.net_amount:.2f}</b>", ParagraphStyle("TRB", parent=small_bold, alignment=2))],
            [Paragraph("PAID AMT :", small_text), Paragraph(f"₹ {sale.paid_amount:.2f}", ParagraphStyle("TR", parent=small_text, alignment=2))],
            [Paragraph("<b>BALANCE AMT :</b>", small_bold), Paragraph(f"<b>₹ {due_bal:.2f}</b>", ParagraphStyle("TR", parent=small_bold, alignment=2))],
            [Paragraph("<font size='6.5'>For <b>KRUSHIDHAN AGRI UDYOG SAMUH</b><br/><br/>Authorized Signatory</font>", ParagraphStyle("Auth", parent=small_text, alignment=1)), Paragraph("")],
        ]
        totals_table = Table(totals_table_data, colWidths=[36 * mm, 30 * mm])
        totals_table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
                    ("INNERGRID", (0, 0), (-1, -2), 0.5, colors.HexColor("#d1d5db")),
                    ("SPAN", (0, -1), (1, -1)),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )

        bottom_main_data = [[left_footer_p, totals_table]]
        bottom_table = Table(bottom_main_data, colWidths=[124 * mm, 70 * mm])
        bottom_table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 1, colors.black),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(bottom_table)

        # Jurisdiction note
        story.append(Spacer(1, 2))
        jurisdiction_p = Paragraph("<font size='6.5' color='#6b7280'>Subject to TASGAON / SANGLI Jurisdiction • Software by Krushidhan ERP</font>", ParagraphStyle("J", parent=small_text, alignment=1))
        story.append(jurisdiction_p)

        doc.build(story)

        if output_path:
            with open(output_path, "rb") as f:
                return f.read()
        return buffer.getvalue()
