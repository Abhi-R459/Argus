# HR workforce setup and imports

Open **Employees → Departments & roles** (also available in Settings). Create a
department, then create its job titles and annual salary bands. A new department
is selected automatically. The searchable role catalogue shows existing titles
and bands, and the role form retains its department after each successful save.
These job roles describe employees; they do not grant application login access.

Use **Add Personnel** for one employee or **Import employees** for up to 100.
The import dialog downloads an empty CSV template and accepts pasted CSV text:

```csv
full_name,email,job_title,department,national_id,contact_info,date_hired,salary
```

Use an existing job title and department name (matching ignores case and outer
spaces), an ISO date such as `2024-01-31`, and a positive annual salary in rupees
without currency signs or thousands separators. Quote text containing commas,
line breaks or double quotes using standard CSV quoting. Each email must be
unique. The preview reports invalid rows; edit the source and review it again
before confirming. Previewing does not save any records.

After confirmation, the HR API saves at most 20 employees in each transaction,
including initial salary rows and immutable audit history. National IDs and
contact information use the same encryption as individual registrations. A
failed batch rolls back completely; earlier successful batches remain saved.
The dialog reports confirmed progress and makes no automatic retry of a failed
batch. After a network interruption, check the directory for existing emails
before importing the remaining rows; the last request may have committed even
if its response was lost. Keep the dialog open until it finishes. Closing the
page does not undo a batch already accepted by the server.

Employee records do not create Google accounts or Supabase login users. Login
remains restricted to the server's approved HR and auditor email lists. New
workforce records confer no application access.

The counterfactual screen preloads the first 100 directory entries. Use its
**Employee ID → Use employee ID** control to investigate any other employee.
