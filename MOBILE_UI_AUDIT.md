# Krushidhan Agri-Input Shop ERP — Mobile UI Audit Report

**Date:** September 16, 2026  
**Auditor:** Senior Mobile UX & Software Architect  
**Target Viewports:** 320px, 360px, 375px, 390px, 414px, 430px (Smartphones) & 768px (Tablets)  

---

## 1. Viewport-by-Viewport Audit Findings

### 320px (Ultra-Small Phones e.g. iPhone SE 1st Gen, KaiOS/Basic Androids)
- **Header:** Header title "KRUSHIDHAN AGRI-INPUT SHOP ERP" wraps into 3 lines. User auth badge ("آकाश लेंगारे ADMIN") pushes "100% Offline Mode" and "1-Click Backup" off-screen or causes severe vertical header expansion.
- **Navigation:** 11 horizontal desktop tabs require excessive horizontal swiping. Tabs off-screen are invisible to the shopkeeper.
- **Billing (`#tab-pos`):**
  - Customer details card takes 280px vertical height before product search is even visible.
  - Cart table requires 280px horizontal scrolling (`min-width: 600px`).
  - Total Net Payable and "Save & Print" button are pushed completely below the fold (~750px down), requiring heavy vertical scrolling during every bill creation.
  - Touch targets on cart item delete buttons (`Del`) are under 30px × 30px, making tap precision difficult.
- **Modals:** Modal dialogs with fixed padding exceed 320px width if minimum width constraints apply, causing viewport horizontal overflow.

### 360px & 375px (Standard Android Devices e.g. Galaxy A series, Redmi)
- **Header:** Sub-badge text ("श्री कृषीधन कृषी सेवा केंद्र...") wraps excessively.
- **Quick-Add Bar:** Product dropdown `#pos-item-product` truncates long brand names (e.g. "Syngenta Ampligo Chlorantraniliprole 100ml").
- **Cart Table:** 9 columns (`#`, Description, Batch, Exp, Qty, Rate, Taxable, Total, Del) are squeezed or force horizontal scrolling.
- **Form Rows:** Multi-column `.form-row` inputs stack into 1 column at `< 600px`, making form height 2.5× longer.

### 390px, 414px & 430px (Large Smartphones e.g. iPhone 13/14/15 Pro Max, Pixel 7/8, Galaxy S23/S24)
- **Billing Workflow:** Stacking `.pos-left` above `.pos-right` means the billing total summary and payment controls are completely separated from the quick-add bar.
- **Product Search:** Datalist autocomplete dropdowns (`#pos-cust-suggestions`) pop up over inputs and push page height dynamically.
- **Buttons:** Action buttons (`+ Add Item`, `Save & Print Invoice`) lack touch feedback states (`:active`) and full touch height (minimum 44px recommended by Apple/Google HIG).

### 768px (Tablets / iPad portrait)
- **Grid Layouts:** 2-column and 3-column cards stack single-column at `< 900px`, leaving excess empty horizontal margins on tablet portrait screens.
- **Header:** Header items sit nicely on 1 line, but navigation bar tabs require right scroll arrow cues.

---

## 2. Component-by-Component Issue Breakdown

### A. Navigation & Header Structure
1. **Desktop Horizontal Tabs on Mobile:** 11 horizontal tabs (`Counter Billing`, `Farmer Status`, `Supplier Khata`, `Inward Purchase`, `Live Stock`, `Accounts`, `PnL`, `GST`, `Statutory Registers`, `Product Catalog`, `Shop Profile`) are hard to navigate on phone screens.
2. **Missing Mobile Quick-Nav:** No bottom tab bar or drawer menu for fast 1-tap tab switching on phone screens.
3. **Header Clutter:** Backup button, user badge, and offline indicator crowd the top bar on mobile screens.

### B. POS Billing Screen (Highest Priority)
1. **Vertical Disconnect Between Cart & Totals:** Shopkeeper cannot see the Running Net Payable amount while adding items without scrolling to the bottom of the page.
2. **Cart Table Density on Mobile:** 9-column HTML table forces horizontal scrolling on 320px-430px screens.
3. **Quick-Add Form Stack Height:** Stacking 6 form fields vertically consumes the full screen height before the cart table is visible.
4. **Touch Target Sizes:** Delete buttons, quantity increment/decrement controls, and dropdown selects are smaller than 44px × 44px.

### C. Forms & Inputs
1. **Input Touch Heights:** Default input height (~34px) is small for thumbs; needs 44px touch height on mobile screens.
2. **Form Row Stacking:** Multi-column rows stack into tall single columns; needs smart 2-column flex grids for compact pairs (e.g. Qty + Rate side-by-side).

### D. Tables & Data Reports
1. **Unresponsive Tables:** Stock list, Ledger tables, Statutory Registers, and GST reports force wide horizontal scrolling without priority column visibility or card alternatives.
2. **Header Freeze / Sticky Header:** Table headers lose sticky positioning on mobile browsers when container scrolls.

### E. Modals & Dialogs
1. **Modal Backdrops & Viewport Heights:** Modals exceed screen height on mobile keyboards open states (`max-height` overflow issues).
2. **Close Buttons:** Close buttons (`×`) are small touch targets (less than 30px).

---

## 3. Required Mobile Responsive Solution Plan

1. **Header & Navigation Overhaul:**
   - Preserve existing desktop horizontal tabs for screens > 768px.
   - Implement a mobile-friendly header with a Hamburger/Drawer Toggle & compact Mobile Navigation bar for screens ≤ 768px.
   - Include a Mobile Bottom Action / Navigation Bar for instant access to top 4 screens (`Billing`, `Stock`, `Farmer Khata`, `Menu`).

2. **POS Billing Optimization (Mobile POS View):**
   - **Sticky Top Bar / Sticky Bottom Bar for Billing Totals:** Display live Net Payable total and 1-tap "Save & Print" button fixed at the bottom of the screen on mobile devices.
   - **Compact Touch Quick-Add Bar:** Group `Qty` and `Rate` side-by-side in a 2-column touch row with big `+` and `-` quantity stepper buttons.
   - **Responsive Cart Items View:** On phone screens (< 600px), render cart items as compact touch-friendly cards or streamlined 4-column cards (`Item Name & Batch`, `Qty × Rate`, `Total`, `Delete Action`).

3. **Touch-First Controls & Typography:**
   - Minimum touch target size of 44px × 44px for all interactive buttons and inputs on mobile viewports.
   - Font sizes tuned for legibility (minimum 14px for body/inputs, 16px for headings).

4. **Responsive Tables & Card Views:**
   - Add mobile card stack layouts for dense lists (Farmer List, Stock List, Product Catalog).
   - Enable touch-momentum smooth scrolling (`-webkit-overflow-scrolling: touch`) with sticky table headers.

5. **Modals & Keyboard Safety:**
   - Modal dialogs auto-center with 92% viewport width and 85vh max-height with internal scrolling body and fixed sticky action footers.

6. **Desktop Preservation & Zero Regression:**
   - Enclose all mobile-specific adjustments inside strict `@media (max-width: 768px)` and `@media (max-width: 600px)` breakpoint queries.
   - Ensure desktop layout (screens > 768px / 1024px / 1440px) remains 100% identical and unchanged.
