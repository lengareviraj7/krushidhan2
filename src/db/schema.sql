-- ============================================================
-- Offline Agri-Input Shop ERP - Complete SQLite DDL Schema
-- Compatible with SQLite 3.35+
-- ============================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- 1. MASTER DATA TABLES
-- ------------------------------------------------------------

-- Categories (Fertilizer, Seed, Pesticide, Hardware, Bio-Fertilizer, etc.)
CREATE TABLE IF NOT EXISTS categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_name TEXT NOT NULL UNIQUE,
    short_name TEXT,
    is_hardware_category INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Manufacturers / Companies (IFFCO, Bayer, Syngenta, Mahyco, etc.)
CREATE TABLE IF NOT EXISTS manufacturers (
    manufacturer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    manufacturer_name TEXT NOT NULL UNIQUE,
    contact_person TEXT,
    mobile TEXT,
    address TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Standard Measurement Units (Nos, KG, GM, LTR, ML, BAG, QTL, etc.)
CREATE TABLE IF NOT EXISTS units (
    unit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_name TEXT NOT NULL UNIQUE,
    symbol TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Unit Conversions (e.g. 1 BAG = 50 KG, 1 LTR = 1000 ML, 1 QTL = 100 KG)
CREATE TABLE IF NOT EXISTS unit_conversions (
    conversion_id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_unit_id INTEGER NOT NULL REFERENCES units(unit_id) ON DELETE CASCADE,
    to_unit_id INTEGER NOT NULL REFERENCES units(unit_id) ON DELETE CASCADE,
    conversion_factor REAL NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(from_unit_id, to_unit_id)
);

-- GST Tax Groups (Exempt, 5%, 12%, 18%, 28%)
CREATE TABLE IF NOT EXISTS tax_groups (
    tax_group_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tax_group_name TEXT NOT NULL UNIQUE,
    cgst_rate REAL DEFAULT 0,
    sgst_rate REAL DEFAULT 0,
    igst_rate REAL DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Target Crops Master (Cotton, Soybean, Sugarcane, Wheat, Tomato, Onion, etc.)
CREATE TABLE IF NOT EXISTS crops (
    crop_id INTEGER PRIMARY KEY AUTOINCREMENT,
    crop_name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Product Master (SKU)
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL,
    category_id INTEGER REFERENCES categories(category_id),
    manufacturer_id INTEGER REFERENCES manufacturers(manufacturer_id),
    hsn_code TEXT,
    unit_id INTEGER REFERENCES units(unit_id),
    tax_group_id INTEGER REFERENCES tax_groups(tax_group_id),
    default_purchase_rate REAL DEFAULT 0,
    default_sale_rate REAL DEFAULT 0,
    default_mrp REAL DEFAULT 0,
    min_stock_alert REAL DEFAULT 0,
    crop_id INTEGER REFERENCES crops(crop_id),
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Customer Groups / Categories (Retail, Wholesale, Farmer Club, etc.)
CREATE TABLE IF NOT EXISTS customer_groups (
    group_id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_name TEXT NOT NULL UNIQUE,
    discount_percent REAL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Customer Master (Farmers & Wholesale buyers)
CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL,
    mobile TEXT,
    village TEXT,
    taluka TEXT,
    district TEXT,
    state TEXT DEFAULT 'Maharashtra',
    aadhar_no TEXT,
    gstin TEXT,
    group_id INTEGER REFERENCES customer_groups(group_id),
    opening_balance REAL DEFAULT 0,
    current_balance REAL DEFAULT 0,
    credit_limit REAL DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Supplier / Distributor Master
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_name TEXT NOT NULL,
    contact_person TEXT,
    mobile TEXT,
    email TEXT,
    address TEXT,
    city TEXT,
    state TEXT DEFAULT 'Maharashtra',
    gstin TEXT,
    pan TEXT,
    dl_number TEXT,
    bank_name TEXT,
    account_no TEXT,
    ifsc_code TEXT,
    opening_balance REAL DEFAULT 0,
    current_balance REAL DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Extra Charges Master (Freight, Loading/Unloading, Labour, Delivery)
CREATE TABLE IF NOT EXISTS extra_charges_master (
    charge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    charge_name TEXT NOT NULL UNIQUE,
    tax_group_id INTEGER REFERENCES tax_groups(tax_group_id),
    default_amount REAL DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);


-- ------------------------------------------------------------
-- 2. INVENTORY & BATCH MANAGEMENT TABLES
-- ------------------------------------------------------------

-- Batch-Wise Stock Management (FEFO support)
CREATE TABLE IF NOT EXISTS stock_batches (
    batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    batch_no TEXT NOT NULL,
    mfg_date TEXT,
    exp_date TEXT,
    purchase_rate REAL NOT NULL DEFAULT 0,
    sale_rate REAL NOT NULL DEFAULT 0,
    mrp REAL NOT NULL DEFAULT 0,
    opening_qty REAL DEFAULT 0,
    current_qty REAL DEFAULT 0,
    barcode TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(product_id, batch_no)
);

-- Stock Ledger (Immutable stock audit trail for every IN/OUT event)
CREATE TABLE IF NOT EXISTS stock_ledger (
    ledger_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    batch_id INTEGER REFERENCES stock_batches(batch_id),
    transaction_type TEXT NOT NULL, -- 'PURCHASE', 'PURCHASE_RETURN', 'SALE', 'SALE_RETURN', 'ADJUSTMENT'
    reference_type TEXT NOT NULL,   -- 'INVOICE', 'CHALLAN', 'MANUAL_ADJUSTMENT'
    reference_id INTEGER NOT NULL,
    movement_date TEXT DEFAULT CURRENT_TIMESTAMP,
    qty_in REAL DEFAULT 0,
    qty_out REAL DEFAULT 0,
    balance_qty REAL NOT NULL,
    rate REAL,
    remarks TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);


-- ------------------------------------------------------------
-- 3. PURCHASE MANAGEMENT TABLES
-- ------------------------------------------------------------

-- Inward Purchase Invoices
CREATE TABLE IF NOT EXISTS purchases (
    purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no TEXT NOT NULL,
    purchase_date TEXT NOT NULL,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(supplier_id),
    challan_no TEXT,
    payment_type TEXT DEFAULT 'CREDIT', -- 'CASH', 'CREDIT', 'BANK_TRANSFER'
    total_taxable REAL DEFAULT 0,
    total_cgst REAL DEFAULT 0,
    total_sgst REAL DEFAULT 0,
    total_igst REAL DEFAULT 0,
    extra_charges REAL DEFAULT 0,
    round_off REAL DEFAULT 0,
    net_amount REAL NOT NULL,
    paid_amount REAL DEFAULT 0,
    due_amount REAL DEFAULT 0,
    remarks TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Purchase Items / Line Items
CREATE TABLE IF NOT EXISTS purchase_items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id INTEGER NOT NULL REFERENCES purchases(purchase_id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    batch_no TEXT NOT NULL,
    mfg_date TEXT,
    exp_date TEXT,
    qty REAL NOT NULL,
    free_qty REAL DEFAULT 0,
    unit_id INTEGER REFERENCES units(unit_id),
    purchase_rate REAL NOT NULL,
    sale_rate REAL NOT NULL,
    mrp REAL NOT NULL,
    discount_percent REAL DEFAULT 0,
    discount_amount REAL DEFAULT 0,
    taxable_amount REAL NOT NULL,
    cgst_rate REAL DEFAULT 0,
    cgst_amount REAL DEFAULT 0,
    sgst_rate REAL DEFAULT 0,
    sgst_amount REAL DEFAULT 0,
    igst_rate REAL DEFAULT 0,
    igst_amount REAL DEFAULT 0,
    total_amount REAL NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Purchase Return
CREATE TABLE IF NOT EXISTS purchase_returns (
    return_id INTEGER PRIMARY KEY AUTOINCREMENT,
    return_no TEXT NOT NULL UNIQUE,
    return_date TEXT NOT NULL,
    purchase_id INTEGER REFERENCES purchases(purchase_id),
    supplier_id INTEGER NOT NULL REFERENCES suppliers(supplier_id),
    total_taxable REAL DEFAULT 0,
    total_tax REAL DEFAULT 0,
    round_off REAL DEFAULT 0,
    net_amount REAL NOT NULL,
    remarks TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Purchase Return Line Items
CREATE TABLE IF NOT EXISTS purchase_return_items (
    return_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    return_id INTEGER NOT NULL REFERENCES purchase_returns(return_id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    batch_id INTEGER REFERENCES stock_batches(batch_id),
    qty REAL NOT NULL,
    purchase_rate REAL NOT NULL,
    taxable_amount REAL NOT NULL,
    tax_amount REAL DEFAULT 0,
    total_amount REAL NOT NULL,
    reason TEXT
);


-- ------------------------------------------------------------
-- 4. SALES & BILLING TABLES
-- ------------------------------------------------------------

-- Sales Invoices
CREATE TABLE IF NOT EXISTS sales (
    sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no TEXT NOT NULL UNIQUE,
    sale_date TEXT NOT NULL,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    doctor_or_officer TEXT,
    payment_mode TEXT DEFAULT 'CASH', -- 'CASH', 'CREDIT', 'UPI', 'CARD', 'SPLIT'
    total_taxable REAL DEFAULT 0,
    total_cgst REAL DEFAULT 0,
    total_sgst REAL DEFAULT 0,
    total_igst REAL DEFAULT 0,
    total_discount REAL DEFAULT 0,
    extra_charges REAL DEFAULT 0,
    round_off REAL DEFAULT 0,
    net_amount REAL NOT NULL,
    paid_amount REAL DEFAULT 0,
    due_amount REAL DEFAULT 0,
    print_count INTEGER DEFAULT 0,
    remarks TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Sale Line Items
CREATE TABLE IF NOT EXISTS sale_items (
    sale_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL REFERENCES sales(sale_id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    batch_id INTEGER NOT NULL REFERENCES stock_batches(batch_id),
    qty REAL NOT NULL,
    unit_id INTEGER REFERENCES units(unit_id),
    sale_rate REAL NOT NULL,
    mrp REAL NOT NULL,
    discount_percent REAL DEFAULT 0,
    discount_amount REAL DEFAULT 0,
    taxable_amount REAL NOT NULL,
    cgst_rate REAL DEFAULT 0,
    cgst_amount REAL DEFAULT 0,
    sgst_rate REAL DEFAULT 0,
    sgst_amount REAL DEFAULT 0,
    igst_rate REAL DEFAULT 0,
    igst_amount REAL DEFAULT 0,
    total_amount REAL NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Sales Returns
CREATE TABLE IF NOT EXISTS sales_returns (
    return_id INTEGER PRIMARY KEY AUTOINCREMENT,
    return_no TEXT NOT NULL UNIQUE,
    return_date TEXT NOT NULL,
    sale_id INTEGER REFERENCES sales(sale_id),
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    total_taxable REAL DEFAULT 0,
    total_tax REAL DEFAULT 0,
    round_off REAL DEFAULT 0,
    net_amount REAL NOT NULL,
    remarks TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Sales Return Line Items
CREATE TABLE IF NOT EXISTS sales_return_items (
    return_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    return_id INTEGER NOT NULL REFERENCES sales_returns(return_id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    batch_id INTEGER REFERENCES stock_batches(batch_id),
    qty REAL NOT NULL,
    sale_rate REAL NOT NULL,
    taxable_amount REAL NOT NULL,
    tax_amount REAL DEFAULT 0,
    total_amount REAL NOT NULL,
    reason TEXT
);


-- ------------------------------------------------------------
-- 5. ACCOUNTS & FINANCIAL LEDGER TABLES
-- ------------------------------------------------------------

-- Chart of Accounts
CREATE TABLE IF NOT EXISTS ledger_accounts (
    account_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_name TEXT NOT NULL UNIQUE,
    account_group TEXT NOT NULL, -- 'ASSETS', 'LIABILITIES', 'INCOME', 'EXPENSE', 'BANK_ACCOUNTS', 'CASH'
    opening_balance REAL DEFAULT 0,
    current_balance REAL DEFAULT 0,
    is_system INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Accounting Vouchers (Receipt, Payment, Contra, Journal, Debit Note, Credit Note)
CREATE TABLE IF NOT EXISTS vouchers (
    voucher_id INTEGER PRIMARY KEY AUTOINCREMENT,
    voucher_no TEXT NOT NULL UNIQUE,
    voucher_date TEXT NOT NULL,
    voucher_type TEXT NOT NULL, -- 'RECEIPT', 'PAYMENT', 'CONTRA', 'JOURNAL', 'DEBIT_NOTE', 'CREDIT_NOTE'
    total_amount REAL NOT NULL,
    narration TEXT,
    reference_type TEXT,        -- 'SALE', 'PURCHASE', 'EXPENSE', 'MANUAL'
    reference_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Double-Entry Ledger Posting Entries
CREATE TABLE IF NOT EXISTS ledger_entries (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    voucher_id INTEGER NOT NULL REFERENCES vouchers(voucher_id) ON DELETE CASCADE,
    account_id INTEGER NOT NULL REFERENCES ledger_accounts(account_id),
    debit_amount REAL DEFAULT 0,
    credit_amount REAL DEFAULT 0,
    particulars TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Expense Categories (Electricity, Shop Rent, Staff Salary, Tea/Refreshment, Transport)
CREATE TABLE IF NOT EXISTS expense_categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Expense Records
CREATE TABLE IF NOT EXISTS expenses (
    expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES expense_categories(category_id),
    expense_date TEXT NOT NULL,
    amount REAL NOT NULL,
    payment_account_id INTEGER REFERENCES ledger_accounts(account_id),
    reference_no TEXT,
    remarks TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);


-- ------------------------------------------------------------
-- 6. SYSTEM, USERS & SECURITY TABLES
-- ------------------------------------------------------------

-- Application Users & Roles
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    role TEXT DEFAULT 'OPERATOR', -- 'ADMIN', 'MANAGER', 'OPERATOR'
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Shop / Enterprise Settings
CREATE TABLE IF NOT EXISTS company_settings (
    setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    address TEXT,
    city TEXT,
    state TEXT DEFAULT 'Maharashtra',
    pincode TEXT,
    mobile TEXT,
    email TEXT,
    gstin TEXT,
    dl_fertilizer TEXT,
    dl_pesticide TEXT,
    dl_seed TEXT,
    bank_name TEXT,
    account_no TEXT,
    ifsc_code TEXT,
    invoice_terms TEXT,
    is_thermal_print INTEGER DEFAULT 0,
    default_invoice_size TEXT DEFAULT 'A4', -- 'A4', 'A5', '3INCH_THERMAL'
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Audit Trail
CREATE TABLE IF NOT EXISTS audit_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(user_id),
    action_type TEXT NOT NULL, -- 'INSERT', 'UPDATE', 'DELETE', 'LOGIN', 'BACKUP'
    table_name TEXT,
    record_id INTEGER,
    details TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Local Database Backups History
CREATE TABLE IF NOT EXISTS backup_log (
    backup_id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    backup_type TEXT NOT NULL, -- 'MANUAL', 'SCHEDULED', 'BEFORE_UPGRADE'
    backup_size_bytes INTEGER,
    status TEXT DEFAULT 'SUCCESS',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Schema Version Tracking Table
CREATE TABLE IF NOT EXISTS schema_version (
    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_number INTEGER NOT NULL UNIQUE,
    description TEXT NOT NULL,
    applied_at TEXT DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO schema_version (version_id, version_number, description) VALUES (1, 1, 'Initial Commercial ERP Baseline Schema');

-- ------------------------------------------------------------
-- INDEXES FOR MAXIMUM QUERY PERFORMANCE & REPORTING
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_hsn ON products(hsn_code);
CREATE INDEX IF NOT EXISTS idx_stock_batches_product ON stock_batches(product_id);
CREATE INDEX IF NOT EXISTS idx_stock_batches_exp ON stock_batches(exp_date);
CREATE INDEX IF NOT EXISTS idx_stock_ledger_product ON stock_ledger(product_id, batch_id);
CREATE INDEX IF NOT EXISTS idx_stock_ledger_date ON stock_ledger(movement_date);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_sales_invoice_no ON sales(invoice_no);
CREATE INDEX IF NOT EXISTS idx_sale_items_sale ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_product ON sale_items(product_id);
CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(purchase_date);
CREATE INDEX IF NOT EXISTS idx_purchases_supplier ON purchases(supplier_id);
CREATE INDEX IF NOT EXISTS idx_purchases_invoice_no ON purchases(invoice_no);
CREATE INDEX IF NOT EXISTS idx_purchase_items_purchase ON purchase_items(purchase_id);
CREATE INDEX IF NOT EXISTS idx_vouchers_date ON vouchers(voucher_date);
CREATE INDEX IF NOT EXISTS idx_ledger_entries_voucher ON ledger_entries(voucher_id);
CREATE INDEX IF NOT EXISTS idx_ledger_entries_account ON ledger_entries(account_id);
CREATE INDEX IF NOT EXISTS idx_customers_mobile ON customers(mobile);
CREATE INDEX IF NOT EXISTS idx_suppliers_mobile ON suppliers(mobile);

