-- ============================================================
-- Default Initial Seed Data for Shree Krushidhan Agri-Input Shop ERP
-- ============================================================

-- 1. Standard Measurement Units
INSERT OR IGNORE INTO units (unit_id, unit_name, symbol) VALUES
(1, 'Bottle', 'BTL'),
(2, 'Bag', 'BAG'),
(3, 'Packet / Pouch', 'PKT'),
(4, 'Kilogram', 'KG'),
(5, 'Gram', 'GM'),
(6, 'Litre', 'LTR'),
(7, 'Millilitre', 'ML'),
(8, 'Quintal', 'QTL'),
(9, 'Numbers / Pieces', 'NOS');

-- 2. Standard Unit Conversions
INSERT OR IGNORE INTO unit_conversions (from_unit_id, to_unit_id, conversion_factor) VALUES
(4, 5, 1000.0), -- 1 KG = 1000 GM
(6, 7, 1000.0), -- 1 LTR = 1000 ML
(2, 4, 50.0),   -- 1 BAG = 50 KG
(8, 4, 100.0);  -- 1 QTL = 100 KG

-- 3. Standard GST Tax Groups
INSERT OR IGNORE INTO tax_groups (tax_group_id, tax_group_name, cgst_rate, sgst_rate, igst_rate) VALUES
(1, 'Exempted (0%)', 0.0, 0.0, 0.0),
(2, 'GST 5% (Fertilizers & Bulk Inputs)', 2.5, 2.5, 5.0),
(3, 'GST 12% (Agricultural Equipment & Implements)', 6.0, 6.0, 12.0),
(4, 'GST 18% (Pesticides, Insecticides & Sprayers)', 9.0, 9.0, 18.0),
(5, 'GST 28% (Luxury & Specialized Machinery)', 14.0, 14.0, 28.0);

-- 4. Standard Product Categories
INSERT OR IGNORE INTO categories (category_id, category_name, short_name, is_hardware_category) VALUES
(1, 'Chemical Fertilizers (रासायनिक खते)', 'FERT', 0),
(2, 'Hybrid & Certified Seeds (बियाणे)', 'SEED', 0),
(3, 'Insecticides & Pesticides (कीटकनाशके)', 'PEST', 0),
(4, 'Fungicides & Herbicides (बुरशीनाशके / तणनाशके)', 'FUNG', 0),
(5, 'Plant Growth Regulators & Bio-Stimulants (टॉनिक / बायो)', 'PGR', 0),
(6, 'Agricultural Hardware & Drip (कृषी उपकरणे / ठिबक)', 'HARD', 1);

-- 5. Standard Crops
INSERT OR IGNORE INTO crops (crop_id, crop_name, description) VALUES
(1, 'Sugarcane (ऊस)', 'Cash crop with high fertilizer requirement'),
(2, 'Cotton (कापूस)', 'Pest sensitive commercial crop'),
(3, 'Soybean (सोयाबीन)', 'Kharif oilseed crop'),
(4, 'Wheat (गहू)', 'Rabi cereal crop'),
(5, 'Onion (कांदा)', 'High fungicide and fertilizer demand'),
(6, 'Tomato (टोमॅटो)', 'Horticulture crop'),
(7, 'Grapes (द्राक्षे)', 'Export quality horticulture crop'),
(8, 'Pomegranate (डाळिंब)', 'Horticulture fruit crop'),
(9, 'Maize (मका)', 'Cereal and fodder crop'),
(10, 'Chilli (मिरची)', 'Vegetable & spice crop');

-- 6. Standard Customer Groups
INSERT OR IGNORE INTO customer_groups (group_id, group_name, discount_percent) VALUES
(1, 'Retail Farmer (किरकोळ शेतकरी)', 0.0),
(2, 'Wholesale Buyer (घाऊक व्यापारी)', 2.0),
(3, 'Grampanchayat / Krishi Mandal (कृषी संस्था)', 5.0);

-- 7. Standard Indian Agri-Input Manufacturers / Brands
INSERT OR IGNORE INTO manufacturers (manufacturer_id, manufacturer_name, contact_person, mobile) VALUES
(1, 'Bayer CropScience Limited', 'Territory Manager', '9800000001'),
(2, 'Syngenta India Limited', 'Sales Representative', '9800000002'),
(3, 'Mahadhan (Smartchem Technologies)', 'Regional Officer', '9800000003'),
(4, 'Mahyco Seeds Limited', 'Area Manager', '9800000004'),
(5, 'UPL Limited', 'Field Executive', '9800000005'),
(6, 'Dhanuka Agritech Limited', 'Marketing Officer', '9800000006'),
(7, 'Corteva Agriscience', 'Sales Manager', '9800000007'),
(8, 'Advanta Seeds', 'Territory Executive', '9800000008'),
(9, 'Rashtriya Chemicals & Fertilizers (RCF)', 'Distributor Lead', '9800000009'),
(10, 'Coromandel International Limited', 'Agri Officer', '9800000010'),
(11, 'PI Industries', 'Field Officer', '9800000011'),
(12, 'Sumitomo Chemical India', 'Area Lead', '9800000012');

-- 8. System Chart of Accounts (Double-Entry Foundation)
INSERT OR IGNORE INTO ledger_accounts (account_id, account_name, account_group, is_system) VALUES
(1, 'Cash in Hand', 'CASH', 1),
(2, 'Bank Account', 'BANK_ACCOUNTS', 1),
(3, 'Sales Account', 'INCOME', 1),
(4, 'Purchase Account', 'EXPENSE', 1),
(5, 'Sales Return Account', 'EXPENSE', 1),
(6, 'Purchase Return Account', 'INCOME', 1),
(7, 'CGST Output Account', 'LIABILITIES', 1),
(8, 'SGST Output Account', 'LIABILITIES', 1),
(9, 'IGST Output Account', 'LIABILITIES', 1),
(10, 'CGST Input Account', 'ASSETS', 1),
(11, 'SGST Input Account', 'ASSETS', 1),
(12, 'IGST Input Account', 'ASSETS', 1),
(13, 'Discount Allowed Account', 'EXPENSE', 1),
(14, 'Discount Received Account', 'INCOME', 1),
(15, 'Round Off Account', 'EXPENSE', 1);

-- 9. Standard Expense Categories
INSERT OR IGNORE INTO expense_categories (category_id, category_name, description) VALUES
(1, 'Shop Rent (दुकान भाडे)', 'Monthly premises rental'),
(2, 'Electricity Bill (वीज बिल)', 'Power and electricity expenses'),
(3, 'Staff Salaries & Wages (हमाली / मजुरी)', 'Employee salaries and daily labor'),
(4, 'Freight & Transportation (वाहतूक खर्च)', 'Goods inward and delivery transport'),
(5, 'Tea, Water & Refreshments (चहा / आदरातिथ्य)', 'Shop hospitality expenses'),
(6, 'Stationery & Printing (स्टेशनरी / छपाई)', 'Billing paper, toner and shop supplies');

-- 10. Real Company Profile — Krushidhan Krushi Udyog Samuh
INSERT OR IGNORE INTO company_settings (
    setting_id, company_name, address, city, state, pincode, mobile, email,
    gstin, dl_fertilizer, dl_pesticide, dl_seed,
    bank_name, account_no, ifsc_code, invoice_terms, default_invoice_size
) VALUES (
    1,
    'कृषीधन कृषी उद्योग समूह',
    'गट नं. १/७, घर नं. २५२, नागोबा कट्ट्याशेजारी, विसापूर, ता. तासगाव, जि. सांगली',
    'विसापूर, ता. तासगाव, जि. सांगली',
    'Maharashtra',
    '416314',
    '9503573620 / 7218409780',
    'akashlengare15@gmail.com',
    '27BSXPL3414R1Z5',
    'LCFRD0920250506SNG',
    'LCID0920250497SNG',
    'LCSD0920250506SNG',
    'IDBI Bank',
    '409002609103',
    'IBKL0000055',
    '१. बिलामधील नमूद केलेली कीटकनाशके मी माझ्या मर्जीने घेतलेली आहेत.\n२. उत्पादनाची हमी संबंधित उत्पादक कंपनीची राहील.\n३. सर्व वाद तासगाव / सांगली न्यायालयाच्या कार्यक्षेत्रात.\n४. माल एकदा विकल्यानंतर परत घेतला जाणार नाही.\n५. उधारीचा व्यवहार ३० दिवसांत पूर्ण करावा.',
    'A4'
);

-- 11. Default Admin & Owner Users (Default Password: krushidhan@2026)
INSERT OR IGNORE INTO users (user_id, username, password_hash, full_name, role, is_active) VALUES
(1, 'admin', '7adeac2dfbc21f07e8a90a6a84309007e8a77d04c9008d19d8758633ff8e3304', 'आकाश लेंगारे (Admin)', 'ADMIN', 1),
(2, 'akash', '7adeac2dfbc21f07e8a90a6a84309007e8a77d04c9008d19d8758633ff8e3304', 'आकाश लेंगारे', 'ADMIN', 1);
