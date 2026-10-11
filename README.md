# Learning Management System

A Flask-based learning platform for students, instructors, and administrators. Built with SQLite, server-rendered templates, and vanilla JavaScript.

## Features

- **Course management** — enrollments, teaching assignments, and course materials.
- **Assignments and grading** — file submissions, scores, and instructor feedback.
- **Discussion forums** — topic lists, numbered replies, and member management.
- **Private messages** — a bubble-style inbox with recipient lookup by name or personal ID.
- **Advanced search** — field filters, phrases, exclusions, and numeric or date ranges.
- **Responsive interface** — an English-language UI for desktop and mobile.
- **Access control** — role-based permissions, hashed passwords, CSRF protection, and revocable sessions.

## Getting Started

### Requirements

- Python 3.10–3.12
- Git

SQLite is included with Python. A MySQL server is not required. The original dependency versions are preserved in `requirements.txt`.

### Installation

```sh
git clone https://github.com/Orangestella/learning_management_system.git
cd learning_management_system
python -m venv .venv
```

Activate the virtual environment:

| Platform | Command |
| --- | --- |
| Windows PowerShell | `.\.venv\Scripts\Activate.ps1` |
| macOS / Linux | `source .venv/bin/activate` |

Then install the dependencies:

```sh
python -m pip install -r requirements.txt
```

### Create Your First Account

For a fresh installation, create an administrator:

```sh
python -m flask create-admin
```

Follow the prompts and note the generated personal ID. Passwords must contain at least 10 characters.

To use the original repository data instead, run `import-legacy` **before creating any accounts**. See [Legacy Data](#legacy-data) below.

### Run Locally

```sh
python app.py
```

Open [localhost:5000](http://127.0.0.1:5000) and sign in with your **personal ID and password**. The database is created automatically on first use. Stop the server with `Ctrl+C`.

## Legacy Data

Import the original MySQL dump into SQLite:

```sh
python -m flask import-legacy
```

The import preserves IDs and relationships, backs up the database, and generates new passwords for imported accounts. Login details are saved to `instance/legacy-credentials-*.csv`; backups are stored in `instance/backups/`. These local files are excluded from Git.

Repeated imports skip unchanged records and retain existing passwords. Conflicting records stop the import without overwriting data.

The original repository does not include the attachment files referenced by its dump. To restore them, place the originals in `static/files/` and rerun the import.

## Search

Use the search dropdown to choose a field, or click **?** for the fields supported on the current page.

| Example | Result |
| --- | --- |
| `name:"Course One"` | Match a phrase in a specific field |
| `name:English instructor:Edgar` | Match both conditions |
| `id:1 OR id:2` | Match either condition |
| `-name:Python` | Exclude matches |
| `name:=English` | Match text exactly |
| `id:>=2 id:<10` | Filter a numeric range |
| `deadline:>=2026-01-01 deadline:<2027-01-01` | Filter a date range |

AND takes precedence over OR. Parenthesized groups are not supported.

## Configuration

| Variable | Purpose |
| --- | --- |
| `LMS_SECRET_KEY` | A stable signing key supplied by your deployment environment |
| `LMS_HTTPS=1` | Enable secure cookies and HSTS when serving over HTTPS |

Local development generates a persistent key in `instance/secret.key`. SQLite data and private uploads also live in `instance/`; back up this directory to preserve your installation.

Use a production WSGI server with `app:app` for deployment. `python app.py` starts the local development server.

## Testing

Run the test suite using Python's built-in `unittest`:

```sh
python -m unittest discover -s tests -v
```

Tests use isolated temporary databases and cover authentication, permissions, search, imports, messaging, and course workflows.
