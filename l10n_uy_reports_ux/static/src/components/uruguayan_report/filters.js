import { _t } from "@web/core/l10n/translation";

import { AccountReport } from "@account_reports/components/account_report/account_report";
import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";

export class L10nUYTaxReportFilters extends AccountReportFilters {
    get selectedUYTaxType() {
        if (!this.controller.cachedFilterOptions.uy_vat_book_tax_types_available) {
            return _t("All");
        }
        const availableTypes = Object.keys(this.controller.cachedFilterOptions.uy_vat_book_tax_types_available);
        const selectedTypes = Object.values(
            this.controller.cachedFilterOptions.uy_vat_book_tax_types_available,
        ).filter((type) => type.selected);

        if (selectedTypes.length === availableTypes.length || selectedTypes.length === 0) {
            return _t("All");
        }

        return selectedTypes.map((type) => type.name).join(", ");
    }

    selectUyVatBookTaxType(taxType) {
        if (!this.controller.cachedFilterOptions.uy_vat_book_tax_types_available) {
            return;
        }
        const newUYVatBookTaxTypes = Object.assign(
            {},
            this.controller.cachedFilterOptions.uy_vat_book_tax_types_available,
        );
        newUYVatBookTaxTypes[taxType]["selected"] = !newUYVatBookTaxTypes[taxType]["selected"];
        this.filterClicked({ optionKey: "uy_vat_book_tax_types_available", optionValue: newUYVatBookTaxTypes, reload: true});
    }
}

AccountReport.registerCustomComponent(L10nUYTaxReportFilters);
