from flask import Flask
from database import cursor

app = Flask(__name__)

@app.route("/")
def home():

    cursor.execute("""
    SELECT username,date,done,problems,plan
    FROM reports
    ORDER BY id DESC
    LIMIT 100
    """)

    rows = cursor.fetchall()

    html = "<h2>📊 Team Reports</h2><table border=1>"

    html += "<tr><th>User</th><th>Date</th><th>Done</th><th>Problems</th><th>Plan</th></tr>"

    for r in rows:

        html += f"""
        <tr>
        <td>@{r[0]}</td>
        <td>{r[1]}</td>
        <td>{r[2]}</td>
        <td>{r[3]}</td>
        <td>{r[4]}</td>
        </tr>
        """

    html += "</table>"

    return html