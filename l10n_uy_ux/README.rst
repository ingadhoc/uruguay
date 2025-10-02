.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

==========
Uruguay UX
==========

This module enhances the official Uruguayan localization with additional UX improvements and features that are not yet available in the official Odoo modules but are valuable for our clients.

Functional description
======================

**Problems solved:**

1. **Uruware Connection Configuration Issue**: This module stores both test and production connection data, allowing users to simply switch between environments in settings without additional configuration. New fields are added to the settings interface.

2. **Legal PDF Report Limitations**: This module always prints the legal PDF for all print actions (invoice print, unpaid invoices, send & print, automatic sending upon validation).

3. **Report Parameter Limitations**: Extended functionality that:
   - Adds company-level parameter in system settings for global PDF format configuration

**New functionalities added:**

1. **DGI Registry Lookup**: Allows querying contact data to check if they are electronic issuers and retrieve registry data as an assistant to help fill contact information more easily. Adds lookup functionality in contact forms.

2. **XML Preview and Validation**: Enables XML preview at any time (not just in demo mode or when errors occur). Adds "Validate XML" button for testing purposes.

3. **Enhanced Addenda and Mandatory Legends Logic**:
   - System defaults: Adds condition field to help apply addenda to documents when conditions are met
   - Preview functionality: Button to preview how they will look before sending

4. **Uruware Invoice Import**: Allows importing invoices created in Uruware from manual sales journals. Users can enter UUID and click "Get Uruware Invoice" to automatically retrieve document number, document type, DGI status, and legal PDF. Adds import functionality to journal interfaces.

5. **Certificate Management**: Adds informational fields in settings to store DGI Certificate and associated key as backup for configuring them in Uruware prod/test when necessary.

Installation
============

To install this module, you need to:

1. Ensure you have the official Uruguay localization modules installed
2. Install this module through the Apps menu or by updating the module list
3. No additional external dependencies are required

Configuration
=============

1. Go to Settings > Users & Companies > Companies
2. Configure your Uruware test and production connection data
3. Set your preferred report parameters for PDF generation
4. Configure DGI certificate information if needed
5. Set up addenda and mandatory legends conditions as required

Usage
=====

**Uruware Environment Switching:**
- Navigate to electronic invoicing settings
- Toggle between test and production environments without reconfiguration

**DGI Registry Lookup:**
- Open any contact form
- Use the DGI lookup feature to automatically populate contact information

**XML Preview and Validation:**
- Access XML preview from any electronic document
- Use "Validate XML" button for testing purposes

**Uruware Invoice Import:**
- Open manual sales journal entries
- Enter UUID and click "Get Uruware Invoice" to import invoice data

**Report Configuration:**
- Access company settings to configure global PDF parameters
- Set addenda and legend conditions as needed

Known issues / Roadmap
======================

* Integration with official Odoo reporting system for legal PDF representation
* Enhanced error handling for Uruware connection failures

Contributors
============

* ADHOC

Maintainer
==========

This module is maintained by ADHOC
