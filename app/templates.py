from html import escape


def dashboard_html(
    stats: dict,
    events: list[dict],
) -> str:

    rows = ""

    for event in events:

        status = (
            "Deleted"
            if event["deleted_successfully"]
            else "FAILED"
        )

        status_class = (
            "success"
            if event["deleted_successfully"]
            else "danger"
        )

        username = event["username"] or "-"

        group = escape(
            event["group_title"] or "Unknown Group"
        )

        filename = escape(
            event["file_name"]
        )

        created_at = event["created_at"]

        rows += f"""
        <tr>
            <td>{created_at}</td>
            <td>{group}</td>
            <td>{filename}</td>
            <td>{escape(username)}</td>
            <td>
                <span class="badge {status_class}">
                    {status}
                </span>
            </td>
        </tr>
        """

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>Telegram File Guard</title>

<style>

* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    background: #0f172a;
    color: #e2e8f0;
    font-family:
        Inter,
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
}}

.container {{
    max-width: 1400px;
    margin: auto;
    padding: 30px;
}}

h1 {{
    margin-bottom: 5px;
}}

.subtitle {{
    color: #94a3b8;
    margin-bottom: 30px;
}}

.cards {{
    display: grid;
    grid-template-columns:
        repeat(auto-fit, minmax(180px, 1fr));

    gap: 18px;
    margin-bottom: 30px;
}}

.card {{
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 14px;
    padding: 22px;
}}

.card-title {{
    color: #94a3b8;
    font-size: 14px;
}}

.card-value {{
    font-size: 32px;
    font-weight: 700;
    margin-top: 8px;
}}

.table-container {{
    background: #1e293b;
    border-radius: 14px;
    border: 1px solid #334155;
    overflow-x: auto;
}}

table {{
    width: 100%;
    border-collapse: collapse;
}}

th,
td {{
    padding: 15px;
    text-align: left;
    border-bottom: 1px solid #334155;
    white-space: nowrap;
}}

th {{
    color: #94a3b8;
    font-size: 13px;
}}

.badge {{
    padding: 5px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
}}

.success {{
    background: #064e3b;
    color: #6ee7b7;
}}

.danger {{
    background: #7f1d1d;
    color: #fca5a5;
}}

.refresh {{
    display: inline-block;
    margin-bottom: 20px;
    padding: 10px 15px;
    border-radius: 8px;
    background: #2563eb;
    color: white;
    text-decoration: none;
}}

</style>

</head>

<body>

<div class="container">

<h1>🛡️ Telegram File Guard</h1>

<div class="subtitle">
    Security & Moderation Dashboard
</div>

<a class="refresh"
   href="javascript:location.reload()">
    Refresh
</a>

<div class="cards">

<div class="card">
    <div class="card-title">
        Total Detected
    </div>

    <div class="card-value">
        {stats["total"]}
    </div>
</div>

<div class="card">
    <div class="card-title">
        Successfully Deleted
    </div>

    <div class="card-value">
        {stats["successful"]}
    </div>
</div>

<div class="card">
    <div class="card-title">
        Failed
    </div>

    <div class="card-value">
        {stats["failed"]}
    </div>
</div>

<div class="card">
    <div class="card-title">
        Groups
    </div>

    <div class="card-value">
        {stats["groups"]}
    </div>
</div>

<div class="card">
    <div class="card-title">
        Users
    </div>

    <div class="card-value">
        {stats["users"]}
    </div>
</div>

<div class="card">
    <div class="card-title">
        Deleted Today
    </div>

    <div class="card-value">
        {stats["today"]}
    </div>
</div>

</div>

<div class="table-container">

<table>

<thead>

<tr>
    <th>Time</th>
    <th>Group</th>
    <th>File</th>
    <th>User</th>
    <th>Status</th>
</tr>

</thead>

<tbody>

{rows}

</tbody>

</table>

</div>

</div>

</body>
</html>
"""