# Child Tables

In Frappe, a **child table** (`istable: true`) is a doctype that exists only as rows embedded inside a parent document. They cannot be created independently.

## Child tables in ExamPro

### Exam Added Question
**Parent:** `Exam`  
Questions resolved onto a specific exam instance. Populated when an Exam Schedule is created, drawing from the `Exam Category Settings` weightage configuration.

### Exam Category Settings
**Parent:** `Exam`  
Defines how many questions to draw from each `Exam Question Category` and the marks per question. This weightage matrix drives question selection when building an exam.

### Exam Answer
**Parent:** `Exam Submission`  
One row per submitted answer. Stores the candidate's response, whether it was correct (`is_correct`), the marks awarded (`mark`), evaluator feedback (`evaluator_response`), and grading state (`evaluation_status`).

### Exam Batch User
**Parent:** `Exam Batch`  
Links Frappe users (candidates) to a named batch group. Batches are then assigned to Exam Schedules.

### Schedule Batch Assignment
**Parent:** `Exam Schedule`  
Links `Exam Batch` groups and their assigned proctors to a schedule. One row per batch assigned to the schedule run.

### Quick Quiz Question
**Parent:** `Quick Quiz`  
Questions embedded directly in a Quick Quiz (not drawn from the shared category bank, unless imported).

### Quick Quiz Answer
**Parent:** `Quick Quiz Question`  
Answer options for a Quick Quiz question. One row per answer choice; one option is flagged as correct.

### Exam Partner User
**Parent:** `Exam Partner`  
Staff users belonging to a partner organisation. Controls which Frappe users are scoped to that partner's data in the Studio.
