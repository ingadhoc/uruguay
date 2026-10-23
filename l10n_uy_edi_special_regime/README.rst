.. image:: https://img.shields.io/badge/licence-LGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/lgpl-3.0-standalone.html
   :alt: License: LGPL-3

======================================
Uruguay - CFE Special Taxpayer Regimes
======================================

This module allows companies under a DGI special regime (Literal E / minimum VAT or
monotributo) to issue valid CFEs.

When the company is under a special regime, Uruware signs the CFEs with a special CAE
(values 2, 3 or 4) and DGI requires the document to meet two conditions that the standard
``l10n_uy_edi`` module does not cover:

* Gross amounts indicator ``MntBruto = 3`` (zone A10 of the header).
* Invoicing indicator ``IndFact = 16`` (minimum VAT, Monotributo or others) instead of the
  VAT rate indicators (1 exempt, 2 minimum rate, 3 basic rate, 4 other rate). The conceptual
  indicators are still used as in the general regime: 5 (free delivery), 6/7 (non-billable,
  e.g. down payments and discount lines) and 10 (export) — confirmed by Uruware.

Without these indicators DGI rejects the document with the error
*"Si el valor del CAE Especial es 2, 3 o 4 entonces el Ind. Mnt Bruto debe ser 3"* (code 05,
a definitive rejection that burns the CAE number).

The ``MntBruto = 3`` indicator applies to every CFE type the company issues —
e-Ticket (101), e-Invoice (111), their credit and debit notes (102, 103, 112, 113) and also
the export CFEs (121, 122, 123): the special CAE is a property of the taxpayer, so Uruware
signs every document with it and DGI requires the indicator on all of them. Export lines keep
their own invoicing indicator (``IndFact = 10``).

The module also validates that the document lines do not carry VAT at a rate other than 0%
(exempt): the user gets a blocking error when the invoice is confirmed, and the same check
runs before sending. Every DGI rejection burns a CAE number, so it is better to stop the
error in Odoo as early as possible.

Configuration
-------------

#. In Odoo: on the company, field **DGI Taxpayer Regime**, select the regime that applies
   (default: general regime, which does not change any behaviour).
#. In Uruware: menu **Empresa** → section **Información Extra** → set **"Literal E o
   monotributo"** to *Sí*. Without this setting Uruware does not sign with the special CAE.

Both settings must be aligned: they mirror each other.

Known issues / Roadmap
======================

Credits
=======

ADHOC

Contributors
------------

* ADHOC

Maintainer
----------

This module is maintained by ADHOC
