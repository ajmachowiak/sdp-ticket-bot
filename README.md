# 🤖 ServiceDesk Plus Scheduled Checks Ticket Bot

A lightweight, zero touch Python background automation system designed to automate the logging and assignment of recurring operational, security and site specific audit checks in **ServiceDesk Plus (SDP)**.

Built with **Python**, **ServiceDesk Plus REST API v3** and automated scheduling logic.
This bot eliminates manual UI navigation, handles weekly duty rotations automatically and dynamically injects calculated parameters for seamless updates.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![ServiceDesk Plus](https://img.shields.io/badge/ServiceDesk%20Plus-REST%20API%20v3-orange.svg)](https://www.manageengine.com/products/service-desk/)

---

## ⚡ Key Features

* **Zero-Touch Automated Dispatch:** Runs silently on scheduled triggers (Mondays and 1st weekday of the month) to dispatch check tickets.
* **Smart Duty Rotation:** `rota_helper.py` shifts engineer assignments forward using *modulo arithmetic* (`+1`), maintaining seamless task distribution.
* **Leave & Exception Handling:** Engineers comment out absent team members in `engineers.md` (`<!-- engineer.one@company.com -->`). The bot automatically filters out absent engineers and applies fallbacks without skipping tickets.
* **Markdown Frontmatter & HTML Rendering:** Converts task templates from `/templates/*.md` into rich HTML formatted for SDP ticket descriptions.
* **Dynamic Parameter Injection:** Calculates and injects dates (e.g. `{{ WEEK_COMMENCING }}`, `{{ CURRENT_DATE }}`, `{{ YEAR }}`) into titles and body text at runtime.
* **OAuth2 Authentication:** Designed specifically for SDP Cloud (ManageEngine / Zoho OAuth2) server-based apps using refresh token exchange.
* **Dry-Run & Audit Logging:** Features a `--dry-run` flag for testing without making network calls and generates date-stamped execution logs (`HHMMSS_DDMMYYYY.log`) in `/logs/`.

---

## 📁 Repository Structure

```text
sdp-ticket-bot/
├── templates/                      # markdown templates for SDP audit tickets
│   ├── weekly/                     # daily and weekly check templates
│   │  ├── weekly_checks.md
│   │  ├── daily_checks.md
│   └── monthly/                    # monthly check templates
│   │  └── monthly_checks.md
├── logs/                           # automated date stamped runtime logs (HHMMSS_DDMMYYYY.log)
├── .env.example                    # environment variables template (API keys, URLs)
├── app.py                          # main app script (SDP REST API POSTs)
├── config.py                       # centralised organisational settings and path definitions
├── engineers.md                    # active team roster and leave management file
├── README.md                       # project documentation
├── requirements.txt                # python package dependencies
├── rota.md                         # live duty rota mapping task templates to engineer UPNs
└── rota_helper.py                  # helper script to auto-shift engineer assignments (+1)
```

---

## 📋 Prerequisites

* **Python:** 3.10 or higher.
* **ManageEngine ServiceDesk Plus:** Cloud or On-Premise instance with REST API v3 access.
* **API Credentials:** SDP OAuth2 credentials with specified scopes mentioned in the SDP API Scope section.
* **Environment:** Server or task scheduler capable of running scheduled Python jobs (*Cron* / *Windows Task Scheduler*).

---

## 🔬 SDP API Scopes

The scopes required for the service account used by this application:

```text
SDPOnDemand.requests.CREATE,SDPOnDemand.requests.READ,SDPOnDemand.setup.READ
```

This allows the bot to check if any open tickets already exists (`SDPOnDemand.requests.READ`), create new tickets (`SDPOnDemand.requests.CREATE`) and lastly, read system setup data to map technician UPNs and categories (`SDPOnDemand.setup.READ`).

---

## 🚀 Installation & Setup

### 1. Clone Repository
```bash
git clone https://github.com/OriginalMistake/sdp-ticket-bot.git
cd sdp-ticket-bot
```

### 2. Create virtual environment and install dependencies
```bash
python -m venv venv
venv\Scripts\activate  # On Linux/macOS use: source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure secrets (`.env`)
Copy the example environment file:
```bash
cp .env.example .env
```

### 4. Edit `.env`:
Edit the `.env` file with your actual SDP details:

```py
# SDP base URLs (adjust domain if using .com, .in or .au {e.g. https://sdpondemand.manageengine.com})
SDP_BASE_URL=https://sdpondemand.manageengine.eu
SDP_ACCOUNTS_URL=https://accounts.zoho.com

# server-based OAuth2 application credentials
SDP_CLIENT_ID=your_zoho_client_id_here
SDP_CLIENT_SECRET=your_zoho_client_secret_here
SDP_REFRESH_TOKEN=your_zoho_refresh_token_here

# system logging
LOG_LEVEL=INFO
```

---

## 🛠️ Configuration (`config.py`)

Organisational default ticket values (used when templates do not explicitly specify frontmatter values) are defined in `config.py`:

```py
SDP_REQUESTER_EMAIL = "itsupport@company.com"
SDP_CATEGORY = "Compliance Checks"
SDP_REQUEST_TYPE = "Support"
SDP_MODE = "Web form"
SDP_IMPACT = "Affects User"
SDP_URGENCY = "Low"
SDP_PRIORITY = "Low"
```

---

## ✏️ Creating Templates & Managing Rota

### 1. Managing Engineer Availability (`engineers.md`)
List all engineer UPNs/emails.  
Comment out users on leaving using HTML comments (`<!-- -->`):

```md
# UPN Roster

engineer.one@company.com
<!-- engineer.two@company.com -->
engineer.three@company.com
engineer.four@company.com
```

### 2. Writing Ticket Templates (`templates/weekly/test_check_weekly.md`)
Templates use standard YAML frontmatter for meta data, followed by Markdown for the description body.  
Dynamic placeholders like `{{ WEEK_COMMENCING }}` will be resolved automatically.

```md
---
title: Sample Weekly System Checks - W/C {{ WEEK_COMMENCING }}
category: Operational Checks
priority: Medium
---

### Tasks
* Verify offsite backup replication logs for week of {{ WEEK_COMMENCING }}
* Review system performance metrics across core servers
* Complete weekly security patch review

---

### Copy & Paste Update (for Teams/Slack Notification)

> **Weekly System Checks - W/C {{ WEEK_COMMENCING }}**
> 
> The following Weekly System Checks have been completed for {{ WEEK_COMMENCING }}:
>
> * Offsite Backup Verification
> * Performance & Capacity Review
> * Security Patch Status
> 
> *No issues to report.*
```

---

## 🧪 Usage & Testing

### 1. Dry-Run Mode (Simulation)
Test template parsing, date injection and JSON payload construction without creating real tickets or consuming API tokens:

```bash
python app.py --schedule weekly --dry-run
```

### 2. Manual Rota Shift
Shift assignments manually to preview technician rotations:

```bash
python rota_helper.py
```

## ⏱️ Production Automation Setup

To ensure zero-touch operation, configure two separate scheduled tasks in Windows Task Scheduler on your automation host server:

### Option 1: Windows Server (Task Scheduler)
> **Note:** The details below are examples, you can modify time/date/path etc. to suit your organisational needs.

#### Task 1: Weekly & Daily Checks
**Trigger:** Every Monday at 08:00 AM  

**Action 1 (Shift Rota):**
* **Program:** `C:\path\to\venv\Scripts\python.exe`
* **Arguments:** `rota_helper.py`
* **Start in:** `C:\path\to\sdp-ticket-bot`  

**Action 2 (Dispatch Tickets):**
* **Program:** `C:\path\to\venv\Scripts\python.exe`
* **Arguments:** `app.py --schedule weekly`
* **Start in:** `C:\path\to\sdp-ticket-bot`  

#### Task 2: Monthly Checks
**Trigger:** 1st day of every month at 08:00 AM  

**Action:**
* **Program:** `C:\path\to\venv\Scripts\python.exe`
* **Arguments:** `app.py --schedule monthly`
* **Start in:** `C:\path\to\sdp-ticket-bot`

### Option 2: Linux Server (Cron)

Edit your crontab (`crontab -e`):

#### Weekly & Daily Checks (Mondays)
```bash
0 7 * * 1 cd /path/to/sdp-ticket-bot && /path/to/venv/bin/python rota_helper.py && /path/to/venv/bin/python app.py --schedule weekly
```

#### Monthly Audit Checks (1st of every month)
```bash
0 7 1 * * cd /path/to/sdp-ticket-bot && /path/to/venv/bin/python app.py --schedule monthly
```

---

## 🧠 Logic Flow

```text
    (engineer edits rota.md ahead of time IF needed)
                         │
                         ▼
                [ Scheduled Trigger ]
                         │
                         ▼
                [ rota_helper.py ]
                         │
                         ├── reads engineers.md (filters out <!-- commented --> users)
                         ├── reads rota.md
                         └── rotates assignments (+1)
                         │
                         ▼
                 [ app.py execution ]
                         │
                         ├── loads Markdown templates from /templates/{schedule}/
                         ├── injects dates (e.g. {{ WEEK_COMMENCING }}, {{ CURRENT_DATE }})
                         ├── converts Markdown body -> SDP HTML
                         ├── fetches OAuth2 access token
                         └── dispatches tickets to SDP
                         │
                         ▼
         [ Logs saved to /logs/HHMMSS_DDMMYYYY.log ]
```

---

## 💬 Issues & Support

If you encounter a bug, have a feature request or run into issues:
1. **Check existing issues:** Search the *GitHub Issues* tab to see if it has already been reported.
2. **Open a new issue:** Provide details about expected vs actual behavior, along with relevant error logs *(ensuring no sensitive data or credentials are included)*.
3. **Pull Requests:** Contributions are welcome! If you'd like to fix a bug or add a feature, feel free to fork the repo and submit a PR.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.