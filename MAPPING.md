# Source‑to‑Target Mapping Document

This document captures the **column mappings** and **business transformations** that are applied when moving data from the source (CSV files) to the target Microsoft SQL Server tables.

---

## 1. Employees (`employees.csv` ➜ `dbo.employees`)
| Source Column | Target Column | Transformation |
|---------------|---------------|----------------|
| `id`          | `id`          | – |
| `name`        | `name`        | – |
| `hire_date`   | `hire_date`   | – |
| `salary`      | `salary`      | – |
| –             | `salary_usd`  | `salary_usd = salary * 1.2` *(convert salary to USD)* |

**Notes**
- The `salary_usd` column exists only in the target; it is derived from the source `salary` using the transformation defined in `metadata.yaml` under `employees.transformations`.
- Validation checks the aggregated sum of `salary * 1.2` in the source against the sum of `salary_usd` in the target.

---

## 2. Departments (`departments.csv` ➜ `dbo.departments`)
| Source Column | Target Column | Transformation |
|---------------|---------------|----------------|
| `dept_id`     | `dept_id`     | – |
| `dept_name`   | `dept_name`   | – |

_No additional transformations are defined for this table._

---

## 3. Projects (`projects.csv` ➜ `dbo.projects`)
| Source Column   | Target Column   | Transformation |
|-----------------|-----------------|----------------|
| `project_id`    | `project_id`    | – |
| `project_name`  | `project_name`  | – |
| `department_id` | `department_id` | – |
| `start_date`    | `start_date`    | – |
| `budget`        | `budget`        | – |
| –               | `budget_usd`    | `budget_usd = budget * 1.2` *(convert budget to USD)* |

**Referential Integrity**
- `projects.department_id` → `departments.dept_id` (FK defined in `metadata.yaml`).

---

## How Transformations are Applied in Code
1. **Metadata definition** – Each table may include a `transformations` list.  Each entry provides:
   - `name` – an identifier for the transformation.
   - `source_expression` – a valid Pandas‑compatible expression evaluated against the source ``DataFrame``.
   - `target_column` – the name of the column that will appear in the target table.
2. **Utility function** – `src.etl.transformation.apply_transformations(table_key, df)` reads the transformation list from ``metadata.yaml`` and creates the new target columns on the DataFrame.
3. **Main workflow** – In ``src/etl/main.py`` the source DataFrame is passed through the transformation utility before validation and loading, ensuring the transformed columns are present for the validation step that compares source aggregates to the target aggregates.

---

## Future Extensions
- Add rounding or currency formatting to the transformation expressions.
- Introduce additional business‑logic transformations (e.g., flagging high‑budget projects).
- Synchronise the transformation logic with the actual ETL load process (e.g., within a stored procedure or an ELT tool) to keep the source‑to‑target contract consistent.

---

*Generated on 2026‑05‑31*