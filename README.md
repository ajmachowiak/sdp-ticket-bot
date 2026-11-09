# ServiceDesk Plus Scheduled Checks Ticket Bot

A Python background automation tool designed to automate the creation, dynamic date rendering, and engineer assignment for recurring operational, security, and site-specific maintenance checks in ServiceDesk Plus (SDP).

The system parses Markdown templates with YAML frontmatter, injects dynamic dates, converts body text into formatted HTML, and dispatches tickets via the SDP REST API v3 using threaded batch execution.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![ServiceDesk Plus](https://img.shields.io/badge/ServiceDesk%20Plus-REST%20API%20v3-orange.svg)](https://www.manageengine.com/products/service-desk/)

---

## Context & Impact

In busy IT environments, manually logging recurring daily, weekly, and monthly maintenance tickets (e.g. audit checks, lifecycle runs, security checks etc.) is repetitive and easy to forget. Manual creation often leads to inconsistent ticket formats, incorrect ticket assignments or a delay in the tasks being carried out.

I built this bot to run headlessly as a scheduled background task. It reads markdown templates, injects dynamic date parameters, auto-rotates engineers across site pools, and dispatches + assigns tickets directly in SDP.

### Impact
* Eliminates manual daily, weekly, and monthly ticket creation entirely.
* Rotates engineers across site pools automatically on ticket dispatch, eliminating the need to manually assign or triage incoming maintenance tickets.
* Parallel dispatches process ticket templates in bulk rather than executing slow sequential API calls.

---

## Key Features

* Uses `ThreadPoolExecutor` in `app.py` to dispatch tickets asynchronously across worker threads, accelerating batch runs.
* Parses section headers in `engineers.md` (e.g. `## London`, `## Tokyo`) to ensure site tagged tickets pull exclusively from their local engineer pool.
* Tracks a `used_engineers` state per execution run to prevent assigning the same engineer multiple checks in a single batch. Gracefully handles 1-engineer pools without breaking rotation math.
* Automatically sets ticket assignment to `Unassigned` if a site pool has no active engineers listed (e.g. all team members commented out on leave).
* Supports `draft: true` frontmatter to skip execution on work-in-progress templates, plus a `--test` CLI flag to dispatch real API payloads with a `[TESTING]` subject prefix.
* Resolves place-holders (`{{ WEEK_COMMENCING }}`, `{{ WEEK_ENDING }}`, `{{ THURSDAY_DATE }}`, `{{ CURRENT_DATE }}`, `{{ MONTH }}`, `{{ YEAR }}`) at runtime.

---

## Logic Flow

```text
                  [ Scheduled Trigger ]
                            │
                            ▼
                    [ rota_helper.py ]
                            │
                            ├── Parsers engineers.md (filters commented out UPNs)
                            ├── Segregates engineers into site pools (## London, ## Tokyo)
                            └── Rotates duty pools (+1)
                            │
                            ▼
                    [ app.py execution ]
                            │
                            ├── Filters out 'draft: true' templates
                            ├── Injects dynamic dates (e.g. {{ WEEK_COMMENCING }})
                            ├── Converts Markdown body -> SDP HTML
                            └── Parallel Dispatch via ThreadPoolExecutor -> SDP API
                            │
                            ▼
         [ Execution logs saved to /logs/HHMMSS_DDMMYYYY.log ]
```

---

## Repository Structure

```text
sdp-ticket-bot/
├── templates/                      # Markdown templates with YAML frontmatter
│   ├── weekly/                     # daily/weekly ticket templates
│   └── monthly/                    # monthly ticket templates
├── logs/                           # runtime execution logs (HHMMSS_DDMMYYYY.log)
├── .env.example                    # environment secrets template
├── app.py                          # main dispatch engine and ThreadPoolExecutor logic
├── config.py                       # global settings and default ticket metadata
├── engineers.md                    # active engineer roster organised by site headers
├── README.md                       # project documentation
├── requirements.txt                # python dependencies
├── rota.md                         # active duty assignment mappings
└── rota_helper.py                  # rotation script handling site pools and shift logic
```

---

## Prerequisites & Scopes

* Python 3.10+
* ServiceDesk Plus instance with REST API v3 enabled.
* SDP OAuth2 credentials with specified scopes mentioned in the ***SDP API Scope*** section.

---

## SDP API Scope

The scope required for the service account used by this application:

```text
SDPOnDemand.requests.CREATE,SDPOnDemand.requests.READ,SDPOnDemand.setup.READ
```

This allows the bot to check if any open tickets already exists (`SDPOnDemand.requests.READ`), create new tickets (`SDPOnDemand.requests.CREATE`), and lastly, read system setup data to map engineer UPNs and categories (`SDPOnDemand.setup.READ`).

---

## Quick Start & Usage

### 1. Installation
```bash
git clone https://github.com/ajmachowiak/sdp-ticket-bot.git
cd sdp-ticket-bot
pip install -r requirements.txt
```

### 2. Configure Environment (`.env`)
Copy the example environment file and update with your OAuth2 credentials:
```bash
cp .env.example .env
```

```ini
SDP_BASE_URL=https://sdpondemand.manageengine.eu
SDP_ACCOUNTS_URL=https://accounts.zoho.com

SDP_CLIENT_ID=your_zoho_client_id_here
SDP_CLIENT_SECRET=your_zoho_client_secret_here
SDP_REFRESH_TOKEN=your_zoho_refresh_token_here

LOG_LEVEL=INFO
```

### 3. Command Line Arguments

```bash
# dry-run execution (validates template parsing, date injection, and prints JSON without network calls)
python app.py --schedule weekly --dry-run

# live test dispatch (creates real SDP tickets with [TESTING] prefix added to the ticket subject)
python app.py --schedule weekly --test

# creates a preview.html file in your directory for you to view the template.md in HTML format
python -c "import app, markdown; parsed = app.parse_template_file('templates/monthly/monthly_audit_checks.md'); open('preview.html', 'w', encoding='utf-8').write(parsed['html_body']); print('preview.html created!')"

# rota.md rotation execution
python rota_helper.py

# production execution
python app.py --schedule weekly
python app.py --schedule monthly
```

---

## Roster & Template Configuration

### Managing Engineers (`engineers.md`)
Group engineers under site headers (`## SiteName`). Comment out engineers on leave using standard HTML comments (`<!-- -->`).
Ensure that the site name does **NOT** have a space between (as shown in "AllSites").

```markdown
# Site Roster

## NewYork
- engineer.one@company.com

## London
<!-- - engineer.two@company.com -->
- engineer.three@company.com

## Tokyo
- engineer.four@company.com
<!-- - engineer.five@company.com -->
- engineer.six@company.com

## AllSites
- engineer.one@company.com
<!-- - engineer.two@company.com -->
- engineer.three@company.com
- engineer.four@company.com
<!-- - engineer.five@company.com -->
- engineer.six@company.com
```

### Template Frontmatter (`/templates/weekly/weekly_AV_check_LD.md`)
Templates use YAML frontmatter for metadata and Markdown for the body. Use dynamic date variables as needed:

```markdown
---
title: Sample Weekly AV System Checks - London - W/C {{ WEEK_COMMENCING }}
category: Operational Checks
priority: Medium
site: London
---

### Tasks
* Book a testing meeting with another IT Support colleague. 
* Check Audio - all microphones and speakers are operational.
* Check Video - both rear and Audience cameras are operational.
* Check Screen share is working.
```

---

## Date Injectors

The bot resolves the following place-holders dynamically at runtime:

* `{{ WEEK_COMMENCING }}` – first day of the current week (Monday)
* `{{ WEEK_ENDING }}` – last day of the current week (Friday)
* `{{ CURRENT_DATE }}` – date of ticket submission
* `{{ THURSDAY_DATE }}` – Thursday of the current week (specific day is configurable in script)
* `{{ MONTH }}` – current month name
* `{{ YEAR }}` – current year

---

## Production Automation Setup

To ensure zero-touch operation, configure two separate scheduled tasks in Windows Task Scheduler on your automation host server:

### Weekly & Daily Checks
* **Trigger:** Every Monday at 08:00 AM
* **Action 1 (Rotate Rota):**
  * **Program/script:** `C:\path\to\venv\Scripts\python.exe`
  * **Add arguments:** `rota_helper.py`
  * **Start in:** `C:\path\to\sdp-ticket-bot`  
* **Action 2 (Dispatch Tickets):**
  * **Program/script:** `C:\path\to\venv\Scripts\python.exe`
  * **Add arguments:** `app.py --schedule weekly`
  * **Start in:** `C:\path\to\sdp-ticket-bot`

### Monthly Audit Checks
* **Trigger:** 1st day of every month at 08:00 AM
* **Action (Dispatch Tickets):**
  * **Program/script:** `C:\path\to\venv\Scripts\python.exe`
  * **Add arguments:** `app.py --schedule monthly`
  * **Start in:** `C:\path\to\sdp-ticket-bot`

---

## License

Distributed under the MIT License. See `LICENSE` for details.
