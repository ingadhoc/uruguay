.. image:: https://img.shields.io/badge/licence-LGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/lgpl-3.0-standalone.html
   :alt: License: LGPL-3

==============================
Uruguay - E-Invoicing POS UX
==============================

Improves how the Point of Sale handles the CFE of its invoices in Uruguay.

Functional description
======================

**Problems solved:**

1. **Invoice with CFE in error from the POS**: when DGI does not validate the CFE of a sale, the sale goes on and its invoice stays posted with its temporary name (``* <id>``). It gets no PDF: neither the invoice report of Odoo nor a proforma. The invoice is fixed and sent again from the backend, even with the session still open.

2. **The cashier did not notice the error**: after paying, the POS warns that the sale was registered but its tax receipt was not issued, with the detail DGI or Uruware returned and what to do: ask a supervisor to fix the tax receipt from the backend, giving them the order number. In Orders, each sale shows the state of its CFE in its own column.

3. **PDF only when it is needed**: the POS does not download the invoice after each sale. The PDF of Uruware is asked the first time the invoice is printed (from Orders in the POS, or from the portal) and it stays on the invoice, so the next prints use the same file.

4. **Printing an invoice without CFE**: printing from the POS shows the error instead of a PDF. The portal (for example, from the QR of the receipt) says the tax receipt was not issued, without showing or rendering any PDF.

**New functionalities added:**

1. **CFE in error filter**: in the invoices and in the POS orders of the backend, to find the sales whose CFE was not issued.

2. **Final consumer limit**: before paying, the POS asks for an identified customer (ID number, address, city, state and country) when the sale exceeds the amount DGI allows for an unidentified one: 5000 UI, taxes included. Without it, that sale is registered with its CFE in error. Backport of Odoo 20, to be removed when migrating the module.

Configuration
=============

The module installs itself with the Uruguayan e-invoicing and the Point of Sale.

The final consumer limit needs no configuration: it is always checked in Uruguay, with the rate of the indexed unit (UYI) of the day.

Usage
=====

**Fixing an invoice with CFE in error:**

- Filter the invoices (or the POS orders) by **CFE in error**
- Open the invoice, reset it to draft and fix what DGI rejects (for example, the customer data)
- Confirm it: the CFE is sent again and the payment of the POS is reconciled, before or after closing the session

Contributors
============

* ADHOC

Maintainer
==========

This module is maintained by ADHOC
