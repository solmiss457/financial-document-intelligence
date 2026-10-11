-- Fiscal year end of the reporting period, entered with the document (registration or upload).
-- G1 uses it to detect "in 2024" questions about companies whose fiscal year is not the calendar year.
SET LOCAL ROLE fdi_owner;
ALTER TABLE fdi.documents ADD COLUMN fiscal_year_end date;
